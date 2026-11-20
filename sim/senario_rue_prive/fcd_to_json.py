import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

FCD = sys.argv[1]
NOM = sys.argv[2]
MAX_T = float(sys.argv[3]) if len(sys.argv) > 3 else 900

paths = defaultdict(list)
types = {}
for _, el in ET.iterparse(FCD, events=("end",)):
    if el.tag == "timestep":
        t = float(el.get("time"))
        if t <= MAX_T:
            for v in el.findall("vehicle"):
                vid = v.get("id")
                paths[vid].append([float(v.get("x")), float(v.get("y")), t])
                types[vid] = v.get("type", "car")
        el.clear()

out = [{"id": k, "type": types[k], "path": p} for k, p in paths.items() if len(p) > 1]
sortie = f"runs/trajectories_{NOM}.json"
with open(sortie, "w") as f:
    json.dump(out, f)

xs = [pt[0] for o in out for pt in o["path"]]
ys = [pt[1] for o in out for pt in o["path"]]
print(len(out), "véhicules exportés dans", sortie)
print("types :", dict(Counter(o["type"] for o in out)))
print(f"temps : 0 à {max(pt[2] for o in out for pt in o['path']):.0f} s")
print(f"lon : {min(xs):.5f} à {max(xs):.5f} | lat : {min(ys):.5f} à {max(ys):.5f}")