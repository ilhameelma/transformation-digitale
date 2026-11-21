"""Même rôle que prepare_kpi.py, pour le réseau de bus complet. N'écrase pas prepare_kpi.py.
- tripinfo sans les bus (pour compute_kpi.py, voitures seulement) + edgedata + kpi_bus.json
- "bus de l'axe" = bus dont la ligne emprunte au moins un tronçon de l'axe 4330541
- les temps des bus sont comparés sur les MÊMES bus, terminés dans les deux scénarios
À lancer dans sim/senario_rue_prive."""
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

BUS_ROU = "bus_reseau.rou.xml"
AXE = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"}
SCEN = {"actuel_bus": ("runs/ref_tripinfo.xml", "runs/ref_edgedata.xml"),
        "voie_reservee": ("runs/demo_tripinfo.xml", "runs/demo_edgedata.xml")}

# Bus de l'axe, d'après les itinéraires du fichier de bus
racine = ET.parse(BUS_ROU).getroot()
routes = {r.get("id"): set((r.get("edges") or "").split()) for r in racine.findall("route")}
tous_bus = [v.get("id") for v in racine.findall("vehicle")]
bus_axe = {v.get("id") for v in racine.findall("vehicle") if routes.get(v.get("route"), set()) & AXE}
print(f"{len(tous_bus)} bus prévus, dont {len(bus_axe)} passent par l'axe")

# Lecture des deux scénarios : on retire les bus du tripinfo
lu = {}
for nom, (trip, _) in SCEN.items():
    tree = ET.parse(trip)
    root = tree.getroot()
    bus = {}
    for t in list(root.findall("tripinfo")):
        if t.get("vType") == "bus":
            bus[t.get("id")] = t
            root.remove(t)
    lu[nom] = (tree, bus)

commun = set.intersection(*(set(b) for _, b in lu.values()))
print(f"{len(commun)} bus terminés dans les DEUX scénarios, {len(tous_bus) - len(commun)} non comparables (non terminés dans l'un des deux)")

def stats(bus, ids):
    ids = [i for i in ids if i in bus]
    if not ids:
        return {"n": 0, "duree": None, "attente": None}
    return {"n": len(ids),
            "duree": round(sum(float(bus[i].get("duration")) for i in ids) / len(ids), 1),
            "attente": round(sum(float(bus[i].get("waitingTime")) for i in ids) / len(ids), 1)}

for nom, (trip, edge) in SCEN.items():
    tree, bus = lu[nom]
    dossier = Path("runs") / f"kpi_{nom}"
    dossier.mkdir(exist_ok=True)
    tree.write(dossier / "tripinfo.xml", encoding="utf-8", xml_declaration=True)
    shutil.copy(edge, dossier / "edgedata.xml")
    tout = stats(bus, commun)
    axe = stats(bus, commun & bus_axe)
    kpi = {"bus_termines": tout["n"], "duree_moyenne_s": tout["duree"], "attente_moyenne_s": tout["attente"],
           "axe_bus_termines": axe["n"], "axe_duree_moyenne_s": axe["duree"], "axe_attente_moyenne_s": axe["attente"],
           "bus_non_comparables": len(tous_bus) - len(commun)}
    (dossier / "kpi_bus.json").write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    print(nom, "|", len(tree.getroot().findall("tripinfo")), "voitures |", kpi)