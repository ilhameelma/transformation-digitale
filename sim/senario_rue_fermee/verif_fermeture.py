"""Verification : des voitures roulent-elles sur la rue fermee ?

Lit les positions (fcd) du tirage 1 : runs/actuel_ref/fcd.xml et runs/rue_fermee/fcd.xml.
Compte les voitures dont la voie (attribut lane) appartient a un troncon ferme, et donne l'emprise
de ces troncons (lon/lat) pour la comparer au trait rouge de la carte (data/closure.geojson).
Usage : python verif_fermeture.py
"""
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from common import DATA, RUNS, troncons_fermes, troncons_lonlat

fermes = set(troncons_fermes())


def analyser(nom):
    ids, lignes, pts = set(), 0, []
    for _, el in ET.iterparse(RUNS / nom / "fcd.xml", events=("end",)):
        if el.tag == "timestep":
            for v in el.findall("vehicle"):
                lane = v.get("lane", "")
                if lane.rsplit("_", 1)[0] in fermes:
                    ids.add(v.get("id"))
                    lignes += 1
                    pts.append((float(v.get("x")), float(v.get("y"))))
            el.clear()
    return ids, lignes, pts


def emprise(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return f"lon {min(xs):.5f} a {max(xs):.5f} | lat {min(ys):.5f} a {max(ys):.5f}"


for nom in ("actuel_ref", "rue_fermee"):
    ids, n, pts = analyser(nom)
    print(f"{nom:<11}: {len(ids)} voitures ont roule sur les troncons fermes ({n} positions)")
    if nom == "actuel_ref" and pts:
        print("   emprise des troncons fermes (vue par les voitures) :", emprise(pts))

f = DATA / "closure.geojson"
if f.exists():
    coords = [c for ft in json.loads(f.read_text(encoding="utf-8"))["features"] for c in ft["geometry"]["coordinates"]]
    print("trait rouge de la carte (closure.geojson)           :", emprise(coords))


# --- Voitures tout pres de la rue fermee (scenario rue fermee) : ou sont-elles ?
formes = troncons_lonlat(fermes)
segs = [(a, b) for pts in formes.values() for a, b in zip(pts, pts[1:])]
KX, KY, SEUIL = 111320 * math.cos(math.radians(34.0)), 110540, 12.0
xs = [p[0] for s_ in segs for p in s_]
ys = [p[1] for s_ in segs for p in s_]
marge = 0.0003
boite = (min(xs) - marge, max(xs) + marge, min(ys) - marge, max(ys) + marge)


def dist_m(p, a, b):
    px, py = (p[0] - a[0]) * KX, (p[1] - a[1]) * KY
    bx, by = (b[0] - a[0]) * KX, (b[1] - a[1]) * KY
    L = bx * bx + by * by
    t = 0 if L == 0 else max(0, min(1, (px * bx + py * by) / L))
    return math.hypot(px - t * bx, py - t * by)


par_type, voitures = Counter(), defaultdict(set)
for _, el in ET.iterparse(RUNS / "rue_fermee" / "fcd.xml", events=("end",)):
    if el.tag == "timestep":
        for v in el.findall("vehicle"):
            p = (float(v.get("x")), float(v.get("y")))
            if not (boite[0] <= p[0] <= boite[1] and boite[2] <= p[1] <= boite[3]):
                continue
            if min(dist_m(p, a, b) for a, b in segs) <= SEUIL:
                lane = v.get("lane", "")
                type_ = "dans un carrefour (voie interne)" if lane.startswith(":") else "sur une autre rue (transversale ou voisine)"
                par_type[type_] += 1
                voitures[type_].add(v.get("id"))
        el.clear()
print(f"\nrue_fermee : positions a moins de {SEUIL:.0f} m de la rue fermee, par type de voie :")
if not par_type:
    print("   aucune")
for t_, n in par_type.items():
    print(f"   {t_} : {n} positions, {len(voitures[t_])} voitures")
print("   (sur les troncons fermes eux-memes : 0, voir plus haut)")