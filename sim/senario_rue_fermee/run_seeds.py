"""Etape 3 : 10 tirages (equivalent de run_seeds.py de senario_rue_prive).

Pour chaque graine, meme demande de reference, deux reseaux : actuel / rue fermee.
Comparaison sur les voitures de la rue (celles dont l'itineraire passait par la rue fermee), terminees dans
les deux scenarios. Une seule graine peut tromper : la conclusion se lit sur les 10.

Ecrit : runs/resume_10_tirages.json
"""
import json
import statistics
import sys

from common import (NET_FERME, NET_REF, ROU_FERME, ROU_REF, RUNS, exiger, ids_sur_axe, lance_sumo,
                    tripinfos, troncons_fermes)

SEEDS = range(1, 11)
FIN = 1500          # laisse le temps aux vehicules de finir (comme run_seeds.py de la voie reservee)


def moy(d, ids, i):
    return sum(d[v][i] for v in ids) / len(ids) if ids else float("nan")


def main():
    exiger("sumo")
    if not (NET_FERME.exists() and ROU_FERME.exists()):
        sys.exit("Lancer d'abord make_rue_fermee.py puis make_demande_fermee.py")
    RUNS.mkdir(exist_ok=True)
    axe = ids_sur_axe(troncons_fermes())
    print(f"{len(axe)} voitures de la demande passent par la rue fermee")
    print(f"{'seed':<5}{'finis a/f':>10}{'axe n':>7}{'durée act.':>12}{'durée fer.':>12}{'écart':>8}{'écart tous':>12}")

    tirages = []
    for s in SEEDS:
        sa, sf = RUNS / f"tripinfo_actuel_{s}.xml", RUNS / f"tripinfo_fermee_{s}.xml"
        lance_sumo(NET_REF, ROU_REF, FIN, s, sa)
        lance_sumo(NET_FERME, ROU_FERME, FIN, s, sf)
        a, f = tripinfos(sa), tripinfos(sf)
        communs_axe = [v for v in axe if v in a and v in f]
        communs = [v for v in a if v in f]
        ecart = moy(f, communs_axe, 0) - moy(a, communs_axe, 0)
        ecart_tous = moy(f, communs, 0) - moy(a, communs, 0)
        tirages.append({"seed": s, "finis_actuel": len(a), "finis_fermee": len(f), "axe_comparables": len(communs_axe),
                        "duree_axe_actuel_s": round(moy(a, communs_axe, 0), 1),
                        "duree_axe_fermee_s": round(moy(f, communs_axe, 0), 1),
                        "ecart_axe_s": round(ecart, 1), "ecart_tous_s": round(ecart_tous, 1)})
        print(f"{s:<5}{str(len(a)) + '/' + str(len(f)):>10}{len(communs_axe):>7}"
              f"{moy(a, communs_axe, 0):>12.1f}{moy(f, communs_axe, 0):>12.1f}{ecart:>+8.1f}{ecart_tous:>+12.1f}")

    ecarts = [t["ecart_axe_s"] for t in tirages]
    tous = [t["ecart_tous_s"] for t in tirages]
    res = {"n_tirages": len(tirages), "voitures_axe": len(axe), "fin_simulation_s": FIN,
           "ecart_moyen_axe_s": round(statistics.mean(ecarts), 1), "ecart_type_axe_s": round(statistics.stdev(ecarts), 1),
           "plus_lent": sum(1 for e in ecarts if e > 0), "plus_rapide": sum(1 for e in ecarts if e < 0),
           "ecart_moyen_tous_s": round(statistics.mean(tous), 1), "ecart_type_tous_s": round(statistics.stdev(tous), 1),
           "tirages": tirages}
    (RUNS / "resume_10_tirages.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nécart moyen de durée (voitures de la rue) : {res['ecart_moyen_axe_s']:+.1f} s, écart-type {res['ecart_type_axe_s']:.1f} s")
    print(f"tirages où la rue fermée est plus lente : {res['plus_lent']} sur {res['n_tirages']} ; plus rapide : {res['plus_rapide']}")
    print(f"écart moyen sur toutes les voitures communes : {res['ecart_moyen_tous_s']:+.1f} s")
    print("-> runs/resume_10_tirages.json")


if __name__ == "__main__":
    main()
