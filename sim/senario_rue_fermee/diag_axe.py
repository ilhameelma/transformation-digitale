"""Diagnostic : pourquoi les voitures de la rue vont-elles plus vite quand elle est fermee ?

Pour les voitures de la rue terminees dans les deux scenarios (tirage donne), compare :
duree, temps d'attente (arrets, feux, files), temps perdu, longueur du trajet.
Relance aussi SUMO sur le reseau de reference pour compter les teleportations (vehicules coinces).

Lit : runs/tripinfo_actuel_<seed>.xml, runs/tripinfo_fermee_<seed>.xml   (crees par run_seeds.py)
Usage : python diag_axe.py [seed]      (defaut : 1)
"""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from common import NET_FERME, NET_REF, ROU_FERME, ROU_REF, RUNS, ids_sur_axe, troncons_fermes

seed = sys.argv[1] if len(sys.argv) > 1 else "1"


def lire(chemin):
    out = {}
    for t in ET.parse(chemin).getroot().findall("tripinfo"):
        out[t.get("id")] = {k: float(t.get(k, 0)) for k in ("duration", "waitingTime", "timeLoss", "routeLength")}
    return out


a = lire(RUNS / f"tripinfo_actuel_{seed}.xml")
f = lire(RUNS / f"tripinfo_fermee_{seed}.xml")
axe = ids_sur_axe(troncons_fermes())
communs = sorted(v for v in axe if v in a and v in f)


def moy(d, cle, ids):
    return sum(d[v][cle] for v in ids) / len(ids)


print(f"Tirage {seed} : {len(communs)} voitures de la rue terminees dans les deux scenarios\n")
print(f"{'':<22}{'actuel':>10}{'rue fermee':>12}{'ecart':>9}")
for cle, nom in (("duration", "duree (s)"), ("waitingTime", "attente (s)"),
                 ("timeLoss", "temps perdu (s)"), ("routeLength", "longueur (m)")):
    x, y = moy(a, cle, communs), moy(f, cle, communs)
    print(f"{nom:<22}{x:>10.1f}{y:>12.1f}{y - x:>+9.1f}")

autres = [v for v in a if v in f and v not in axe]
print(f"\nAutres voitures ({len(autres)}) : duree {moy(a, 'duration', autres):.1f} -> {moy(f, 'duration', autres):.1f} s, "
      f"attente {moy(a, 'waitingTime', autres):.1f} -> {moy(f, 'waitingTime', autres):.1f} s")

if shutil.which("sumo"):
    print("\nTeleportations (vehicules coinces, dechargees par SUMO) :")
    for nom, net, rou in (("actuel", NET_REF, ROU_REF), ("rue fermee", NET_FERME, ROU_FERME)):
        r = subprocess.run(["sumo", "-n", str(net), "-r", str(rou), "-b", "0", "-e", "1500", "--seed", seed,
                            "--no-step-log", "true", "--duration-log.statistics", "true"],
                           capture_output=True, text=True)
        lignes = [l.strip() for l in (r.stdout + r.stderr).splitlines() if re.search(r"[Tt]eleport", l)]
        print(f"  {nom:<12}: " + (" | ".join(lignes) if lignes else "aucune ligne 'Teleports' (probablement 0)"))