"""
run_scenario.py - M1 : simule UN scenario avec SUMO et exporte les trajectoires pour la vue 3D.
A lancer dans le conteneur sim (m1), qui contient SUMO.

Lit    : data/hassan.net.xml                 (reseau SUMO)
         data/<demande>.trips.xml            (cree par traffic/generate_demand.py)
Ecrit  : data/<demande>.rou.xml              (itineraires, via duarouter)
         data/tripinfo_<scenario>.xml        (une ligne par trajet termine : duree, longueur, CO2)
         data/edgedata_<scenario>.xml        (vitesse relative par rue et par minute)
         data/fcd_<scenario>.xml             (position de chaque vehicule a chaque seconde)
         data/trajectories_<scenario>.json   (meme format que trajectories_actuel.json)
         data/run_<scenario>.json            (resume : vehicules demandes / termines, version SUMO)

La demande est <demande> = "demand" pour le scenario "actuel", "demand_<scenario>" sinon.

Exemple (scenario pic de trafic +30 %) :
    python generate_demand.py --scale 1.3 --out /data/demand_pic.csv     (conteneur traffic)
    python run_scenario.py --scenario pic                                (conteneur sim)

Par securite, le script refuse d'ecraser des resultats existants sans --force
(il protege notamment les fichiers du scenario "actuel").
"""
import argparse
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_DATA = Path(os.getenv("DATA_DIR") or os.getenv("OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "data")


def run(cmd):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def count_tags(path, tag):
    n = 0
    for _, el in ET.iterparse(path):
        if el.tag == tag:
            n += 1
        el.clear()
    return n


def fcd_to_trajectories(fcd_path, out_path, every=1):
    """fcd.xml (lon/lat) -> [{"id":..., "path": [[lon, lat, t], ...]}, ...]"""
    paths = {}
    for _, el in ET.iterparse(fcd_path):
        if el.tag == "timestep":
            t = float(el.get("time"))
            if every <= 1 or abs(t % every) < 1e-9:
                for v in el.findall("vehicle"):
                    paths.setdefault(v.get("id"), []).append(
                        [round(float(v.get("x")), 6), round(float(v.get("y")), 6), round(t, 1)])
            el.clear()
    data = [{"id": vid, "path": p} for vid, p in paths.items() if len(p) > 1]
    Path(out_path).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    return len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, help="nom du scenario : actuel, pic, ...")
    ap.add_argument("--demand", help="prefixe du fichier de demande (defaut : demand pour actuel, demand_<scenario> sinon)")
    ap.add_argument("--end", type=int, default=900, help="duree simulee en secondes (comme hassan.sumocfg)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--every", type=int, default=1, help="garder un point de trajectoire toutes les N secondes")
    ap.add_argument("--force", action="store_true", help="ecraser les resultats existants")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    a = ap.parse_args()

    for exe in ("sumo", "duarouter"):
        if shutil.which(exe) is None:
            raise SystemExit(f"'{exe}' introuvable : ce script se lance dans le conteneur sim (m1), qui contient SUMO.")

    d, s = a.data, a.scenario
    prefix = a.demand or ("demand" if s == "actuel" else f"demand_{s}")
    net, trips, rou = d / "hassan.net.xml", d / f"{prefix}.trips.xml", d / f"{prefix}.rou.xml"
    tripinfo, edgedata, fcd = d / f"tripinfo_{s}.xml", d / f"edgedata_{s}.xml", d / f"fcd_{s}.xml"
    traj, summary, add = d / f"trajectories_{s}.json", d / f"run_{s}.json", d / f"additional_{s}.xml"

    for f in (net, trips):
        if not f.exists():
            raise SystemExit(f"Fichier manquant : {f}\n(reseau : conteneur sim ; demande : conteneur traffic)")
    existing = [f.name for f in (tripinfo, edgedata, fcd, traj) if f.exists()]
    if existing and not a.force:
        raise SystemExit(f"Resultats deja presents pour '{s}' : {', '.join(existing)}\nRelancez avec --force pour les remplacer.")

    # 1) itineraires
    run(["duarouter", "-n", net, "--route-files", trips, "-o", rou, "--ignore-errors", "--no-warnings"])

    # 2) mesure par rue et par minute (intervalles de 60 s, rues vides ignorees)
    add.write_text(f'<additional>\n    <edgeData id="edges_{s}" file="{edgedata}" period="60" excludeEmpty="true"/>\n</additional>\n',
                   encoding="utf-8")

    # 3) simulation
    run(["sumo", "-n", net, "-r", rou, "--begin", 0, "--end", a.end, "--seed", a.seed,
         "--additional-files", add, "--tripinfo-output", tripinfo,
         "--fcd-output", fcd, "--fcd-output.geo", "true",
         "--device.emissions.probability", 1, "--no-step-log", "true", "--no-warnings", "true"])

    # 4) trajectoires pour la vue 3D
    n_traj = fcd_to_trajectories(fcd, traj, a.every)

    demanded, routed = count_tags(trips, "trip"), count_tags(rou, "vehicle")
    finished = count_tags(tripinfo, "tripinfo")
    info = {"scenario": s, "demande": prefix, "vehicules_demandes": demanded,
            "sans_itineraire": demanded - routed,          # trajets que duarouter n'a pas pu router
            "trajets_termines": finished,
            "en_route_a_la_fin": routed - finished,        # partis mais pas arrives a t = fin_simulation_s
            "fin_simulation_s": a.end, "seed": a.seed,
            "sumo": subprocess.run(["sumo", "--version"], capture_output=True, text=True).stdout.splitlines()[0]}
    summary.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nScenario '{s}' : {demanded} vehicules demandes ({demanded - routed} sans itineraire), "
          f"{finished} trajets termines, {routed - finished} encore en route a t = {a.end} s, "
          f"{n_traj} trajectoires exportees.")
    print(f"-> {traj}")
    print(f"Etape suivante : python compute_kpi.py --scenario {s}   (conteneur traffic)")


if __name__ == "__main__":
    main()
