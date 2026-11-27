# La zone d'étude : zone Hassan, Rabat centre

Projet : jumeau numérique 3D de mobilité urbaine, Rabat centre. Version du 26 novembre 2026. Les données de trafic sont simulées (SUMO) ; le réseau et les bâtiments viennent d'OpenStreetMap (© contributeurs OpenStreetMap, licence ODbL).

## 1. Où se trouve la zone

La zone, appelée zone Hassan dans le projet, est centrée sur le point de latitude 34,0182 et de longitude −6,8308, au centre de Rabat. Elle couvre notamment les abords de l'avenue Mohamed V, de l'avenue Allal Ben Abdellah, de l'avenue Hassan II et de l'avenue Moulay Hassan.

## 2. Une zone agrandie par décision de l'équipe

L'équipe a décidé d'agrandir la zone d'étude au-delà de la zone initiale. La zone initiale, extraite avec OSMnx pour la vue 3D (fichier `zone.json`), est un carré d'environ 1,5 km sur 1,5 km, soit environ 2,25 km², avec 419 nœuds, 744 tronçons routiers (réseau de type voiture) et 1653 bâtiments. Elle respectait la fourchette de 1 à 3 km² du cahier des charges.

Le réseau utilisé pour la simulation SUMO (`hassan.net.xml`) couvre la zone agrandie : il compte 887 tronçons, environ 524 carrefours dont 84 carrefours à feux, et s'étend sur un rectangle d'environ 2,0 km sur 2,7 km. L'enveloppe convexe de ses carrefours mesure environ 4 km², et celle des trajectoires des véhicules environ 3,5 km² (calculs approximatifs). Cette zone dépasse la fourchette de 1 à 3 km² du cahier des charges : c'est un écart voulu, à mentionner comme tel dans le rapport.

Au 26 novembre 2026, les fichiers de la vue 3D (`zone.json`, `buildings.geojson`, `network_nodes.geojson`, `network_edges.geojson`) décrivent encore la zone initiale. Les chiffres de nœuds, de tronçons OSMnx et de bâtiments donnés ci-dessus concernent donc la zone initiale. Tant que ces fichiers ne sont pas régénérés, des véhicules circulent en partie hors de la zone dessinée en 3D.

## 3. Comment le réseau SUMO a été construit

Le réseau SUMO est converti depuis un export OpenStreetMap (`hassan.osm`) avec `netconvert` (SUMO 1.28.0). La conversion ne garde que les voies ouvertes aux voitures, supprime les tronçons isolés, devine les giratoires, fusionne certains carrefours proches et devine les feux de circulation à partir des données OpenStreetMap. Les feux et leurs durées ne sont donc pas calés sur les feux réels de Rabat.

Comme les carrefours sont fusionnés, les tronçons SUMO sont découpés et raccourcis différemment de ceux d'OSMnx : une même rue n'a pas la même longueur dans les deux fichiers.

## 4. Les principales rues

Le fichier `rues_principales.csv` classe les rues par type. Parmi les axes principaux (primary) figurent l'avenue Moulay Ismail (2031 m), l'avenue Al Alaouiyine (1547 m), l'avenue Hassan II (1545 m), l'avenue Moulay Al Hassan (838 m) et l'avenue d'Alger (784 m). Parmi les axes secondaires : l'avenue Mohamed V (2135 m) et l'avenue Allal Ben Abdellah (1022 m). Parmi les axes tertiaires : l'avenue Chellah (1255 m) et l'avenue Moulay Youssef (784 m). Beaucoup de ces rues sont à sens unique, par exemple 100 % pour l'avenue Moulay Ismail.

## 5. Limites

Les bâtiments et les rues d'OpenStreetMap peuvent être incomplets ou erronés. La zone a été choisie parce qu'elle est bien cartographiée, mais ce n'est pas une garantie d'exactitude. Les données de trafic sont simulées, pas observées.
