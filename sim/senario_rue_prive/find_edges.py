import sumolib

net = sumolib.net.readNet("hassan_net.xml")
rues = [e for e in net.getEdges()
        if e.getLaneNumber() >= 2 and e.allows("passenger")]
rues.sort(key=lambda e: e.getLength(), reverse=True)

print(len(rues), "rues avec 2 voies ou plus")
for e in rues[:20]:
    print(e.getID(), "|", e.getName(), "|", e.getLaneNumber(), "voies |", round(e.getLength()), "m")