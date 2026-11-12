# Jumeau numérique 3D de mobilité urbaine : Rabat centre

Projet de module **Transformation digitale** (Smart City, IA, Big Data, IoT).
Équipe de 4 étudiants, 4 semaines.

## 1. Présentation

Les communes décident souvent d'un aménagement de mobilité (fermer une rue, créer une voie de bus) à partir de plans 2D et de rapports statiques, puis découvrent l'impact après les travaux.

Ce projet livre un **prototype de jumeau numérique 3D** d'une zone de 1 à 3 km² du centre de Rabat. Le décideur teste une décision de mobilité sur une copie 3D de la ville et **compare la situation actuelle avec la situation simulée**, avant de l'appliquer.

### Objectifs du MVP

1. Reproduire en 3D une zone du centre de Rabat à partir d'OpenStreetMap.
2. Simuler le trafic avec SUMO pour 3 scénarios : situation actuelle, fermeture d'une rue, pic de trafic (+30 %).
3. Calculer 4 indicateurs par scénario : temps de trajet moyen, vitesse moyenne, taux de congestion par rue, émissions de CO₂ estimées.
4. Comparer « actuel » et « simulé » dans une interface 3D, un scénario s'affichant en 3 clics.
5. Optionnel (P2) : prédire la congestion à 15-30 minutes avec un modèle simple.

### Hors périmètre

Capteurs IoT réels, flux en temps réel (MQTT, Kafka), plusieurs villes, rendu photoréaliste, réalité virtuelle, deep learning. Le temps réel est une perspective de phase 2.

> **Transparence** : les données de trafic sont **simulées** (SUMO, trajets aléatoires), calées sur des sources ouvertes. Elles sont signalées comme telles dans l'interface et dans le rapport.

## 2. Architecture

Les données traversent 4 étapes, **sans streaming** : les scénarios sont précalculés avec SUMO, puis rejoués dans la vue 3D.

```
Données de la ville (OSMnx) ─┐
                             ├─► Simulation SUMO ─► Export JSON/GeoJSON ─► Vue 3D (pydeck / deck.gl)
Demande de trafic (Python) ──┘     3 scénarios        trajectoires + KPI
                                                              └─► Prédiction IA (P2, scikit-learn)
```

| Couche | Technologie | Plan B |
|---|---|---|
| Données de la ville | OpenStreetMap, OSMnx | Export manuel depuis openstreetmap.org |
| Demande de trafic | Script Python (pics du matin et du soir) | Fichier CSV écrit à la main |
| Simulation | SUMO 1.28.0 | Simulation Python avec NetworkX |
| Export | Fichiers JSON / GeoJSON | Fichiers CSV |
| Vue 3D | pydeck (deck.gl) | MapLibre GL JS avec bâtiments extrudés |
| Prédiction (P2) | Python, scikit-learn | Moyenne mobile par tranche horaire |
| Déploiement | Docker, Docker Compose | Scripts de lancement manuels |

## 3. Structure du dépôt

```
projet/
├── docker-compose.yml
├── README.md
├── fcd_to_json.py   # convertit data/fcd.xml en data/trajectories_<scenario>.json
├── data/            # volume partagé : réseau, bâtiments, demande, trajectoires, KPI
├── sim/             # réseau SUMO, configuration, Dockerfile, script de lancement
├── traffic/         # génération de la demande de trafic + calcul des indicateurs
├── viz/             # vue 3D (pydeck / deck.gl), aperçu preview.html
└── docs/            # cahier des charges, Business Model Canvas, rapport
```

Chaque service lit et écrit des fichiers dans `data/`. Ce dossier est le **format d'échange** entre les membres de l'équipe.

### Format d'échange

| Fichier | Produit par | Lu par | Contenu |
|---|---|---|---|
| `data/network.geojson` | sim | viz | Routes de la zone |
| `data/buildings.geojson` | sim | viz | Bâtiments de la zone |
| `data/demand.csv` | traffic | sim | Demande de trafic simulée |
| `data/tripinfo.xml`, `data/edgedata.xml`, `data/fcd.xml` | sim (SUMO) | traffic, `fcd_to_json.py` | Sorties brutes de SUMO |
| `data/trajectories_<scenario>.json` | sim | viz | Trajets des véhicules par scénario |
| `data/kpi_<scenario>.json` | traffic | viz | Les 4 indicateurs par scénario |

