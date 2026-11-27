"""Scénario « rue fermée » pour une rue donnée : prepare -> simulate -> export -> publish.

Généralise sim/senario_rue_fermee/ (écrit pour une seule rue, Avenue Allal Ben Abdellah) à n'importe quelle
rue de data/street_index.json. Même méthode, mêmes paramètres :
  - le réseau de référence et la demande de référence (300 véhicules) ne sont jamais modifiés ;
  - on interdit toutes les voies des tronçons fermés (disallow="all") ;
  - seules les voitures dont l'itinéraire passait par la rue sont re-routées (duarouter) ;
  - un seul tirage, graine fixe : même graine et même durée que la situation actuelle de référence ;
  - la situation actuelle n'est jamais recalculée : on compare à data/tripinfo_actuel_ref.xml.

Sorties dans data/scenarios/<street_id>/ (cache : si elles existent, rien n'est recalculé) :
  meta.json, trajectories_rue_fermee.json, kpi_rue_fermee.json, closed_edges.geojson, status.json

Chaque étape lit et écrit des fichiers dans un dossier de travail `.staging-<run>` ; seule `publish` touche
aux fichiers visibles par la vue 3D. Les valeurs échangées entre étapes (`ctx`) sont de petits dictionnaires.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from . import config as C
from .street_index import StreetError, get_street, is_valid_id

SKIP_CACHE = "cache"        # scénario déjà prêt
SKIP_BUSY = "en_cours"      # un autre run calcule déjà cette rue


# ------------------------------------------------------------------------------------------------ fichiers
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_run_id(run_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id))[:80] or "run"


def _write_json(path, obj, compact=False):
    """Écriture atomique : la vue 3D ne lit jamais un fichier à moitié écrit."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":") if compact else None,
                              indent=None if compact else 2), encoding="utf-8")
    os.replace(tmp, path)


def scenario_dir(street_id):
    if not is_valid_id(street_id):
        raise StreetError("street_id invalide")
    return C.SCENARIOS / street_id


def is_ready(street_id):
    d = scenario_dir(street_id)
    return all((d / f).is_file() for f in C.FILES)


def read_status(street_id):
    """État d'une rue, pour get_scenario et pour la vue 3D : ready, running, failed ou missing."""
    d = scenario_dir(street_id)
    st = {}
    f = d / "status.json"
    if f.is_file():
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            st = {}
    if is_ready(street_id):
        return {**st, "street_id": street_id, "state": "ready", "step": "done", "error": None}
    if st.get("state") == "running" and time.time() - st.get("updated_epoch", 0) > C.LOCK_TTL_S:
        return {**st, "state": "failed", "error": "calcul interrompu (état périmé)"}
    if st.get("state") in ("running", "failed"):
        return st
    return {"street_id": street_id, "state": "missing"}


def _set_status(street_id, run_id, state, step, error=None):
    sdir = scenario_dir(street_id)
    f = sdir / "status.json"
    old = {}
    if f.is_file():
        try:
            old = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    started = old.get("started_at") if old.get("run_id") == run_id else None
    _write_json(f, {"street_id": street_id, "state": state, "step": step, "run_id": run_id,
                    "started_at": started or _now(), "updated_at": _now(), "updated_epoch": time.time(),
                    "error": error})
    lock = sdir / ".lock"
    if lock.exists():
        os.utime(lock)       # le verrou reste « frais » tant que le calcul avance


# ------------------------------------------------------------------------------------------------- verrou
def _acquire_lock(sdir, run_id):
    """Un seul calcul à la fois par rue. Reprise possible par le même run (nouvelle tentative)."""
    lock = sdir / ".lock"
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                holder = json.loads(lock.read_text(encoding="utf-8") or "{}")
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue            # libéré entre-temps : on réessaie
            except ValueError:
                holder, age = {}, 0     # en cours d'écriture par un autre : on le considère occupé
            if holder.get("run_id") == run_id:
                return True
            if age > C.LOCK_TTL_S:
                lock.unlink(missing_ok=True)    # verrou abandonné
                continue
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"run_id": run_id, "epoch": time.time()}, fh)
        return True
    return False


