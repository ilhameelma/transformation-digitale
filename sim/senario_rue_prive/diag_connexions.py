import sys
import xml.etree.ElementTree as ET
from collections import Counter
import sumolib

NET = sys.argv[1]
ROU = sys.argv[2] if len(sys.argv) > 2 else "../hassan.rou.xml"

net = sumolib.net.readNet(NET)
cache = {}

def utilisable(a, b):
    cle = (a, b)
    if cle not in cache:
        conns = net.getEdge(a).getConnections(net.getEdge(b))
        cache[cle] = any(c.getFromLane().allows("passenger") and
                         c.getToLane().allows("passenger") for c in conns)
    return cache[cle]

casses = Counter()
voitures_touchees = set()
total = 0
for _, el in ET.iterparse(ROU, events=("end",)):
    if el.tag == "vehicle":
        total += 1
        route = el.find("route")
        if route is not None and route.get("edges"):
            edges = route.get("edges").split()
            for a, b in zip(edges, edges[1:]):
                if not utilisable(a, b):
                    casses[(a, b)] += 1
                    voitures_touchees.add(el.get("id"))
        el.clear()

print(total, "véhicules dans le fichier")
print(len(casses), "virages impossibles |", len(voitures_touchees), "voitures touchées")
for (a, b), n in casses.most_common(15):
    print(a, "->", b, "|", n, "voitures")