Format de `trajectories_<scenario>.json` (WGS84, temps en secondes depuis le début de la simulation) :

```json
[{"id": "0", "path": [[-6.835673, 34.016046, 0], [-6.835776, 34.015864, 1]]}]
```

## 4. Installation

### Prérequis

- Docker Desktop et Docker Compose
- Git
- Python 3.11 ou plus, pour les scripts hors Docker
- Windows, macOS ou Linux (sous Windows, utiliser des chemins relatifs dans le `docker-compose.yml`)

> **Règle d'équipe : la version de SUMO doit être identique partout** (poste local, Docker, tous les membres) : `eclipse-sumo==1.28.0`. Le paquet `sumo` de Debian (`apt`) installe la 1.15, incompatible avec les réseaux convertis en 1.28.

### Démarrage

```bash
git clone <url-du-depot>
cd projet
docker compose up --build sim
```

Le premier build dure environ 5 minutes. Résultat attendu : `Simulation terminée, sorties dans /data`, code de sortie 0, et `tripinfo.xml`, `fcd.xml`, `edgedata.xml` dans `data/`.

Puis convertir les trajectoires pour la vue 3D :

```bash
python fcd_to_json.py
```

### Lancer un service seul

```bash
docker compose up --build sim
docker compose up --build traffic
docker compose up --build viz
```

### Arrêter et nettoyer

```bash
docker compose down
```

## 5. Simulation SUMO (état d'avancement)

La simulation tourne dans Docker **sans interface** (`sumo`, pas `sumo-gui`) : elle écrit des fichiers et n'affiche rien. L'affichage est assuré par la vue 3D.

### Contenu de `sim/`

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Image Python 3.11 + SUMO 1.28.0 (pip) + bibliothèques système |
| `run_test.py` | Lance `sumo` avec les sorties dans `/data` |
| `rabat.sumocfg` | Configuration (réseau, trajets, durée 0 à 600 s) |
| `rabat.net.xml` | Réseau routier converti depuis OpenStreetMap |
| `rabat.rou.xml` | Trajets des véhicules (300 véhicules, simulés) |
| `additional.xml` | Mesure par rue et par minute (`edgeData`) écrite vers `/data/edgedata.xml` |

### Chaîne de commandes validée (zone de test)

Zone de test : bbox `-6.8360,34.0105,-6.8293,34.0160` (≈ 0,35 km², autour de la gare de Rabat-Ville). La zone finale (1 à 3 km²) sera fournie par M1 et la même chaîne sera relancée.

```
curl -o map.osm "https://overpass.private.coffee/api/map?bbox=-6.8360,34.0105,-6.8293,34.0160"
netconvert --osm-files map.osm -o rabat.net.xml --geometry.remove --roundabouts.guess --junctions.join --tls.guess-signals --tls.discard-simple --keep-edges.by-vclass passenger --remove-edges.isolated
python "%SUMO_HOME%\tools\randomTrips.py" -n rabat.net.xml -e 600 -p 2 -r rabat.rou.xml --fringe-factor 5 --validate
sumo -c rabat.sumocfg --additional-files additional.xml --tripinfo-output tripinfo.xml --fcd-output fcd.xml --fcd-output.geo true --device.emissions.probability 1
```

Notes :
- `overpass-api.de` peut répondre `406 Not Acceptable` à `curl` : utiliser `overpass.private.coffee` ou l'export manuel depuis openstreetmap.org.
- `--fcd-output.geo true` donne des longitude/latitude, à utiliser seulement sur un réseau géoréférencé (OSM).
- Pour voir la simulation à l'écran (contrôle visuel, hors Docker) : `cd sim` puis `sumo-gui -c rabat.sumocfg --start --delay 100`. Ne pas utiliser `-n`, qui ouvre le réseau sans véhicule.

### Fichiers de sortie

| Fichier | Contenu | Indicateur |
|---|---|---|
| `tripinfo.xml` | une ligne par trajet terminé : durée, longueur, CO₂ | temps de trajet moyen, vitesse moyenne, CO₂ |
| `edgedata.xml` | une ligne par rue et par minute : vitesse, occupation, `speedRelative` | taux de congestion par rue |
| `fcd.xml` | position (lon, lat), vitesse, angle de chaque véhicule, seconde par seconde | trajectoires pour la vue 3D |

