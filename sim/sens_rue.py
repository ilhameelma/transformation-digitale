import json, math
from pathlib import Path

data = Path(__file__).resolve().parent.parent / "data"
feats = json.loads((data / "closure.geojson").read_text(encoding="utf-8"))["features"]

us = {f["properties"]["u"] for f in feats}
vs = {f["properties"]["v"] for f in feats}
start = next(f for f in feats if f["properties"]["u"] not in vs)   # premier tronçon de la chaîne
end = next(f for f in feats if f["properties"]["v"] not in us)     # dernier tronçon

lon1, lat1 = start["geometry"]["coordinates"][0]
lon2, lat2 = end["geometry"]["coordinates"][-1]

dx = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
dy = lat2 - lat1
bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360
points = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"]
cardinal = points[round(bearing / 45) % 8]

print(f"Depart : lat {lat1:.5f}, lon {lon1:.5f}")
print(f"Arrivee : lat {lat2:.5f}, lon {lon2:.5f}")
print(f"Sens de circulation : vers le {cardinal} (cap {bearing:.0f} degres)")