def _release_lock(sdir, run_id):
    lock = sdir / ".lock"
    try:
        if json.loads(lock.read_text(encoding="utf-8")).get("run_id") == run_id:
            lock.unlink(missing_ok=True)
    except (FileNotFoundError, ValueError):
        pass


# ------------------------------------------------------------------------------------------------- réseau
def _edge_nodes():
    """{rue SUMO: (noeud de départ, noeud d'arrivée)}, voies internes des carrefours exclues."""
    info = {}
    for _, el in ET.iterparse(C.NET_REF, events=("end",)):
        if el.tag == "edge":
            if el.get("function") != "internal" and el.get("from"):
                info[el.get("id")] = (el.get("from"), el.get("to"))
            el.clear()
    return info


def compute_closure(street_edges, close_crossings=None):
    """(tronçons de la rue, rues transversales fermées avec eux).

    Même règle que sim/senario_rue_fermee/common.py : les rues qui entrent ou sortent d'un carrefour
    situé entre deux tronçons fermés sont fermées aussi (FERMER_CARREFOURS=0 pour les laisser ouvertes).
    Un carrefour est « intérieur » si la rue le traverse, pas si elle y fait seulement demi-tour (extrémité
    d'une rue à double sens).
    """
    close_crossings = C.FERMER_CARREFOURS if close_crossings is None else close_crossings
    info = _edge_nodes()
    street = set(street_edges)
    missing = street - set(info)
    if missing:
        raise StreetError(f"tronçons absents du réseau : {sorted(missing)[:5]}")
    transv = set()
    if close_crossings:
        starts, ends = defaultdict(list), defaultdict(list)
        for e in street:
            a, b = info[e]
            starts[a].append(e)
            ends[b].append(e)
        interior = {n for n, outs in starts.items() for o in outs for i in ends.get(n, ())
                    if info[o][1] != info[i][0]}
        transv = {e for e, (a, b) in info.items() if e not in street and (a in interior or b in interior)}
    return sorted(street), sorted(transv)


_LANE = re.compile(r'<lane id="(.+?)_\d+"[^>]*>')


def _write_closed_net(closed, out):
    """Copie du réseau où toutes les voies des tronçons fermés sont interdites. Retourne le nombre de voies."""
    closed, found, voies = set(closed), set(), 0

    def patch(m):
        nonlocal voies
        if m.group(1) not in closed:
            return m.group(0)
        found.add(m.group(1))
        voies += 1
        tag = re.sub(r'\s(allow|disallow)="[^"]*"', "", m.group(0))
        return tag.replace("<lane", '<lane disallow="all"', 1)

    text = _LANE.sub(patch, C.NET_REF.read_text(encoding="utf-8"))
    if closed - found:
        raise StreetError(f"tronçons sans voie dans le réseau : {sorted(closed - found)[:5]}")
    out.write_text(text, encoding="utf-8")
    return voies


# ------------------------------------------------------------------------------------------------- SUMO
@lru_cache(maxsize=1)
def sumo_version():
    r = subprocess.run(["sumo", "--version"], capture_output=True, text=True, timeout=30)
    m = re.search(r"SUMO sumo (\d+\.\d+\.\d+)", r.stdout)
    return m.group(1) if m else "inconnue"