### Résultats de référence

| Réseau | Trajets terminés | Durée moy. | Vitesse moy. | CO₂ total |
|---|---|---|---|---|
| Grille 5x5 (test, local) | 150 / 150 | 86,4 s | 41,9 km/h | 31 635 g |
| Rabat, 0,35 km² (local) | 264 / 300 | 67,7 s | 42,8 km/h | 61 432 g |
| Rabat, 0,35 km² (Docker) | 264 / 300 | 67,7 s | 42,8 km/h | 61 432 g |

Le résultat Docker est identique au local : la simulation est reproductible. 122 rues sont mesurées.

### Limites connues

1. 36 véhicules sur 300 n'ont pas fini leur trajet à t = 600 s et sont absents de `tripinfo.xml` : léger biais du temps moyen vers les trajets courts. Allonger la simulation ou le documenter.
2. Le taux de congestion est à interpréter avec précaution : peu de mesures par rue, et le seuil relatif pénalise les rues à vitesse limite élevée. Prévoir un minimum de mesures (par exemple 3).
3. Le CO₂ total ne se compare qu'entre scénarios de même durée et de même demande.
4. La zone de test est trop petite pour la démo.

### Dépannage Docker

| Erreur | Cause | Solution |
|---|---|---|
| `Unknown vehicle class 'container'...` | SUMO installé par `apt` (1.15) plus ancien que le réseau (1.28) | installer `eclipse-sumo==1.28.0` via pip |
| `libX11.so.6: cannot open shared object file` | bibliothèques X11/OpenGL absentes de l'image `slim` | paquets `apt` listés dans le `Dockerfile` |
| `libatomic.so.1: cannot open shared object file` | bibliothèque manquante | paquet `libatomic1` |

Diagnostic : `docker compose run --rm --entrypoint sh sim -c "ldd /usr/local/lib/python3.11/site-packages/sumo/bin/sumo | grep 'not found'"`.

Ne pas modifier les deux `RUN` du Dockerfile une fois qu'ils marchent : cela garde le cache Docker.

## 6. Utilisation

1. Lancer la simulation (`docker compose up --build sim`) puis `python fcd_to_json.py`.
2. Aperçu rapide des trajectoires : `python -m http.server 8000`, puis ouvrir `http://localhost:8000/viz/preview.html`.
3. Dans la vue 3D finale : choisir un scénario (**situation actuelle**, **rue fermée** ou **pic de trafic (+30 %)**), observer les véhicules animés et les rues colorées selon la congestion, puis comparer « actuel » et « simulé » en 3D et dans le tableau des 4 indicateurs.

## 7. Indicateurs

| Indicateur | Description |
|---|---|
| Temps de trajet moyen | Durée moyenne des trajets simulés (`tripinfo.xml`) |
| Vitesse moyenne | Vitesse moyenne sur le réseau (`tripinfo.xml`) |
| Taux de congestion par rue | Part des intervalles de 60 s où `speedRelative < 0,5`, parmi les intervalles où la rue a eu des véhicules (`edgedata.xml`) |
| Émissions de CO₂ estimées | Somme de `CO2_abs` des trajets (`tripinfo.xml`, en mg) |

Le seuil de congestion (0,5) et le nombre minimal de mesures par rue sont des choix de modélisation, à fixer avec M4 et à documenter dans `docs/`.

## 8. Équipe et rôles

| Membre | Rôle | Responsabilités principales |
|---|---|---|
| Membre 1 | Zone et réseau | Choix de la zone, OSMnx, sources de données |
| Membre 2 | SUMO | Installation, simulation, scénarios |
| Membre 3 | Vue 3D | Scène 3D, véhicules animés, comparaison |
| Membre 4 | Trafic et indicateurs | Demande de trafic, KPI, prédiction (P2) |

Chaque membre a un binôme de secours : M1 avec M2, M3 avec M4.

### Fonctionnement

- Point de 15 minutes le lundi et le jeudi.
- Tableau de tâches partagé (Trello, Notion ou GitHub Projects).
- Un dépôt Git unique, **une branche par fonctionnalité**, revue avant fusion.

## 9. Planning

