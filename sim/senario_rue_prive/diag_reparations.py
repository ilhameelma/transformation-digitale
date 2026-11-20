import xml.etree.ElementTree as ET
import sumolib

AXE = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"}
net = sumolib.net.readNet("hassan_voie_reservee.net.xml")

def lire(fichier):
    d = {}
    for _, el in ET.iterparse(fichier, events=("end",)):
        if el.tag == "vehicle":
            r = el.find("route")
            if r is not None and r.get("edges"):
                d[el.get("id")] = r.get("edges").split()
            el.clear()
    return d

def metres(route):
    return sum(net.getEdge(e).getLength() for e in route)

avant = lire("../hassan.rou.xml")
apres = lire("voie_reservee.rou.xml")
changes = [v for v in avant if v in apres and avant[v] != apres[v]]

print(len(changes), "trajets modifiés sur", len(avant))
print(f"{'véhicule':<10}{'axe avant':>10}{'axe après':>11}{'m avant':>9}{'m après':>9}")
for v in changes:
    a = sum(1 for e in avant[v] if e in AXE)
    b = sum(1 for e in apres[v] if e in AXE)
    print(f"{v:<10}{a:>10}{b:>11}{metres(avant[v]):>9.0f}{metres(apres[v]):>9.0f}")

tout_a = sum(1 for v in avant for e in avant[v] if e in AXE)
tout_b = sum(1 for v in apres for e in apres[v] if e in AXE)
vu_a = sum(1 for v in avant if any(e in AXE for e in avant[v]))
vu_b = sum(1 for v in apres if any(e in AXE for e in apres[v]))
print("\npassages sur l'axe (tous véhicules) :", tout_a, "->", tout_b)
print("véhicules utilisant l'axe :", vu_a, "->", vu_b)
print("détour moyen des trajets modifiés :",
      round(sum(metres(apres[v]) - metres(avant[v]) for v in changes) / len(changes)), "m")