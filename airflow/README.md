# Partie Airflow : scénario « rue fermée » à la demande

Airflow simule la fermeture d'**une rue entière** avec SUMO et publie les fichiers lus par la vue 3D.
Données simulées (SUMO) : tirage 1, graine 1, 900 s, indicatif.

## Lancer

```bash
cp .env.example .env            # puis changer les mots de passe
docker compose --profile airflow up --build airflow
```

Interface : http://localhost:8080 (compte `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD`).
Le profil `airflow` est séparé : la démo de base (`docker compose up`) reste inchangée.

## Index des rues

`data/street_index.json` (149 rues) est généré par :

```bash
python airflow/tools/build_street_index.py
```

Les noms viennent de `data/network_edges.geojson` : `hassan.net.xml` ne contient aucun nom de rue.
Les 139 tronçons sans nom ne sont pas indexés. Si l'index est produit autrement, garder le même format.

## DAG

| DAG | Rôle |
|---|---|
| `closed_street` | une rue : `prepare` → `simulate` → `export` → `publish`. Paramètres : `street_id`, `force` |
| `precompute_top_streets` | les N rues les plus utilisées (5 par défaut), 2 en parallèle. Paramètres : `n`, `force` |

Si le scénario existe déjà, `closed_street` saute toutes les tâches (aucun recalcul).
La situation actuelle n'est jamais recalculée : comparaison avec `data/tripinfo_actuel_ref.xml`.

## Appel depuis le chatbot (API REST)

```bash
# Déclencher (street_id : clé de street_index.json)
curl -u admin:MOT_DE_PASSE -H 'Content-Type: application/json' \
  -X POST http://localhost:8080/api/v1/dags/closed_street/dagRuns \
  -d '{"conf": {"street_id": "avenue-mohamed-v"}}'

# Suivre le run
curl -u admin:MOT_DE_PASSE http://localhost:8080/api/v1/dags/closed_street/dagRuns/<dag_run_id>
```

Un `street_id` hors format (`../x`, majuscules, espaces) est refusé par l'API (HTTP 400). Un `street_id` bien
formé mais absent de l'index fait échouer `prepare`. Aucun dossier n'est créé dans les deux cas.

## Sorties : `data/scenarios/<street_id>/`

| Fichier | Contenu |
|---|---|
| `meta.json` | méthode, graine, version SUMO, tronçons fermés, impact sur les voitures de la rue, validation. Écrit en dernier : sa présence veut dire « prêt » |
| `kpi_rue_fermee.json` | les 4 indicateurs (formules de `traffic/compute_kpi.py`) |
| `trajectories_rue_fermee.json` | trajectoires, même format que `data/trajectories_*.json` |
| `closed_edges.geojson` | tracé des tronçons fermés (`rue` / `transversale`) |
| `status.json` | `running` / `ready` / `failed`, étape en cours, erreur |

Pas de `meta.json` : scénario pas prêt. `status.json` à `failed` : lire `error`. Un état `running` vieux de plus de
30 min est considéré comme échoué. Un recalcul forcé qui échoue ne casse pas les fichiers déjà publiés.

## Réglages

- `FERMER_CARREFOURS=0` : ne ferme que la rue (par défaut, les rues transversales des carrefours intérieurs sont
  fermées aussi, comme dans `sim/senario_rue_fermee/common.py`). Variable de l'environnement du conteneur `airflow`.
- `ARRIVED_MIN_RATIO` (`include/jumeau/config.py`) : alerte si moins de 85 % des trajets de la référence se terminent.

## Tests

```bash
pip install apache-airflow==2.10.5 pytest eclipse-sumo==1.28.0   # Python 3.11
pytest airflow/tests
```

Le test de régression rejoue la section déjà simulée (Avenue Allal Ben Abdellah) et vérifie qu'on retrouve
exactement les résultats de l'équipe.
