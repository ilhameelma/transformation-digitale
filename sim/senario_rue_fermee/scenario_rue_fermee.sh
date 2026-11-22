#!/usr/bin/env bash
# Scenario rue fermee (Avenue Allal Ben Abdellah), meme methode que senario_rue_prive (voie reservee).
# A lancer depuis la RACINE du depot :   ./scenario_rue_fermee.sh [--force]
set -e
EXTRA=""
[ "$1" = "--force" ] && EXTRA="--force"
sim() { s="$1"; shift; docker compose run --rm -v "$PWD/sim:/sim" -w /sim/senario_rue_fermee traffic python "$s" "$@"; }

echo "=== 1/9 Construction du conteneur traffic ===";            docker compose build traffic
echo "=== 2/9 Reseau avec la rue fermee ===";                    sim make_rue_fermee.py
echo "=== 3/9 Demande : voitures de la rue deviees ===";         sim make_demande_fermee.py
echo "=== 4/9 10 tirages (20 simulations) ===";                  sim run_seeds.py
echo "=== 5/9 Tirage 1 detaille ===";                            sim run_demo.py
echo "=== 6/9 Indicateur de la rue ===";                         sim kpi_axe.py
echo "=== 7/9 Publication dans data/ ===";                       sim publier.py $EXTRA
echo "=== 8/9 Indicateurs : situation actuelle ===";             docker compose run --rm traffic python compute_kpi.py --scenario actuel_ref
echo "=== 9/9 Indicateurs : rue fermee ===";                     docker compose run --rm traffic python compute_kpi.py --scenario rue_fermee

echo; echo "Termine. Reconstruisez l'application : docker compose up -d --build react-viz"
echo "Puis ouvrez http://localhost:5173/rue-fermee"
