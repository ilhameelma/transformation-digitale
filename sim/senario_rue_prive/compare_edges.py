import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]
MIN_SECONDES = 60   # ignorer les rues trop peu mesurées

def lire(fichier):
    d = defaultdict(lambda: {"sec": 0.0, "vit": 0.0, "entrees": 0})
    for _, el in ET.iterparse(fichier, events=("end",)):
        if el.tag == "edge":
            s = float(el.get("sampledSeconds", 0))
            d[el.get("id")]["sec"] += s
            d[el.get("id")]["vit"] += s * float(el.get("speed", 0))
            d[el.get("id")]["entrees"] += int(float(el.get("entered", 0)))
            el.clear()
    res = {}
    for k, v in d.items():
        if v["sec"] > 0:
            res[k] = (v["vit"] / v["sec"] * 3.6, v["entrees"], v["sec"])
    return res

a = lire(sys.argv[1])
b = lire(sys.argv[2])

print("--- Les 8 tronçons de l'axe ---")
print(f"{'tronçon':<14}{'v actuel':>10}{'v réservée':>12}{'entrées act.':>14}{'entrées rés.':>14}")
for e in EDGES:
    if e in a and e in b:
        print(f"{e:<14}{a[e][0]:>9.1f} {b[e][0]:>11.1f} {a[e][1]:>13} {b[e][1]:>13}")
    else:
        print(f"{e:<14} absent d'un des fichiers (aucun véhicule mesuré)")

communs = [e for e in a if e in b and a[e][2] >= MIN_SECONDES and b[e][2] >= MIN_SECONDES]
ecarts = sorted(communs, key=lambda e: b[e][0] - a[e][0])

print("\n--- 8 rues qui ralentissent le plus ---")
for e in ecarts[:8]:
    print(f"{e:<16}{a[e][0]:>7.1f} -> {b[e][0]:>6.1f} km/h | entrées {a[e][1]} -> {b[e][1]}")

print("\n--- 8 rues qui accélèrent le plus ---")
for e in ecarts[-8:][::-1]:
    print(f"{e:<16}{a[e][0]:>7.1f} -> {b[e][0]:>6.1f} km/h | entrées {a[e][1]} -> {b[e][1]}")