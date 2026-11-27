"""Chemins et constantes de la partie Airflow.

Tout est lu dans l'environnement avec des valeurs par défaut pour le conteneur `airflow`
(voir docker-compose.yml). Les autres modules lisent ces valeurs à l'appel (`config.DATA`),
ce qui permet de les remplacer dans les tests.
"""
import os
import re
from pathlib import Path

# --- Dossiers (montés par docker-compose) ------------------------------------------------------------
DATA = Path(os.getenv("DATA_DIR", "/data"))          # volume partagé avec les autres services
SIM = Path(os.getenv("SIM_DIR", "/sim"))             # réseau et demande de référence (lecture seule)
TRAFFIC = Path(os.getenv("TRAFFIC_DIR", "/traffic"))  # compute_kpi.py de M4 (formules des indicateurs)

# --- Fichiers de référence (jamais modifiés) ---------------------------------------------------------
NET_REF = SIM / "hassan.net.xml"
ROU_REF = SIM / "hassan.rou.xml"
STREET_INDEX = DATA / "street_index.json"
REF_TRIPINFO = DATA / "tripinfo_actuel_ref.xml"      # situation actuelle : jamais recalculée
REF_KPI = DATA / "kpi_actuel_ref.json"
SCENARIOS = DATA / "scenarios"

# --- Paramètres de simulation : identiques à ceux de la situation actuelle de référence ---------------
# (sim/senario_rue_fermee/run_demo.py : graine 1, 900 s). Même graine et même durée sont nécessaires
# pour que l'écart mesuré soit celui de la fermeture et pas du hasard.
SEED = 1
SIM_END_S = 900
SEUIL_CONGESTION = 0.5
MIN_MESURES = 3

# Même variable et même défaut que sim/senario_rue_fermee/common.py : on ferme aussi les rues
# transversales des carrefours intérieurs, pour qu'aucune voiture ne traverse la rue fermée.
FERMER_CARREFOURS = os.getenv("FERMER_CARREFOURS", "1") != "0"

# --- Contrôles ---------------------------------------------------------------------------------------
ARRIVED_MIN_RATIO = 0.85      # alerte si moins de 85 % des trajets de la référence se terminent
MIN_LENGTH_M = 100            # longueur minimale d'une rue pour le précalcul (comme count_usage.py)
LOCK_TTL_S = 30 * 60          # un verrou plus vieux est considéré comme abandonné
SUMO_TIMEOUT_S = 300

# street_id : minuscules, chiffres, tirets. Pas de point ni de barre : aucun risque de sortir du dossier.
STREET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Fichiers d'un scénario prêt. meta.json est écrit en dernier : sa présence dit « publié ».
FILES = ("trajectories_rue_fermee.json", "kpi_rue_fermee.json", "closed_edges.geojson", "meta.json")
