"""Etape 7 : copie les fichiers utiles a la vue 3D dans data/. Refuse d'ecraser sans --force.

  runs/trajectories_actuel_ref.json -> data/trajectories_actuel_ref.json
  runs/trajectories_rue_fermee.json -> data/trajectories_rue_fermee.json
  runs/kpi_axe.json                 -> data/kpi_axe_rue_fermee.json   (kpi_axe.json est celui de la voie reservee)
  runs/resume_10_tirages.json       -> data/tirages_rue_fermee.json
  runs/<nom>/tripinfo.xml, edgedata.xml -> data/tripinfo_<nom>.xml, edgedata_<nom>.xml   (lus par compute_kpi.py)
Ensuite : compute_kpi.py --scenario actuel_ref / rue_fermee ecrit data/kpi_<nom>.json.
"""
import shutil
import sys

from common import DATA, RUNS

COPIES = {"trajectories_actuel_ref.json": "trajectories_actuel_ref.json",
          "trajectories_rue_fermee.json": "trajectories_rue_fermee.json",
          "kpi_axe.json": "kpi_axe_rue_fermee.json",
          "resume_10_tirages.json": "tirages_rue_fermee.json",
          "actuel_ref/tripinfo.xml": "tripinfo_actuel_ref.xml", "actuel_ref/edgedata.xml": "edgedata_actuel_ref.xml",
          "rue_fermee/tripinfo.xml": "tripinfo_rue_fermee.xml", "rue_fermee/edgedata.xml": "edgedata_rue_fermee.xml"}

force = "--force" in sys.argv
for src, dst in COPIES.items():
    s, d = RUNS / src, DATA / dst
    if not s.exists():
        sys.exit(f"{s} manquant : relancer les etapes precedentes")
    if d.exists() and not force:
        sys.exit(f"{d.name} existe deja dans data/ : relancer avec --force pour le remplacer")
    shutil.copy(s, d)
    print(f"{src} -> data/{dst}")
