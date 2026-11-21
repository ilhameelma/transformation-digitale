import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

SCEN = {"actuel_bus": ("runs/ref_tripinfo.xml", "runs/ref_edgedata.xml"),
        "voie_reservee": ("runs/demo_tripinfo.xml", "runs/demo_edgedata.xml")}

for nom, (trip, edge) in SCEN.items():
    dossier = Path("runs") / f"kpi_{nom}"
    dossier.mkdir(exist_ok=True)
    tree = ET.parse(trip)
    root = tree.getroot()
    bus = []
    for t in list(root.findall("tripinfo")):
        if t.get("vType") == "bus":
            bus.append(t)
            root.remove(t)
    tree.write(dossier / "tripinfo.xml", encoding="utf-8", xml_declaration=True)
    shutil.copy(edge, dossier / "edgedata.xml")

    stats = {"bus_termines": len(bus),
             "duree_moyenne_s": round(sum(float(t.get("duration")) for t in bus) / len(bus), 1),
             "attente_moyenne_s": round(sum(float(t.get("waitingTime")) for t in bus) / len(bus), 1)}
    (dossier / "kpi_bus.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(nom, "|", len(root.findall("tripinfo")), "voitures |", stats)