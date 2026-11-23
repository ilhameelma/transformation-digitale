# Scénario : rue fermée

Même méthode que le scénario `senario_rue_prive` (voie réservée aux bus) : dossier dédié
`sim/senario_rue_fermee/`, demande de référence jamais modifiée, 10 tirages, comparaison des voitures de la rue,
puis publication dans `data/` et page dans la vue 3D.

## 1. Définition

Même zone (Hassan), même demande de référence `sim/hassan.rou.xml` (300 véhicules, jamais modifiée). Une section
de l'**Avenue Allal Ben Abdellah** (8 tronçons SUMO, 359,8 m, liste dans `data/closure_sumo.json`, c'est l'axe
4330541 de la voie réservée) est interdite à la circulation (`disallow="all"` sur toutes ses voies).

**Seules les voitures dont l'itinéraire passait par la rue sont re-routées** (duarouter, réseau fermé : 37 voitures
sur 300). Les 263 autres gardent exactement leur itinéraire de référence. L'écart mesuré est donc celui de la
fermeture. Une voiture dont le départ ou l'arrivée est sur la rue fermée n'a plus d'itinéraire : elle est retirée
et comptée (`sans_itineraire`).

## 2. Chaîne de traitement (dans `sim/senario_rue_fermee/`)

| Étape | Script | Sortie |
|---|---|---|
| 1 | `make_rue_fermee.py` | `hassan_rue_fermee.net.xml` |
| 2 | `make_demande_fermee.py` | `runs/rue_fermee.rou.xml`, `runs/rue_fermee_demande.json` |
| 3 | `run_seeds.py` | 10 tirages (graines 1 à 10, 1500 s), `runs/resume_10_tirages.json` |
| 4 | `run_demo.py` | tirage 1 sur 900 s : `runs/<nom>/tripinfo.xml, edgedata.xml, fcd.xml`, `runs/trajectories_<nom>.json` |
| 5 | `kpi_axe.py` | `runs/kpi_axe.json` (durée des voitures de la rue, mêmes voitures dans les deux cas) |
| 6 | `publier.py` | copie dans `data/` (refuse d'écraser sans `--force`) |
| 7 | `traffic/compute_kpi.py --scenario actuel_ref` puis `rue_fermee` | `data/kpi_actuel_ref.json`, `data/kpi_rue_fermee.json` |

`<nom>` vaut `actuel_ref` (réseau de référence) ou `rue_fermee`. Le scénario « actuel » de l'équipe
(`kpi_actuel.json`) n'est pas touché ; `actuel_ref` est la référence propre à cette comparaison, sur la demande
`hassan.rou.xml`, comme `actuel_bus` pour la voie réservée.

Tout se lance avec `scenario_rue_fermee.ps1` (Windows) ou `scenario_rue_fermee.sh`, depuis la racine du dépôt.
Les scripts tournent dans le conteneur `traffic` (SUMO inclus) avec `sim/` monté : rien à installer sur le PC.

## 3. Fichiers livrés

| Fichier | Statut |
|---|---|
| `sim/senario_rue_fermee/*.py`, `.gitignore` | nouveaux |
| `mon-app-3d/src/AppRueFermee.jsx` | nouveau : page `/rue-fermee`, bouton Situation actuelle / Rue fermée, rue en rouge, tableau des écarts, conclusion des 10 tirages |
| `mon-app-3d/src/main.jsx` | modifié : route `/rue-fermee` (même principe que `/voie-reservee`) |
| `scenario_rue_fermee.ps1` / `.sh` / `.md` | nouveaux |

Fichiers ajoutés dans `data/` : `trajectories_actuel_ref.json`, `trajectories_rue_fermee.json`, `kpi_actuel_ref.json`,
`kpi_rue_fermee.json`, `kpi_axe_rue_fermee.json`, `tirages_rue_fermee.json` (et `tripinfo_*`, `edgedata_*` : lourds,
à ne pas envoyer sur GitHub). `data/kpi_rue_fermee.json` et `data/trajectories_rue_fermee.json` existent peut-être
déjà d'un essai précédent : `-Force` les remplace.

## 4. Lancer

```
.\scenario_rue_fermee.ps1 -Force
docker compose up -d --build react-viz
```
Puis ouvrir http://localhost:5173/rue-fermee.

## 5. Vérifications à faire (dans cet ordre)

1. `make_demande_fermee.py` affiche « 37 voitures passaient par la rue fermée » (la voie réservée en annonce 37 aussi).
2. `run_seeds.py` : les nombres de trajets terminés (`finis a/f`) sont proches dans les deux cas.
3. Le sens des écarts : temps de trajet des voitures de la rue en hausse. Si `plus_lent` est faible, chercher la cause
   avant de conclure (voir section 6).
4. Les 10 tirages donnent une conclusion stable : écart moyen nettement plus grand que l'écart-type.

## 6. Lire les résultats (limites à écrire dans le rapport)

- **Effet dilué** : 37 voitures sur 300 seulement passent par la rue. Les indicateurs de tout le réseau bougent peu ;
  ceux des voitures de la rue sont les plus parlants.
- **Moyennes sur les voitures terminées dans les deux cas.** Les voitures qui n'ont pas fini ne comptent pas. Les
  voitures sans itinéraire sont comptées à part.
- **Feux** : dans le modèle de la voie réservée, l'axe est freiné par ses feux. Dévier peut donc ne pas coûter de
  temps. À vérifier sur les résultats avant de formuler une conclusion.
- **Demande simulée** : aucune donnée de trafic réelle de Rabat. Les écarts sont des ordres de grandeur du modèle,
  pas des prévisions.
- Une seule graine peut tromper : la conclusion se lit sur les 10 tirages, pas sur le tirage 1 de l'animation.

## 7. Ce qui a été testé, et ce qui ne l'a pas été

Testé avec un **faux SUMO** (programmes `sumo` et `duarouter` remplacés par de petits scripts) : l'enchaînement des
scripts, la fabrication du réseau fermé (16 voies sur 8 rues), la détection des 37 voitures de la rue dans
`hassan.rou.xml`, le re-routage partiel, les statistiques des 10 tirages, `kpi_axe.py`, `publier.py` et sa protection.
Les chiffres de ce banc d'essai ne sont pas des résultats.

**Non testé** : l'exécution avec le vrai SUMO 1.28.0, les scripts `.ps1` et `.sh`, l'option `-w` de
`docker compose run` sur votre version de Docker, la compilation et l'affichage de `AppRueFermee.jsx`.

## 8. Pas encore couvert
- Vue Cesium : pas de fichier CZML pour la rue fermée.
- Lien vers `/rue-fermee` dans la vue principale (`App.jsx`, fichier de M3, non modifié).
- Les bus du scénario voie réservée ne sont pas dans ce scénario (demande de voitures uniquement).
