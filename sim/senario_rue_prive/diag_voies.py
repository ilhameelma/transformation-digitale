import sumolib

NET = "hassan_voie_reservee_v2.net.xml"
PAIRES = [("4330541#18", "1278789351#0"), ("4330541#15", "407005355#1"),
          ("-236715625#4", "4330541#15"), ("4330541#12", "236715625#2")]

net = sumolib.net.readNet(NET)

for a, b in PAIRES:
    ea, eb = net.getEdge(a), net.getEdge(b)
    print(f"\n{a} ({ea.getLaneNumber()} voies) -> {b} ({eb.getLaneNumber()} voies)")
    print("  connexions sortantes de", a, ":")
    for lane in ea.getLanes():
        for c in lane.getOutgoing():
            fl, tl = c.getFromLane(), c.getToLane()
            utilisable = fl.allows("passenger") and tl.allows("passenger")
            cible = c.getTo().getID()
            marque = "" if utilisable else "   <-- inutilisable par les voitures"
            suite = "   (virage concerné)" if cible == b else ""
            print(f"    voie {fl.getIndex()} -> {cible} voie {tl.getIndex()}{marque}{suite}")
    print("  connexions entrantes vers", b, ":")
    for lane in eb.getLanes():
        for c in lane.getIncoming():
            pass