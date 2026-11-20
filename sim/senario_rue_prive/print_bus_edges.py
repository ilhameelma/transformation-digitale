import xml.etree.ElementTree as ET

NB_BUS = 5
EDGES = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
         "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

d = {}
for _, el in ET.iterparse("runs/edgedata_bus_test.xml", events=("end",)):
    if el.tag == "edge":
        d[el.get("id")] = el.attrib
        el.clear()

print(f"{'tronçon':<14}{'temps/bus (s)':>14}{'attente/bus (s)':>17}{'bus entrés':>12}")
tot_t = tot_w = 0
for e in EDGES:
    a = d.get(e)
    if a is None:
        print(f"{e:<14} aucun bus mesuré")
        continue
    t = float(a.get("sampledSeconds", 0)) / NB_BUS
    w = float(a.get("waitingTime", 0)) / NB_BUS
    tot_t += t
    tot_w += w
    print(f"{e:<14}{t:>14.1f}{w:>17.1f}{a.get('entered', '?'):>12}")
print(f"{'total':<14}{tot_t:>14.1f}{tot_w:>17.1f}")