def _run(cmd, what):
    """Lance un programme SUMO sans shell : aucun texte venu de l'extérieur n'entre dans la commande."""
    try:
        subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, timeout=C.SUMO_TIMEOUT_S)
    except FileNotFoundError:
        raise RuntimeError(f"{cmd[0]} introuvable : SUMO n'est pas installé dans cette image")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{what} a échoué (code {exc.returncode}) : {(exc.stderr or exc.stdout or '')[-600:]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{what} : délai de {C.SUMO_TIMEOUT_S} s dépassé")


def _route_edges(veh):
    edges = []
    for route in veh.iter("route"):
        edges += (route.get("edges") or "").split()
    return edges


# ------------------------------------------------------------------------------------------------ étapes
def _check_stage(ctx):
    sdir = scenario_dir(ctx["street_id"]).resolve()
    stage = Path(ctx["stage"]).resolve()
    if stage.parent != sdir or not stage.name.startswith(".staging-") or not stage.is_dir():
        raise RuntimeError("dossier de travail invalide ou absent : relancer depuis prepare")
    return stage


def prepare(street_id, run_id, force=False, edges=None):
    """Étape 1 : contrôle du street_id, cache, verrou, réseau fermé, demande re-routée.

    Retourne {"skip": "cache" | "en_cours"} si rien n'est à faire, sinon le contexte des étapes suivantes.
    `edges` remplace les tronçons de l'index : réservé aux tests, jamais exposé par un DAG.
    """
    t0 = time.time()
    street = get_street(street_id)                      # liste blanche : lève StreetError sinon
    if is_ready(street_id) and not force:
        return {"skip": SKIP_CACHE}
    sdir = scenario_dir(street_id)
    sdir.mkdir(parents=True, exist_ok=True)
    if not _acquire_lock(sdir, run_id):
        return {"skip": SKIP_BUSY}
    if is_ready(street_id) and not force:               # un autre run a fini entre-temps
        _release_lock(sdir, run_id)
        return {"skip": SKIP_CACHE}

    _set_status(street_id, run_id, "running", "prepare")
    stage = sdir / f".staging-{_safe_run_id(run_id)}"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()

    rue, transv = compute_closure(edges if edges is not None else street["edges"])
    closed = rue + transv
    voies = _write_closed_net(closed, stage / "closed.net.xml")
    _write_json(stage / "closure.json", {"rue": rue, "transversales": transv})

    # Demande : seules les voitures dont l'itinéraire passait par la rue fermée sont re-routées
    tree = ET.parse(C.ROU_REF)
    root = tree.getroot()
    fermes = set(closed)
    touches = []
    for v in root.findall("vehicle"):
        e = _route_edges(v)
        if e and fermes & set(e):
            touches.append((v.get("id"), v.get("depart"), e[0], e[-1]))
    n_ref = len(root.findall("vehicle"))

    nouveaux = {}
    if touches:
        trips = ET.Element("routes")
        for vid, depart, a, b in touches:
            ET.SubElement(trips, "trip", {"id": vid, "depart": depart, "from": a, "to": b})
        ET.ElementTree(trips).write(stage / "touches.trips.xml", encoding="utf-8")
        _run(["duarouter", "-n", stage / "closed.net.xml", "--route-files", stage / "touches.trips.xml",
              "-o", stage / "touches.rou.xml", "--ignore-errors", "--no-warnings", "--no-step-log"], "duarouter")
        nouveaux = {v.get("id"): _route_edges(v) for v in ET.parse(stage / "touches.rou.xml").getroot().iter("vehicle")}

    ids_touches = {t[0] for t in touches}
    deviees = retires = 0
    for v in list(root.findall("vehicle")):
        if v.get("id") not in ids_touches:
            continue
        if nouveaux.get(v.get("id")):
            r = v.find("route")
            r.set("edges", " ".join(nouveaux[v.get("id")]))
            for k in ("cost", "savings"):
                r.attrib.pop(k, None)
            deviees += 1
        else:                       # départ ou arrivée sur la rue fermée : plus d'itinéraire, on le compte
            root.remove(v)
            retires += 1
    tree.write(stage / "closed.rou.xml", encoding="utf-8", xml_declaration=True)

    demande = {"vehicules_reference": n_ref, "voitures_sur_la_rue_fermee": len(touches),
               "deviees": deviees, "sans_itineraire": retires,
               "ids_concernees": sorted(ids_touches, key=lambda x: (len(x), x))}
    _write_json(stage / "demande.json", demande)
    return {"street_id": street_id, "run_id": run_id, "stage": str(stage), "voies_fermees": voies,
            "n_rue": len(rue), "n_transversales": len(transv),
            "durees_s": {"prepare": round(time.time() - t0, 2)}}


def simulate(ctx):
    """Étape 2 : une simulation SUMO, graine fixe, mêmes réglages que la situation actuelle de référence."""
    t0 = time.time()
    stage = _check_stage(ctx)
    _set_status(ctx["street_id"], ctx["run_id"], "running", "simulate")
    (stage / "additional.xml").write_text(
        f'<additional>\n  <edgeData id="edges" file="{stage / "edgedata.xml"}" period="60" excludeEmpty="true"/>\n'
        "</additional>\n", encoding="utf-8")
    _run(["sumo", "-n", stage / "closed.net.xml", "-r", stage / "closed.rou.xml", "-b", "0", "-e", C.SIM_END_S,
          "--seed", C.SEED, "--tripinfo-output", stage / "tripinfo.xml", "--device.emissions.probability", "1",
          "--additional-files", stage / "additional.xml", "--fcd-output", stage / "fcd.xml",
          "--fcd-output.geo", "true", "--no-step-log", "true", "--no-warnings", "true"], "sumo")
    return {**ctx, "durees_s": {**ctx["durees_s"], "simulate": round(time.time() - t0, 2)}}


def _projection():
    """Décalage et zone UTM du réseau (ligne <location> de hassan.net.xml)."""
    with open(C.NET_REF, encoding="utf-8", errors="ignore") as f:
        tete = f.read(6000)
    off = re.search(r'netOffset="([-\d.]+),([-\d.]+)"', tete)
    zone = re.search(r"\+zone=(\d+)", tete)
    if not (off and zone):
        raise RuntimeError("projection du réseau introuvable (ligne <location> de hassan.net.xml)")
    return float(off.group(1)), float(off.group(2)), int(zone.group(1))


def _utm_inverse(E, N, zone):
    """UTM (hémisphère nord, WGS84) -> (lon, lat). Repris de sim/senario_rue_fermee/common.py."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    b = [n / 2 - 2 * n ** 2 / 3 + 37 * n ** 3 / 96 - n ** 4 / 360, n ** 2 / 48 + n ** 3 / 15 - 437 * n ** 4 / 1440,
         17 * n ** 3 / 480 - 37 * n ** 4 / 840, 4397 * n ** 4 / 161280]
    d = [2 * n - 2 * n ** 2 / 3 - 2 * n ** 3, 7 * n ** 2 / 3 - 8 * n ** 3 / 5, 56 * n ** 3 / 15]
    xi, eta = N / (k0 * A), (E - 500000) / (k0 * A)
    xp = xi - sum(b[j] * math.sin(2 * (j + 1) * xi) * math.cosh(2 * (j + 1) * eta) for j in range(4))
    ep = eta - sum(b[j] * math.cos(2 * (j + 1) * xi) * math.sinh(2 * (j + 1) * eta) for j in range(4))
    chi = math.asin(math.sin(xp) / math.cosh(ep))
    lat = chi + sum(d[j] * math.sin(2 * (j + 1) * chi) for j in range(3))
    lon = math.radians(zone * 6 - 183) + math.atan2(math.sinh(ep), math.cos(xp))
    return math.degrees(lon), math.degrees(lat)


def _closed_geojson(rue, transv):
    """Tracé exact des tronçons fermés (même format que data/rue_fermee_troncons.geojson)."""
    ox, oy, zone = _projection()
    wanted = set(rue) | set(transv)
    feats = {}
    for _, el in ET.iterparse(C.NET_REF, events=("end",)):
        if el.tag == "edge":
            if el.get("id") in wanted:
                pts = [_utm_inverse(float(p.split(",")[0]) - ox, float(p.split(",")[1]) - oy, zone)
                       for p in el.find("lane").get("shape").split()]
                feats[el.get("id")] = {"type": "Feature",
                                       "properties": {"edge": el.get("id"),
                                                      "type": "transversale" if el.get("id") in transv else "rue"},
                                       "geometry": {"type": "LineString",
                                                    "coordinates": [[round(x, 6), round(y, 6)] for x, y in pts]}}
            el.clear()
    return {"type": "FeatureCollection", "features": [feats[e] for e in sorted(feats)]}


def _fcd_export(fcd, closed, tmax):
    """Trajectoires au format de data/trajectories_*.json, et nombre de positions sur une rue fermée."""
    paths, types, violations = defaultdict(list), {}, 0
    for _, el in ET.iterparse(fcd, events=("end",)):
        if el.tag == "timestep":
            t = float(el.get("time"))
            if t <= tmax:
                for v in el.findall("vehicle"):
                    if v.get("lane", "").rsplit("_", 1)[0] in closed:
                        violations += 1
                    paths[v.get("id")].append([round(float(v.get("x")), 6), round(float(v.get("y")), 6), t])
                    types[v.get("id")] = v.get("type", "car")
            el.clear()
    return [{"id": k, "type": types[k], "path": p} for k, p in paths.items() if len(p) > 1], violations


def _durations(tripinfo):
    out = {}
    for _, el in ET.iterparse(tripinfo, events=("end",)):
        if el.tag == "tripinfo":
            out[el.get("id")] = float(el.get("duration"))
            el.clear()
    return out


def _compute_kpi(tripinfo, edgedata):
    """Les 4 indicateurs, avec les formules de M4 (traffic/compute_kpi.py) : une seule définition."""
    if str(C.TRAFFIC) not in sys.path:
        sys.path.insert(0, str(C.TRAFFIC))
    try:
        import compute_kpi
    except ImportError as exc:
        raise RuntimeError(f"compute_kpi.py introuvable dans {C.TRAFFIC} (volume ./traffic monté ?) : {exc}")
    try:
        trip = compute_kpi.trip_kpi(tripinfo)
    except SystemExit as exc:           # compute_kpi.py sort avec un message s'il n'y a aucun trajet terminé
        raise RuntimeError(str(exc))
    return trip, compute_kpi.congestion(edgedata, C.SEUIL_CONGESTION, C.MIN_MESURES)


def export(ctx):
    """Étape 3 : trajectoires, indicateurs, tracé de la rue, contrôles de validité, meta.json."""
    t0 = time.time()
    street_id = ctx["street_id"]
    stage = _check_stage(ctx)
    _set_status(street_id, ctx["run_id"], "running", "export")
    street = get_street(street_id)
    closure = json.loads((stage / "closure.json").read_text(encoding="utf-8"))
    demande = json.loads((stage / "demande.json").read_text(encoding="utf-8"))
    closed = set(closure["rue"]) | set(closure["transversales"])

    trajectoires, violations = _fcd_export(stage / "fcd.xml", closed, C.SIM_END_S)
    if violations:
        raise RuntimeError(f"scénario invalide : {violations} positions de véhicules sur les tronçons fermés")
    _write_json(stage / "trajectories_rue_fermee.json", trajectoires, compact=True)

    trip, cong = _compute_kpi(stage / "tripinfo.xml", stage / "edgedata.xml")
    kpi = {"scenario": "rue_fermee", "street_id": street_id, "donnees": "simulees (SUMO)",
           "tirage": "tirage 1, indicatif", "seuil_congestion": C.SEUIL_CONGESTION, "min_mesures": C.MIN_MESURES,
           **trip, **cong}
    _write_json(stage / "kpi_rue_fermee.json", kpi)
    _write_json(stage / "closed_edges.geojson", _closed_geojson(closure["rue"], set(closure["transversales"])),
                compact=True)

    # Effet sur les voitures de la rue : mêmes voitures, terminées dans les deux cas, durée moyenne
    ref, new = _durations(C.REF_TRIPINFO), _durations(stage / "tripinfo.xml")
    communs = [v for v in demande["ids_concernees"] if v in ref and v in new]
    moy = lambda d: round(sum(d[v] for v in communs) / len(communs), 1) if communs else None
    impact = {"voitures_concernees": demande["voitures_sur_la_rue_fermee"], "deviees": demande["deviees"],
              "sans_itineraire": demande["sans_itineraire"], "comparables": len(communs),
              "duree_moyenne_actuel_s": moy(ref), "duree_moyenne_rue_fermee_s": moy(new),
              "ecart_s": round(moy(new) - moy(ref), 1) if communs else None,
              "ids_concernees": demande["ids_concernees"]}

    ref_arrives = None
    if C.REF_KPI.is_file():
        ref_arrives = json.loads(C.REF_KPI.read_text(encoding="utf-8")).get("trajets_termines")
    alertes = []
    if ref_arrives and trip["trajets_termines"] < C.ARRIVED_MIN_RATIO * ref_arrives:
        alertes.append(f"{trip['trajets_termines']} trajets terminés contre {ref_arrives} en situation actuelle")
    validation = {"positions_sur_rues_fermees": violations, "trajets_termines": trip["trajets_termines"],
                  "trajets_termines_actuel": ref_arrives, "alertes": alertes, "ok": not alertes}

    durees = {**ctx["durees_s"], "export": round(time.time() - t0, 2)}
    _write_json(stage / "meta.json", {
        "street_id": street_id, "street_name": street.get("name"), "scenario": "rue_fermee",
        "donnees": "simulees (SUMO)", "genere_le": _now(), "dag_run_id": ctx["run_id"],
        "sumo_version": sumo_version(),
        "tirage": {"graine": C.SEED, "n_tirages": 1, "fin_simulation_s": C.SIM_END_S, "statut": "tirage 1, indicatif"},
        "fermeture": {"carrefours_fermes": C.FERMER_CARREFOURS, "troncons_rue": closure["rue"],
                      "troncons_transversaux": closure["transversales"], "voies_fermees": ctx["voies_fermees"]},
        "impact": impact, "validation": validation, "durees_s": durees,
        "reference": {"trajectoires": "../../trajectories_actuel_ref.json", "kpi": "../../kpi_actuel_ref.json"}})
    return {**ctx, "durees_s": durees}


def publish(ctx):
    """Étape 4 : rend les fichiers visibles. meta.json en dernier : c'est lui qui dit « prêt »."""
    street_id, run_id = ctx["street_id"], ctx["run_id"]
    stage = _check_stage(ctx)
    sdir = scenario_dir(street_id)
    _set_status(street_id, run_id, "running", "publish")
    (sdir / "meta.json").unlink(missing_ok=True)        # recalcul forcé : le scénario n'est « prêt » qu'à la fin
    for name in C.FILES:
        os.replace(stage / name, sdir / name)
    shutil.rmtree(stage, ignore_errors=True)            # fcd.xml, tripinfo.xml... : lourds, non publiés
    _set_status(street_id, run_id, "ready", "done")
    _release_lock(sdir, run_id)
    return {"street_id": street_id, "state": "ready", "durees_s": ctx["durees_s"]}


# ------------------------------------------------------------------------------- erreurs et enchaînement
def mark_failed(street_id, run_id, error):
    """Note l'échec, nettoie le dossier de travail, libère le verrou. Sans effet pour une rue inconnue
    (aucun dossier n'est créé à partir d'un texte non validé). Les fichiers déjà publiés restent en place."""
    try:
        get_street(street_id)
        sdir = scenario_dir(street_id)
    except StreetError:
        return
    if not sdir.is_dir():
        return
    shutil.rmtree(sdir / f".staging-{_safe_run_id(run_id)}", ignore_errors=True)
    f = sdir / "status.json"
    try:
        old = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except ValueError:
        old = {}
    if not (old.get("state") == "failed" and old.get("run_id") == run_id and old.get("error")):
        # Airflow appelle l'échec de la tâche puis celui du run : le premier message, le plus précis, est gardé
        _set_status(street_id, run_id, "failed", "failed", error=str(error)[:500])
    _release_lock(sdir, run_id)


def run_pipeline(street_id, run_id, force=False, edges=None):
    """Les 4 étapes à la suite (DAG en lot, tests). Lève l'exception après avoir noté l'échec."""
    t0 = time.time()
    try:
        ctx = prepare(street_id, run_id, force=force, edges=edges)
        if ctx.get("skip"):
            return {"street_id": street_id, "state": ctx["skip"], "duree_s": round(time.time() - t0, 2)}
        res = publish(export(simulate(ctx)))
    except Exception as exc:
        mark_failed(street_id, run_id, f"{type(exc).__name__}: {exc}")
        raise
    return {**res, "duree_s": round(time.time() - t0, 2)}
