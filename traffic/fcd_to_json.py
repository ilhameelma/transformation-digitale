"""
fcd_to_json.py - M4 : prepare les trajets d'un scenario pour la carte 3D (viz/).

Lit    : data/fcd_<scenario>.xml
Ecrit  : data/trajectories_<scenario>.json   [{id, path:[[lon, lat, t], ...]}, ...]

Usage : python fcd_to_json.py rue_fermee      (ou actuel, pic, all)
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

DATA = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
SCENARIOS = ["actuel", "rue_fermee", "pic"]


def convert(name):
    src = DATA / f"fcd_{name}.xml"
    if not src.exists():
        sys.exit(f"{src.name} introuvable : lance d'abord run_scenario.py {name}")
    paths = defaultdict(list)
    for _, el in ET.iterparse(src, events=("end",)):
        if el.tag == "timestep":
            t = float(el.get("time"))
            for v in el.findall("vehicle"):
                paths[v.get("id")].append([float(v.get("x")), float(v.get("y")), t])
            el.clear()
    out = [{"id": k, "path": p} for k, p in paths.items() if len(p) > 1]
    dst = DATA / f"trajectories_{name}.json"
    dst.write_text(json.dumps(out), encoding="utf-8")
    print(f"{name} : {len(out)} vehicules -> {dst.name}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    for s in (SCENARIOS if arg == "all" else [arg]):
        convert(s)