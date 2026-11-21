import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
import sumolib

NET = "../hassan.net.xml"
ROU = sys.argv[1]
LONGUEUR_MIN = 100   # mètres, longueur totale de la rue

def cle_rue(edge_id):
    sens = "inverse" if edge_id.startswith("-") else "normal"
    base = edge_id.lstrip("-").split("#")[0]
    return (base, sens)

# 1. nombre de voitures par rue entière
voitures = Counter()
for _, el in ET.iterparse(ROU, events=("end",)):
    if el.tag == "route" and el.get("edges"):
        rues = {cle_rue(e) for e in el.get("edges").split()}
        for r in rues:
            voitures[r] += 1
    el.clear()

# 2. tronçons à 2 voies voiture ou plus, regroupés par rue
net = sumolib.net.readNet(NET)
troncons = defaultdict(list)
for e in net.getEdges():
    if sum(1 for l in e.getLanes() if l.allows("passenger")) >= 2:
        troncons[cle_rue(e.getID())].append(e)

resultats = []
for cle, edges in troncons.items():
    longueur = sum(e.getLength() for e in edges)
    if longueur >= LONGUEUR_MIN:
        resultats.append((voitures[cle], cle, edges, longueur))

resultats.sort(key=lambda x: x[0], reverse=True)

print("rue | sens | voitures | tronçons | longueur totale")
for n, (base, sens), edges, longueur in resultats[:15]:
    print(base, "|", sens, "|", n, "voitures |", len(edges), "tronçons |", round(longueur), "m")