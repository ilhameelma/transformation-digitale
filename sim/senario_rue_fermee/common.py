"""Constantes et petites fonctions partagees par les scripts du scenario rue fermee.
A lancer depuis sim/senario_rue_fermee (comme les scripts de senario_rue_prive)."""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
DATA = Path(os.getenv("DATA_DIR") or os.getenv("OUTPUT_DIR") or SIM.parent / "data")
RUNS = HERE / "runs"

NET_REF = SIM / "hassan.net.xml"            # reseau de reference, jamais modifie
ROU_REF = SIM / "hassan.rou.xml"            # demande de reference (300 vehicules), jamais modifiee
NET_FERME = HERE / "hassan_rue_fermee.net.xml"
ROU_FERME = RUNS / "rue_fermee.rou.xml"

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


# Fermeture complete (defaut) : les tronçons de l'avenue ET les rues qui entrent ou sortent des carrefours situes
# entre ces tronçons, pour qu'aucune voiture ne traverse la section. FERMER_CARREFOURS=0 : tronçons de l'avenue seuls
# (les voitures des rues transversales peuvent alors traverser les carrefours).
FERMER_CARREFOURS = os.getenv("FERMER_CARREFOURS", "1") != "0"
_cache = {}


def structure_fermeture():
    """(avenue, transversales) : deux ensembles d'identifiants de rues SUMO."""
    if "s" in _cache:
        return _cache["s"]
    f = DATA / "closure_sumo.json"
    if not f.exists():
        sys.exit(f"{f} introuvable")
    avenue = set(json.loads(f.read_text(encoding="utf-8"))["edges"])
    transv = set()
    if FERMER_CARREFOURS:
        info = {}
        for _, el in ET.iterparse(NET_REF, events=("end",)):
            if el.tag == "edge":
                if el.get("function") != "internal" and el.get("from"):
                    info[el.get("id")] = (el.get("from"), el.get("to"))
                el.clear()
        manquants = avenue - set(info)
        if manquants:
            sys.exit(f"Rues absentes du reseau : {sorted(manquants)}")
        debuts = {info[e][0] for e in avenue}
        fins = {info[e][1] for e in avenue}
        interieurs = debuts & fins                      # carrefours entre deux tronçons fermes
        transv = {e for e, (a, b) in info.items() if e not in avenue and (a in interieurs or b in interieurs)}
    _cache["s"] = (avenue, transv)
    return _cache["s"]


def troncons_fermes():
    """Toutes les rues interdites a la circulation."""
    avenue, transv = structure_fermeture()
    return sorted(avenue | transv)


def route_de(veh):
    """Rues de l'itineraire d'un vehicule (element <route edges=...>)."""
    edges = []
    for route in veh.iter("route"):
        edges += (route.get("edges") or "").split()
    return edges


def ids_sur_axe(fermes):
    """Vehicules de la demande de reference dont l'itineraire passe par la rue fermee."""
    f = set(fermes)
    return {v.get("id") for v in ET.parse(ROU_REF).getroot().iter("vehicle") if f & set(route_de(v))}


def exiger(*programmes):
    for p in programmes:
        if shutil.which(p) is None:
            sys.exit(f"'{p}' introuvable : lancer ce script dans un conteneur avec SUMO (voir scenario_rue_fermee.ps1).")


def lance_sumo(net, rou, fin, seed, tripinfo, extra=()):
    cmd = ["sumo", "-n", net, "-r", rou, "-b", "0", "-e", fin, "--seed", seed,
           "--tripinfo-output", tripinfo, "--device.emissions.probability", "1",
           "--no-step-log", "true", "--no-warnings", "true", *extra]
    subprocess.run([str(c) for c in cmd], check=True, stdout=subprocess.DEVNULL)


def tripinfos(path):
    """{id: (duree_s, attente_s, co2_g)} des trajets termines."""
    out = {}
    for t in ET.parse(path).getroot().findall("tripinfo"):
        em = t.find("emissions")
        out[t.get("id")] = (float(t.get("duration")), float(t.get("waitingTime")),
                            float(em.get("CO2_abs")) / 1000 if em is not None else 0.0)
    return out


def _projection():
    """Decalage et zone UTM du reseau (ligne <location .../> du fichier .net.xml)."""
    with open(NET_REF, encoding="utf-8", errors="ignore") as f:
        tete = f.read(6000)
    off = re.search(r'netOffset="([-\d.]+),([-\d.]+)"', tete)
    zone = re.search(r"\+zone=(\d+)", tete)
    if not (off and zone):
        sys.exit("Projection du reseau introuvable (ligne <location> de hassan.net.xml)")
    return float(off.group(1)), float(off.group(2)), int(zone.group(1))


def utm_inverse(E, N, zone):
    """UTM (hemisphere nord, WGS84) -> (lon, lat) en degres (series de Kruger)."""
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


def troncons_lonlat(fermes):
    """{rue: [(lon, lat), ...]} : forme exacte (SUMO) de chaque troncon ferme."""
    ox, oy, zone = _projection()
    out = {}
    for _, el in ET.iterparse(NET_REF, events=("end",)):
        if el.tag == "edge":
            if el.get("id") in fermes:
                forme = el.find("lane").get("shape").split()
                out[el.get("id")] = [utm_inverse(float(p.split(",")[0]) - ox, float(p.split(",")[1]) - oy, zone)
                                     for p in forme]
            el.clear()
    return out