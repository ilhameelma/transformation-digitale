import xml.etree.ElementTree as ET

AXE = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"}

def routes(fichier):
    d = {}
    for _, el in ET.iterparse(fichier, events=("end",)):
        if el.tag == "vehicle":
            r = el.find("route")
            if r is not None and r.get("edges"):
                d[el.get("id")] = r.get("edges").split()
            el.clear()
    return d

def trips(fichier):
    d = {}
    for t in ET.parse(fichier).getroot().findall("tripinfo"):
        d[t.get("id")] = (float(t.get("duration")), float(t.get("waitingTime")),
                          float(t.get("timeLoss")))
    return d

avant = routes("../hassan.rou.xml")
apres = routes("../hassan.rou.xml")
tb = trips("tripinfo_voie_reservee_v2.xml")
ta = trips("tripinfo_actuel.xml")

utilisent = [v for v in avant if any(e in AXE for e in avant[v])]
restent = [v for v in utilisent if any(e in AXE for e in apres.get(v, []))]
quittent = [v for v in utilisent if v not in restent]
modifies = [v for v in avant if avant[v] != apres.get(v)]

print(len(utilisent), "voitures utilisaient l'axe (actuel)")
print(len(restent), "l'utilisent encore |", len(quittent), "ne l'utilisent plus")
print(len(modifies), "trajets modifiés au total\n")

def moyenne(ids, t, i):
    return sum(t[v][i] for v in ids) / len(ids)

print(f"{'groupe':<22}{'n':>4}{'durée act.':>12}{'durée rés.':>12}{'attente act.':>14}{'attente rés.':>14}")
for nom, ids in [("restent sur l'axe", restent), ("quittent l'axe", quittent)]:
    communs = [v for v in ids if v in ta and v in tb]
    if communs:
        print(f"{nom:<22}{len(communs):>4}{moyenne(communs, ta, 0):>12.1f}{moyenne(communs, tb, 0):>12.1f}"
              f"{moyenne(communs, ta, 1):>14.1f}{moyenne(communs, tb, 1):>14.1f}")