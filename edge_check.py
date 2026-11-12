import xml.etree.ElementTree as ET
from collections import defaultdict

SEUIL = 0.5  # une rue est "congestionnée" si vitesse < 50 % de la vitesse max

stats = defaultdict(lambda: {"mesures": 0, "congestionne": 0, "vitesses": []})

root = ET.parse("edgedata.xml").getroot()
for interval in root.findall("interval"):
    for e in interval.findall("edge"):
        s = stats[e.get("id")]
        s["mesures"] += 1
        s["vitesses"].append(float(e.get("speed")) * 3.6)
        rel = e.get("speedRelative")
        if rel is not None and float(rel) < SEUIL:
            s["congestionne"] += 1

print(f"{len(stats)} rues mesurées")
print(f"{'rue':<10}{'vitesse moy (km/h)':>20}{'taux congestion':>18}")
pires = sorted(stats.items(), key=lambda kv: kv[1]["congestionne"] / kv[1]["mesures"], reverse=True)
for rue, s in pires[:10]:
    v = sum(s["vitesses"]) / len(s["vitesses"])
    taux = s["congestionne"] / s["mesures"]
    print(f"{rue:<10}{v:>20.1f}{taux:>17.0%}")