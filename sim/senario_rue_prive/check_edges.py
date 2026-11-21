import sumolib

NET = "../hassan.net.xml"
EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

net = sumolib.net.readNet(NET)
total = 0
for eid in EDGES:
    e = net.getEdge(eid)
    nb_total = e.getLaneNumber()
    nb_voiture = sum(1 for l in e.getLanes() if l.allows("passenger"))
    total += e.getLength()
    suivants = [s.getID() for s in e.getOutgoing()]
    print(eid, "|", nb_total, "voies |", nb_voiture, "pour voitures |",
          round(e.getLength()), "m |", e.getFromNode().getID(), "->", e.getToNode().getID())
    print("    suivants :", suivants)
print("longueur totale :", round(total, 1), "m")