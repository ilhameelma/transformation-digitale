# Scénario 3 : pic de trafic +30 %

## 1. Définition

Même zone (Hassan), même réseau, même fenêtre simulée (pic du matin, 900 s), même graine (42) que le
scénario « actuel ». Seule la **demande** change : 650 véhicules au lieu de 500 (500 × 1,3).

Les trajets du scénario « actuel » sont **tous présents** dans le scénario +30 % : le générateur
(`traffic/generate_demand.py --scale 1.3`) utilise la même suite de tirages aléatoires, les 150 véhicules
supplémentaires s'ajoutent donc aux 500 d'origine. Vérifié sur un réseau d'essai : 500 trajets de base,
650 trajets au total, aucun trajet de base perdu.

## 2. Chaîne de traitement

```
traffic : generate_demand.py --scale 1.3   ->  data/demand_pic.csv + demand_pic.trips.xml
sim (m1): run_scenario.py --scenario pic   ->  duarouter + SUMO
                                               data/tripinfo_pic.xml, edgedata_pic.xml, fcd_pic.xml,
                                               trajectories_pic.json, run_pic.json
traffic : compute_kpi.py --scenario pic    ->  data/kpi_pic.json
tests   : convert_to_czml.py --scenario pic->  trafic_czml_pic.json
app     : App.jsx                          ->  sélecteur, comparaison 3D et tableau des écarts
```

Tout se lance avec `scenario_pic.ps1` (Windows) ou `scenario_pic.sh`, depuis la racine du dépôt.

## 3. Fichiers livrés

| Fichier | Statut | Rôle |
|---|---|---|
| `sim/run_scenario.py` | nouveau | Simule un scénario avec SUMO, exporte les trajectoires. Refuse d'écraser des résultats existants sans `--force` |
| `traffic/compute_kpi.py` | modifié | Lit `tripinfo_<scénario>.xml` / `edgedata_<scénario>.xml` ; ajoute `co2_par_vehicule_g`. Le scénario « actuel » continue d'utiliser les anciens noms de fichiers |
| `tests/convert_to_czml.py` | modifié | Options `--scenario`, `--max`, `--out`. Sans option : même résultat qu'avant |
| `mon-app-3d/src/App.jsx` | modifié | Sélecteur de scénario, mode comparaison (2 cartes), tableau des écarts, accents corrigés sur les étiquettes |
| `scenario_pic.ps1` / `.sh` | nouveau | Enchaîne les 5 étapes |

Aucun fichier du scénario « actuel » n'est modifié ou écrasé.

## 4. Lancer

```
.\scenario_pic.ps1
docker compose up -d --build react-viz
```
Puis ouvrir http://localhost:5173/ : choisir « Pic de trafic +30 % », ou cocher « Mode comparaison ».

## 5. Vérifications à faire (dans cet ordre)

1. `data/demand_pic.csv` contient **650 lignes** de données (500 × 1,3).
2. `data/run_pic.json` : `sans_itineraire` doit être petit ; noter `trajets_termines` et `en_route_a_la_fin`.
3. **Cohérence de la base de comparaison.** Les chiffres du scénario « actuel » doivent venir de la même
   chaîne. Test sans rien écraser :
   ```
   docker compose run --rm m1 python run_scenario.py --scenario actuel_ref --demand demand
   docker compose run --rm traffic python compute_kpi.py --scenario actuel_ref
   ```
   Comparer `data/kpi_actuel_ref.json` et `data/kpi_actuel.json` : s'ils sont **identiques**, la comparaison
   est valide. S'ils diffèrent, le scénario « actuel » a été produit avec d'autres paramètres : décider avec
   l'équipe de la version de référence avant de présenter des écarts.
4. Le sens des écarts est cohérent : temps de trajet en hausse, vitesse en baisse, congestion en hausse.
   Si c'est l'inverse, chercher la cause avant d'afficher les résultats.
5. Optionnel : `docker compose run --rm traffic python compute_kpi.py --scenario actuel` recalcule `kpi_actuel.json`
   à partir des fichiers SUMO existants (mêmes valeurs) et y ajoute l'indicateur `co2_par_vehicule_g`.
   Il ne touche ni aux trajectoires ni aux fichiers SUMO.

## 6. Lire les résultats (limites à écrire dans le rapport)

- **CO₂ total** : il augmente mécaniquement avec le nombre de véhicules (+30 % de véhicules ≈ +30 % de CO₂
  avant tout effet de congestion). La **comparaison juste** est le CO₂ par véhicule, ajouté pour cela.
- **Moyennes sur les trajets terminés seulement.** La simulation s'arrête à 900 s : les véhicules encore en
  route ne comptent pas. Avec plus de trafic, davantage de véhicules sont en retard, et les moyennes de temps
  de trajet sont donc **légèrement sous-estimées** pour le scénario chargé. `run_pic.json` donne le nombre
  de véhicules encore en route.
- **Congestion** : part des intervalles d'une minute où la vitesse relative est inférieure à 0,5, comptée
  sur les rues mesurées (définition de `compute_kpi.py`, seuil modifiable).
- **Demande simulée** : aucune donnée de trafic réelle de Rabat n'est utilisée (voir `sources_donnees.md`).
  Les écarts sont des ordres de grandeur du modèle, pas des prévisions.

## 7. Ce qui a été testé, et ce qui ne l'a pas été

Testé avec un **vrai SUMO 1.28.0** (même version que `Dockerfile.m2`) sur un réseau d'essai (grille de 8 × 8
carrefours dans l'emprise de Hassan), avec le `generate_demand.py` et le `compute_kpi.py` de l'équipe :
la demande +30 %, les deux simulations, les indicateurs, la reproductibilité (deux lancements identiques),
la protection contre l'écrasement. `App.jsx` compile avec deck.gl 8.9 et react-map-gl 7.1, et le tableau des
écarts a été vérifié avec les indicateurs réels de l'essai.

**Non testé** : l'exécution dans vos conteneurs Docker, le réseau réel de Hassan, l'affichage visuel de la
nouvelle page dans un navigateur (WebGL), et les noms de services `traffic` et `m1` de votre
`docker-compose.yml` (déduits des commentaires de vos Dockerfile). Les chiffres de l'essai ne sont **pas**
ceux de Rabat.

## 8. Pas encore couvert
- Vue Cesium : `trafic_czml_pic.json` est généré, mais la page `test_cesium_trafic.html` charge seulement
  `trafic_czml.json`. Il faut son contenu pour ajouter le choix du scénario.
- Application Streamlit (`app.py`) : inchangée, seul le scénario « actuel » y est proposé.
