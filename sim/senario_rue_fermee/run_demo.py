"""Etape 4 : tirage 1 detaille, pour l'animation et les 4 indicateurs (900 s, comme hassan.sumocfg).

Ecrit, pour chaque scenario (actuel_ref, rue_fermee) :
  runs/<nom>/tripinfo.xml, edgedata.xml (par minute), fcd.xml (lon/lat)
  runs/trajectories_<nom>.json   (format de data/trajectories_*.json)
"""
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

from common import NET_FERME, NET_REF, ROU_FERME, ROU_REF, RUNS, exiger, lance_sumo

SEED, FIN = 1, 900
SCENARIOS = {"actuel_ref": (NET_REF, ROU_REF), "rue_fermee": (NET_FERME, ROU_FERME)}


def fcd_vers_json(fcd, sortie, tmax):
    paths, types = defaultdict(list), {}
    for _, el in ET.iterparse(fcd, events=("end",)):
        if el.tag == "timestep":
            t = float(el.get("time"))
            if t <= tmax:
                for v in el.findall("vehicle"):
                    paths[v.get("id")].append([round(float(v.get("x")), 6), round(float(v.get("y")), 6), t])
                    types[v.get("id")] = v.get("type", "car")
            el.clear()
    out = [{"id": k, "type": types[k], "path": p} for k, p in paths.items() if len(p) > 1]
    sortie.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return len(out)


def main():
    exiger("sumo")
    if not (NET_FERME.exists() and ROU_FERME.exists()):
        sys.exit("Lancer d'abord make_rue_fermee.py puis make_demande_fermee.py")
    for nom, (net, rou) in SCENARIOS.items():
        d = RUNS / nom
        d.mkdir(parents=True, exist_ok=True)
        add = d / "additional.xml"
        add.write_text(f'<additional>\n  <edgeData id="edges" file="{d / "edgedata.xml"}" period="60" excludeEmpty="true"/>\n</additional>\n',
                       encoding="utf-8")
        lance_sumo(net, rou, FIN, SEED, d / "tripinfo.xml",
                   extra=["--additional-files", add, "--fcd-output", d / "fcd.xml", "--fcd-output.geo", "true"])
        n = fcd_vers_json(d / "fcd.xml", RUNS / f"trajectories_{nom}.json", FIN)
        print(f"{nom} : {n} vehicules exportes -> runs/trajectories_{nom}.json")


if __name__ == "__main__":
    main()
