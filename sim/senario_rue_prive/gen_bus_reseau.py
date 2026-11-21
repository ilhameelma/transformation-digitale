"""Variante : réseau de bus sur toute la zone (plusieurs lignes aller-retour).
À lancer dans sim/senario_rue_prive. Ne modifie aucun fichier existant : écrit un nouveau fichier.

  python gen_bus_reseau.py --seed 1          # tirage 1 (décalage des départs différent à chaque seed)
"""
import argparse
import random
import xml.etree.ElementTree as ET

import sumolib

AXE_PAR_DEFAUT = "4330541#3 4330541#7 4330541#9 4330541#10 4330541#11 4330541#12 4330541#15 4330541#18"

p = argparse.ArgumentParser()
p.add_argument("--net", default="../hassan.net.xml", help="réseau de référence (lu seulement)")
p.add_argument("--old-bus", default="bus.rou.xml", help="ancien fichier de bus (pour reprendre le vType)")
p.add_argument("--out", default="bus_reseau.rou.xml")
p.add_argument("--interval", type=int, default=300, help="un bus toutes les N s, par ligne et par sens")
p.add_argument("--end", type=int, default=1500)
p.add_argument("--lignes", type=int, default=4, help="nombre de lignes traversant la zone (1 à 5), en plus de la ligne de l'axe")
p.add_argument("--seed", type=int, default=None, help="tirage : change le décalage de départ de chaque ligne")
p.add_argument("--par-axe", type=int, default=2, help="nombre de lignes (parmi les premières) forcées à passer par l'axe, pour mesurer le gain de la voie réservée")
p.add_argument("--min-longueur", type=float, default=800.0, help="longueur minimale d'une ligne (m)")
p.add_argument("--axe-edges", default=AXE_PAR_DEFAUT)
a = p.parse_args()

AXE = a.axe_edges.split()
rng = random.Random(a.seed)
net = sumolib.net.readNet(a.net)

def route_bus(e_from, e_to):
    chemin, _ = net.getShortestPath(e_from, e_to, vClass="bus")
    return [e.getID() for e in chemin] if chemin else None

def longueur(ids):
    return sum(net.getEdge(i).getLength() for i in ids)

# 1. vType : repris de l'ancien fichier de bus s'il existe, sinon valeur par défaut
vtype_xml = '<vType id="bus" vClass="bus" length="12" maxSpeed="14" guiShape="bus" color="1,0.6,0"/>'
try:
    vt = ET.parse(a.old_bus).getroot().find("vType")
    if vt is not None:
        vtype_xml = ET.tostring(vt, encoding="unicode").strip()
except (OSError, ET.ParseError):
    print(f"(!) {a.old_bus} introuvable ou illisible : vType par défaut utilisé")
vtype_id = ET.fromstring(vtype_xml).get("id")
if vtype_id != "bus":
    print(f"(!) vType id = '{vtype_id}' : la vue 3D colore les bus quand type == 'bus'. Renomme-le en 'bus'.")

# 2. Ligne 0 = l'axe (comme avant) ; aller et retour si possible
lignes = []
axe_route = route_bus(net.getEdge(AXE[0]), net.getEdge(AXE[-1]))
if axe_route is None or not set(AXE) <= set(axe_route):
    print("(!) Le plus court chemin pour bus entre le 1er et le dernier tronçon ne contient pas les 8 tronçons de l'axe :")
    print("    la ligne de l'axe est construite directement avec la liste des tronçons.")
    axe_route = AXE
lignes.append(("axe", [axe_route]))

# 3. Lignes qui traversent la zone : terminus choisis près de points répartis dans la zone
xmin, ymin, xmax, ymax = net.getBoundary()
w, h = xmax - xmin, ymax - ymin
def pt(fx, fy):
    return (xmin + fx * w, ymin + fy * h)
PAIRES = [  # (départ, arrivée) en fractions de la boîte englobante
    ((0.12, 0.88), (0.88, 0.12)),  # nord-ouest -> sud-est
    ((0.88, 0.88), (0.12, 0.12)),  # nord-est -> sud-ouest
    ((0.50, 0.92), (0.50, 0.08)),  # nord -> sud
    ((0.08, 0.50), (0.92, 0.50)),  # ouest -> est
    ((0.30, 0.10), (0.70, 0.90)),
]
candidats = [e for e in net.getEdges()
             if e.allows("bus") and e.getLength() >= 40 and e.getSpeed() >= 8.3]
def centre(e):
    s = e.getShape()
    return s[len(s) // 2]
def proches(point, n=6):
    return sorted(candidats, key=lambda e: (centre(e)[0] - point[0]) ** 2 + (centre(e)[1] - point[1]) ** 2)[:n]

for k, (d, f) in enumerate(PAIRES[:a.lignes], start=1):
    trouve = None
    for e1 in proches(pt(*d)):
        for e2 in proches(pt(*f)):
            if e1 is e2:
                continue
            if k <= a.par_axe:  # ligne qui emprunte l'axe : terminus 1 -> axe -> terminus 2
                p1 = route_bus(e1, net.getEdge(AXE[0]))
                p2 = route_bus(net.getEdge(AXE[-1]), e2)
                aller = (p1[:-1] + axe_route + p2[1:]) if (p1 and p2) else None
            else:
                aller = route_bus(e1, e2)
            if aller and longueur(aller) >= a.min_longueur and len(set(aller)) == len(aller):
                retour = route_bus(e2, e1)
                trouve = [aller] + ([retour] if retour else [])
                break
        if trouve:
            break
    if trouve:
        lignes.append((f"L{k}", trouve))
    else:
        print(f"(!) ligne L{k} : aucun itinéraire bus d'au moins {a.min_longueur:.0f} m trouvé entre ces deux zones")

# 4. Écriture : routes, puis véhicules triés par heure de départ (obligatoire dans SUMO)
vehicules = []
for nom, routes in lignes:
    decalage = rng.uniform(0, a.interval) if a.seed is not None else 0
    for s_idx, rid in enumerate(range(len(routes))):
        t = decalage + s_idx * a.interval / 2  # le sens retour part à mi-intervalle
        n = 0
        while t < a.end:
            vehicules.append((t, f"bus_{nom}_{'AR'[s_idx]}{n}", f"{nom}_{'AR'[s_idx]}"))
            t += a.interval
            n += 1
vehicules.sort()

with open(a.out, "w", encoding="utf-8") as f:
    f.write("<routes>\n  " + vtype_xml + "\n")
    for nom, routes in lignes:
        for s_idx, r in enumerate(routes):
            f.write(f'  <route id="{nom}_{"AR"[s_idx]}" edges="{" ".join(r)}"/>\n')
    for t, vid, rid in vehicules:
        f.write(f'  <vehicle id="{vid}" type="{vtype_id}" route="{rid}" depart="{t:.1f}"/>\n')
    f.write("</routes>\n")

print(f"\n{a.out} : {len(vehicules)} bus sur {len(lignes)} lignes (tirage {a.seed})")
for nom, routes in lignes:
    for s_idx, r in enumerate(routes):
        sur_axe = len(set(r) & set(AXE))
        if len(set(r)) < len(r):
            print(f"  (!) {nom}_{'AR'[s_idx]} repasse par le même tronçon : choisis d'autres terminus ou change --lignes")
        print(f"  {nom}_{'AR'[s_idx]} : {len(r):>3} tronçons, {longueur(r):>6.0f} m, passe par {sur_axe}/8 tronçons de l'axe")