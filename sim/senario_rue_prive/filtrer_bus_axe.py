"""Garde seulement les bus dont la ligne emprunte l'axe 4330541 (pour le scénario voie réservée).
Lit bus_reseau.rou.xml sans le modifier, écrit bus_axe_seul.rou.xml (mêmes identifiants, mêmes heures de départ).
  python filtrer_bus_axe.py                       # toutes les lignes qui touchent l'axe
  python filtrer_bus_axe.py --lignes axe_A        # seulement la ligne qui reste sur l'axe (360 m)"""
import argparse
import xml.etree.ElementTree as ET

AXE = "4330541#3 4330541#7 4330541#9 4330541#10 4330541#11 4330541#12 4330541#15 4330541#18"
p = argparse.ArgumentParser()
p.add_argument("--entree", default="bus_reseau.rou.xml")
p.add_argument("--sortie", default="bus_axe_seul.rou.xml")
p.add_argument("--axe-edges", default=AXE)
p.add_argument("--lignes", nargs="*", default=None, help="identifiants de routes à garder (ex. axe_A), parmi celles qui touchent l'axe")
a = p.parse_args()
axe = set(a.axe_edges.split())

src = ET.parse(a.entree).getroot()
routes = {r.get("id"): r for r in src.findall("route")}
sur_axe = {rid for rid, r in routes.items() if axe & set((r.get("edges") or "").split())}
if a.lignes:
    sur_axe = {r for r in sur_axe if r in set(a.lignes)}
vehs = [v for v in src.findall("vehicle") if v.get("route") in sur_axe]

out = ET.Element("routes")
for vt in src.findall("vType"):
    out.append(vt)
for rid in routes:
    if rid in sur_axe:
        out.append(routes[rid])
for v in vehs:   # l'ordre d'origine (par heure de départ) est conservé
    out.append(v)
ET.indent(out)
ET.ElementTree(out).write(a.sortie, encoding="utf-8", xml_declaration=True)
print(f"{len(vehs)} bus gardés sur {len(src.findall('vehicle'))} (lignes : {', '.join(sorted(sur_axe))}) -> {a.sortie}")