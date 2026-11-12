import json
import xml.etree.ElementTree as ET
from collections import defaultdict

paths = defaultdict(list)
for _, el in ET.iterparse("data/fcd.xml", events=("end",)):
    if el.tag == "timestep":
        t = float(el.get("time"))
        for v in el.findall("vehicle"):
            paths[v.get("id")].append([float(v.get("x")), float(v.get("y")), t])
        el.clear()

out = [{"id": k, "path": p} for k, p in paths.items() if len(p) > 1]
with open("data/trajectories_actuel.json", "w") as f:
    json.dump(out, f)
print(len(out), "vehicules exportes")