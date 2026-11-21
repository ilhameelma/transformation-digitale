"""Convertit un fcd.xml (avec --fcd-output.geo true) en JSON pour la vue 3D.
Garde le type du véhicule (car / bus) pour colorer les bus à part. Ne modifie aucun fichier existant.

  python fcd_to_json_reseau.py runs/ref_fcd.xml  runs/trajectories_actuel_bus.json
  python fcd_to_json_reseau.py runs/demo_fcd.xml runs/trajectories_voie_reservee.json
"""
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

if len(sys.argv) != 3:
    sys.exit("usage : python fcd_to_json_reseau.py ENTREE_fcd.xml SORTIE.json")
entree, sortie = sys.argv[1], sys.argv[2]

chemins = defaultdict(list)
types = {}
for _, el in ET.iterparse(entree, events=("end",)):
    if el.tag == "timestep":
        t = float(el.get("time"))
        for v in el.findall("vehicle"):
            vid = v.get("id")
            types[vid] = v.get("type", "car")
            chemins[vid].append([float(v.get("x")), float(v.get("y")), t])
        el.clear()

out = [{"id": k, "type": types[k], "path": p} for k, p in chemins.items() if len(p) > 1]
with open(sortie, "w", encoding="utf-8") as f:
    json.dump(out, f)
n_bus = sum(1 for v in out if v["type"] == "bus")
print(f"{len(out)} véhicules exportés ({n_bus} bus) -> {sortie}")