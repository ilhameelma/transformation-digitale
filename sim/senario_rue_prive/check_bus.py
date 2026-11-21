import sumolib

NET = "hassan_voie_reservee_v3.net.xml"
EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

net = sumolib.net.readNet(NET)
ok = True
for a, b in zip(EDGES, EDGES[1:]):
    ea, eb = net.getEdge(a), net.getEdge(b)
    liens = [(c.getFromLane().getIndex(), c.getToLane().getIndex())
             for lane in ea.getLanes() for c in lane.getOutgoing()
             if c.getTo().getID() == b and c.getFromLane().allows("bus") and c.getToLane().allows("bus")]
    print(f"{a} -> {b} : liaisons utilisables par un bus {liens}")
    if not liens:
        ok = False
print("\nligne de bus continue :", ok)
print("longueur :", round(sum(net.getEdge(e).getLength() for e in EDGES), 1), "m")