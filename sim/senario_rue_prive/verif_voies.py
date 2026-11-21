"""Vérifie sur quelles voies de l'axe 4330541 roulent les bus et les voitures (d'après fcd.xml).
  python verif_voies.py runs/ref_fcd.xml
  python verif_voies.py runs/demo_fcd.xml
Voie 0 = voie réservée aux bus dans le scénario. Attendu dans demo : 0 bus sur la voie 1, 0 voiture sur la voie 0."""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

AXE = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"}
c = Counter()
for _, el in ET.iterparse(sys.argv[1], events=("end",)):
    if el.tag == "timestep":
        for v in el.findall("vehicle"):
            lane = v.get("lane") or ""
            edge, _, num = lane.rpartition("_")
            if edge in AXE:
                genre = "bus" if v.get("type") == "bus" else "voiture"
                c[(genre, num)] += 1
        el.clear()
for genre in ("bus", "voiture"):
    print(f"{genre:8s} voie 0 : {c[(genre, '0')]:>7} instants   voie 1 : {c[(genre, '1')]:>7} instants")