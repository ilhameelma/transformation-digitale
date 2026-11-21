#!/usr/bin/env bash
# Scenario 3 : pic de trafic +30 %
# A lancer depuis la RACINE du depot (dossier qui contient docker-compose.yml) :
#   ./scenario_pic.sh            premiere fois
#   ./scenario_pic.sh --force    pour refaire le scenario (ecrase les anciens resultats 'pic')
# Hypothese : les services docker compose s'appellent "traffic" et "m1".
set -e
EXTRA=""
[ "$1" = "--force" ] && EXTRA="--force"

echo "=== 1/5 Construction des conteneurs ==="
docker compose build traffic m1
echo "=== 2/5 Demande +30 % : 500 x 1,3 = 650 vehicules ==="
docker compose run --rm traffic python generate_demand.py --scale 1.3 --out /data/demand_pic.csv
echo "=== 3/5 Simulation SUMO du scenario pic ==="
docker compose run --rm m1 python run_scenario.py --scenario pic $EXTRA
echo "=== 4/5 Calcul des indicateurs ==="
docker compose run --rm traffic python compute_kpi.py --scenario pic
echo "=== 5/5 Fichier CZML pour la vue Cesium ==="
python3 tests/convert_to_czml.py --scenario pic

echo
echo "Termine. Reconstruisez l'application : docker compose up -d --build react-viz"
