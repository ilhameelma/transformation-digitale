"""
run_scenario.py - M4 : lance un scenario complet et calcule ses 4 indicateurs.

Scenarios :
  actuel       demande normale, toutes les rues ouvertes
  rue_fermee   meme demande, section de data/closure_sumo.json interdite a la circulation
  pic          demande x1,3 (+30 %), toutes les rues ouvertes

Etapes : demande -> (reseau modifie si rue fermee) -> duarouter -> sumo -> compute_kpi.py
La MEME graine et les MEMES rues d'origine/destination (hors rue fermee) sont utilisees
pour les 3 scenarios, afin que la comparaison ne mesure que l'effet du scenario.

Sorties dans data/ : demand_<s>.csv, <s>.rou.xml, tripinfo_<s>.xml, edgedata_<s>.xml,
                     fcd_<s>.xml, kpi_<s>.json, trajectories_<s>.json (pour la carte)  (+ hassan_rue_fermee.net.xml)

Usage : python run_scenario.py rue_fermee      (ou actuel, pic, all)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.getenv("DATA_DIR") or HERE.parent / "data")
NET = DATA / "hassan.net.xml"
SCALE = {"actuel": 1.0, "rue_fermee": 1.0, "pic": 1.3}
SIM_END = 900  # meme duree que sim/hassan.sumocfg


def run(cmd):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode != 0:
        sys.exit(f"ECHEC (code {r.returncode}) : {cmd[0]}")


def close_edges(net_in, net_out, edges):
    """Copie le reseau en interdisant toutes les voies des rues fermees (disallow=all)."""
    closed, text = set(edges), net_in.read_text(encoding="utf-8")
    count = 0

    def patch(m):
        nonlocal count
        tag = m.group(0)
        if m.group(1) in closed:
            tag = re.sub(r'\s(allow|disallow)="[^"]*"', "", tag)
            count += 1
            return tag.replace("<lane", '<lane disallow="all"', 1)
        return tag

    text = re.sub(r'<lane id="(.+?)_\d+"[^>]*>', patch, text)
    if count == 0:
        sys.exit("Aucune voie fermee : les ids de closure_sumo.json ne sont pas dans le reseau.")
    net_out.write_text(text, encoding="utf-8")
    print(f"{count} voies fermees sur {len(closed)} rues -> {net_out.name}")


def scenario(name):
    print(f"\n===== Scenario : {name} =====")
    csv_out = DATA / f"demand_{name}.csv"
    run([sys.executable, HERE / "generate_demand.py", "--scale", SCALE[name],
         "--exclude-closure", "--out", csv_out])
    trips = csv_out.with_suffix(".trips.xml")

    net = NET
    if name == "rue_fermee":
        closure = json.loads((DATA / "closure_sumo.json").read_text(encoding="utf-8"))
        net = DATA / "hassan_rue_fermee.net.xml"
        close_edges(NET, net, closure["edges"])

    rou = DATA / f"{name}.rou.xml"
    run(["duarouter", "-n", net, "--route-files", trips, "-o", rou,
         "--ignore-errors", "--no-warnings", "--no-step-log"])

    add = DATA / f"additional_{name}.xml"
    add.write_text(f'<additional>\n  <edgeData id="edges" file="{DATA / f"edgedata_{name}.xml"}" '
                   f'period="60" excludeEmpty="true"/>\n</additional>\n', encoding="utf-8")
    run(["sumo", "-n", net, "-r", rou, "--additional-files", add,
         "--begin", 0, "--end", SIM_END,
         "--tripinfo-output", DATA / f"tripinfo_{name}.xml",
         "--fcd-output", DATA / f"fcd_{name}.xml", "--fcd-output.geo", "true",
         "--device.emissions.probability", 1, "--no-step-log", "--no-warnings"])

    run([sys.executable, HERE / "compute_kpi.py", "--scenario", name])
    run([sys.executable, HERE / "fcd_to_json.py", name])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=[*SCALE, "all"])
    a = ap.parse_args()
    for s in (SCALE if a.scenario == "all" else [a.scenario]):
        scenario(s)