| Semaine | Objectif | Jalon |
|---|---|---|
| 1 | Cadrage | Zone choisie, SUMO et vue 3D testés séparément, chaque conteneur tourne seul |
| 2 | Tranche minimale | Un réseau simulé dans SUMO, un véhicule animé en 3D, un indicateur affiché |
| 3 | Intégration | **Démo figée** : 3 scénarios, vue 3D et comparaison intégrés |
| 4 | Finalisation | Tests, correctifs, rapport, vidéo de démo, soutenance |

Aucune nouvelle fonctionnalité en semaine 4.

### Avancement

- [x] SUMO installé, testé en local (grille 5x5) puis sur un réseau OSM de Rabat
- [x] Sorties `tripinfo`, `fcd`, `edgedata` produites et contrôlées
- [x] `docker compose up --build sim` fonctionne sans interface, résultats identiques au local
- [x] Conversion `fcd.xml` vers `trajectories_actuel.json` (299 véhicules) et aperçu animé
- [x] Décision : **continuer avec SUMO** (pas de plan B NetworkX)
- [ ] Zone finale de 1 à 3 km² (M1)
- [ ] Fusion du Dockerfile `sim/` avec celui de M1 (ajout d'OSMnx, version de Python alignée)
- [ ] Scénarios « rue fermée » et « pic de trafic +30 % » (`closingReroute` ou réseau modifié ; `--scale 1.3`)
- [ ] `fcd_to_json.py` avec le nom du scénario en argument
- [ ] Fichiers `kpi_<scenario>.json` (M4)
- [ ] Vue 3D avec fond de carte et bâtiments (M3)

## 10. Tests d'acceptation

| Réf. | Test | Résultat attendu |
|---|---|---|
| T1 | Charger la zone de Rabat | Routes et bâtiments s'affichent en 3D |
| T2 | Lancer la simulation actuelle | Les 4 indicateurs de référence sont calculés |
| T3 | Exécuter les 3 scénarios | Indicateurs différents de la référence |
| T4 | Observer la scène pendant un scénario | Les véhicules circulent sur le réseau |
| T5 | Comparer « actuel » et « simulé » | Différence visible en 3D et en chiffres |
| T6 | Mesurer l'affichage d'un scénario | Moins de 5 secondes, en 3 clics |
| T7 | Mode démo guidé (P2) | Les scénarios s'enchaînent pas à pas |
| T8 | Remettre le rapport | Analyse de transformation digitale complète |

## 11. Risques et plans B

| Risque | Plan B |
|---|---|
| SUMO plus long à prendre en main | Levé en semaine 1 (SUMO validé en local et dans Docker) ; plan B NetworkX conservé si besoin |
| Vue 3D plus longue à prendre en main | Tranche minimale en semaine 2 : un bâtiment, un véhicule, un chiffre |
| Données de trafic réelles indisponibles | Données simulées, calées sur des sources ouvertes, signalées comme telles |
| Bâtiments OSM incomplets | Choisir une zone bien cartographiée |
| Retard sur l'intégration | Démo figée en semaine 3 |
| Absence d'un membre | Binômes de secours et code documenté |

### Conseils Docker

- SUMO se lance **sans interface** (`sumo`, pas `sumo-gui`) dans un conteneur.
- Un port différent par service qui expose une page web.
- Même version de Python dans tous les `Dockerfile`.
- Même version de SUMO partout : `eclipse-sumo==1.28.0`.

## 12. Sources de données candidates

À vérifier (couverture, licence, format) :

- Portail data.gov.ma
- Wiki OpenStreetMap Maroc
- GTFS ONCF et Tétouan
- Jeu de données de trafic de Casablanca

## 13. Livrables

| Livrable | Échéance |
|---|---|
| Cahier des charges et Business Model Canvas | Fin de semaine 1 |
| Jeu de données (réseau OSM, demande simulée, script de génération) | Fin de semaine 2 |
| Prototype fonctionnel | Fin de semaine 3 |
| Démo de 5 minutes avec vidéo de secours | Semaine 4 |
| Code source avec README | Fin de semaine 4 |
| Rapport avec analyse de transformation digitale | Fin de semaine 4 |
| Présentation de 10 à 12 diapositives | Fin de semaine 4 |

## 14. Licence et données

Aucune donnée personnelle n'est utilisée. Les données OpenStreetMap sont sous licence ODbL (© contributeurs OpenStreetMap). Les données de trafic sont simulées. Les licences des autres sources sont à vérifier.
