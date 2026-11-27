# Références de comparaison des scénarios

Projet : jumeau numérique 3D de mobilité urbaine, Rabat centre. Note de l'étape 0 du RAG, version du 26 novembre 2026.
Les données de trafic sont simulées (SUMO 1.28.0) et doivent être signalées comme telles.

## 1. Règle générale

Un scénario ne se compare qu'à la situation de départ simulée dans les mêmes conditions (même demande, même durée, même graine). Les trois familles ci-dessous ne se mélangent pas.

| Scénario | Référence | Conditions communes | Trajets terminés (réf. → scénario) |
|---|---|---|---|
| `rue_fermee` | `actuel_ref` | 300 voitures, départs de 0 à 598 s, 900 s, graine 1 | 295 → 281 |
| `pic` (+30 %) | situation actuelle à 500 trajets (`tripinfo_actuel.xml`) | 500 puis 650 trajets, départs jusqu'à 898 s, 900 s | 363 → 476 |
| `voie_reservee` | `actuel_bus` | 300 voitures + bus, 1500 s, tirage 1 | 300 → 300 |

Mise en garde : `rue_fermee.rou.xml` (462 véhicules) et `demand_rue_fermee.csv` (500 trajets) présents dans `data/` ne sont pas ceux utilisés par la simulation de la rue fermée (qui lit `senario_rue_fermee/runs/rue_fermee.rou.xml`). Ne pas les utiliser pour interpréter `kpi_rue_fermee.json`.

## 2. Sort de `kpi_actuel.json`

Ce fichier annonce 295 trajets et 176,7 s. Il ne correspond à aucune simulation du dossier : `tripinfo_actuel.xml` donne 363 trajets et 169,4 s, `actuel_ref` donne 295 trajets et 174,7 s.
Décision : ne pas l'indexer. Régénérer un KPI de la situation actuelle à 500 trajets à partir de `tripinfo_actuel.xml` et `edgedata_actuel.xml` avec `compute_kpi.py`, puis l'utiliser comme référence du pic.

## 3. La rue concernée

Axe 4330541 (avenue Allal Ben Abdellah). Dans SUMO : 8 tronçons, 359,8 m. Dans OSMnx (`closure.json`) : 7 tronçons, 502 m. C'est la même portion : la conversion SUMO fusionne des carrefours et raccourcit les tronçons. Valeurs de référence : celles de SUMO (8 tronçons, 359,8 m), identiques pour la rue fermée et la voie réservée.

## 4. Les quatre tronçons différents (résolu, effet négligeable)

Le réseau de la rue fermée (`hassan_rue_fermee.net.xml`, généré le 15/11) n'est pas identique au réseau de base (`hassan.net.xml`, généré le 20/11). En plus des 8 tronçons fermés, 27 autres tronçons ont une longueur ou une vitesse légèrement différentes (12 pour la vitesse), dont quatre ont une voie en moins (3 → 2) : `172515199#0`, `172515199#2`, `4049989#0`, `4049989#2`. Ce n'est pas un choix d'aménagement : c'est une différence de version du réseau.

Effet mesuré (SUMO 1.28.0, 3 graines, demande à 500 trajets, rue rouverte dans le réseau ancien) : écart de durée moyenne inférieur à 2 s, dans le bruit entre graines (158 à 160 s dans les deux cas), et 1 à 2 trajets terminés de moins. Cette mesure n'utilise pas la demande exacte de la rue fermée.
Formulation à retenir : « une partie très faible de l'écart observé peut venir d'une différence de version du réseau, pas de la fermeture ». Correction possible : régénérer le réseau fermé depuis `hassan.net.xml`.

## 5. Les bus (résolu)

- En situation actuelle (`actuel_bus`), il y a 22 bus : l'axe (4), et les lignes L2 (7), L3 (7) et L4 (4). En voie réservée, seuls les 4 bus de la ligne de l'axe (`axe_A`) circulent.
- `bus_termines = 4` : ce sont les 4 bus de l'axe, la seule ligne présente dans les deux scénarios. `bus_non_comparables = 18` : les bus des autres lignes (22 − 4), absents de la voie réservée.
- Le chiffre de 5 bus vient de l'ancienne version (ligne unique de 360 m). Ces résultats (bus −20,8 s, 10 tirages) sont à étiqueter « ancienne version » et ne s'appliquent plus.
- Attention, tirage 1 : durée moyenne des 4 bus de l'axe 241,8 s → 219,5 s (−22,3 s), attente 169,5 s → 150,2 s. Trois bus sur quatre ont la même durée à 1 s près ; le gain vient d'un seul bus (`bus_axe_A2`, environ −90 s). Ne pas conclure d'un gain général avant les 10 tirages sur le nouveau réseau de bus.

## 6. À faire encore

1. Régénérer le KPI de la situation actuelle à 500 trajets (section 2).
2. Relancer 10 tirages pour la voie réservée avec le nouveau réseau de bus.
3. Décider si le réseau de la rue fermée est régénéré (section 4).

## Note de 5 lignes

1. Rue fermée : comparée à `actuel_ref` (300 voitures, 900 s, graine 1).
2. Pic : comparé à la situation actuelle à 500 trajets (363 terminés), pas à `actuel_ref`.
3. Voie réservée : comparée à `actuel_bus` (1500 s, 22 bus, dont 4 sur l'axe), non comparable aux autres.
4. Axe 4330541 : 8 tronçons, 359,8 m ; le réseau fermé diffère légèrement du réseau de base (effet inférieur à 2 s).
5. `kpi_actuel.json` est exclu ; les gains bus du tirage 1 reposent sur un seul bus.
