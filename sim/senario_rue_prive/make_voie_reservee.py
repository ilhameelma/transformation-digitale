import xml.etree.ElementTree as ET
import sumolib

NET_IN = "../hassan.net.xml"
NET_OUT = "hassan_voie_reservee.net.xml"
EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
tree = ET.parse(NET_IN)

trouves = set()
for edge in tree.getroot().findall("edge"):
    if edge.get("id") in EDGES:
        for lane in edge.findall("lane"):
            if lane.get("index") == "0":
                lane.set("allow", "bus")
                lane.attrib.pop("disallow", None)
                trouves.add(edge.get("id"))
                print("voie réservée :", lane.get("id"))

manquants = set(EDGES) - trouves
if manquants:
    raise SystemExit(f"tronçons introuvables : {manquants}")

tree.write(NET_OUT, encoding="utf-8", xml_declaration=True)
print("écrit :", NET_OUT)

# vérification
net = sumolib.net.readNet(NET_OUT)
for eid in EDGES:
    e = net.getEdge(eid)
    l0, l1 = e.getLanes()[0], e.getLanes()[1]
    print(eid, "| voie 0 : voiture", l0.allows("passenger"), "bus", l0.allows("bus"),
          "| voie 1 : voiture", l1.allows("passenger"))