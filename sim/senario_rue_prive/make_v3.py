import xml.etree.ElementTree as ET
import sumolib

NET_IN = "hassan_voie_reservee_v2.net.xml"
NET_OUT = "hassan_voie_reservee_v3.net.xml"
EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
tree = ET.parse(NET_IN)

n = 0
for edge in tree.getroot().findall("edge"):
    if edge.get("id") in EDGES:
        for lane in edge.findall("lane"):
            if lane.get("index") == "1":
                allow = lane.get("allow")
                if allow is not None:
                    lane.set("allow", " ".join(c for c in allow.split() if c != "bus"))
                else:
                    dis = lane.get("disallow", "").split()
                    if "bus" not in dis:
                        dis.append("bus")
                    lane.set("disallow", " ".join(dis))
                n += 1
print(n, "voies publiques modifiées (attendu : 8)")
tree.write(NET_OUT, encoding="utf-8", xml_declaration=True)

v2 = sumolib.net.readNet(NET_IN)
v3 = sumolib.net.readNet(NET_OUT)
diff = []
for e in v2.getEdges():
    for l in e.getLanes():
        l3 = v3.getLane(l.getID())
        if set(l.getPermissions()) != set(l3.getPermissions()):
            diff.append(l.getID())
print("voies dont les permissions changent :", len(diff), diff)

for eid in EDGES:
    l0, l1 = v3.getEdge(eid).getLanes()[:2]
    print(eid, "| voie 0 : bus", l0.allows("bus"), "voiture", l0.allows("passenger"),
          "| voie 1 : bus", l1.allows("bus"), "voiture", l1.allows("passenger"))