"""Etape 5 : indicateur propre a la rue (equivalent de kpi_axe.py), tirage 1.

Duree moyenne des voitures dont l'itineraire passait par la rue fermee, comparee sur les MEMES voitures
(terminees dans les deux scenarios). Ecrit : runs/kpi_axe.json
"""
import json

from common import HERE, RUNS, ids_sur_axe, tripinfos, troncons_fermes

axe = ids_sur_axe(troncons_fermes())
a = tripinfos(RUNS / "actuel_ref" / "tripinfo.xml")
f = tripinfos(RUNS / "rue_fermee" / "tripinfo.xml")
dem = json.loads((RUNS / "rue_fermee_demande.json").read_text(encoding="utf-8"))
communs = sorted(v for v in axe if v in a and v in f)


def moy(d):
    return round(sum(d[v][0] for v in communs) / len(communs), 1) if communs else None


out = {"ids_concernees": dem.get("ids_concernees", sorted(axe)), "voitures_axe": len(axe), "sans_itineraire": dem["sans_itineraire"], "deviees": dem["deviees"],
       "comparables": len(communs), "actuel_ref": {"n": len(communs), "duree_moyenne_s": moy(a)},
       "rue_fermee": {"n": len(communs), "duree_moyenne_s": moy(f)}}
(RUNS / "kpi_axe.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(axe)} voitures sur la rue ; {len(communs)} terminees dans les deux scenarios (tirage 1)")
print("actuel_ref", out["actuel_ref"], "| rue_fermee", out["rue_fermee"])
print("-> runs/kpi_axe.json")