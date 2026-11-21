"""KPI de l'axe 4330541 (tirage 1) : durée moyenne des voitures qui l'empruntent.
À lancer dans sim/senario_rue_prive. Ne modifie aucun fichier existant."""
import json
import xml.etree.ElementTree as ET

ROU = "../hassan.rou.xml"  # demande de référence (jamais modifiée)
TRONCONS = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
            "4330541#11", "4330541#12", "4330541#15", "4330541#18"}
SCENARIOS = {
    "actuel_bus": "runs/kpi_actuel_bus/tripinfo.xml",
    "voie_reservee": "runs/kpi_voie_reservee/tripinfo.xml",
}

# 1. Voitures dont l'itinéraire passe par au moins un tronçon de l'axe
sur_axe = set()
for veh in ET.parse(ROU).getroot().iter("vehicle"):
    edges = []
    for route in veh.iter("route"):
        edges += (route.get("edges") or "").split()
    if TRONCONS & set(edges):
        sur_axe.add(veh.get("id"))
print(f"{len(sur_axe)} voitures sur l'axe (attendu : 37)")

# 2. Durée moyenne de ces voitures dans chaque scénario
out = {}
for nom, chemin in SCENARIOS.items():
    durees = [float(t.get("duration")) for t in ET.parse(chemin).getroot().findall("tripinfo")
              if t.get("id") in sur_axe]
    out[nom] = {"n": len(durees), "duree_moyenne_s": round(sum(durees) / len(durees), 1)}
    print(nom, out[nom])

with open("runs/kpi_axe.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("-> runs/kpi_axe.json")