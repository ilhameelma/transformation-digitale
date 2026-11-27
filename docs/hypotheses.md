# Hypothèses et limites des simulations

Projet : jumeau numérique 3D de mobilité urbaine, Rabat centre. Version du 26 novembre 2026. Ce document explique ce que les indicateurs ne disent pas. Les références de comparaison de chaque scénario sont dans `references_comparaison.md`.

## 1. Nature des données

Toutes les données de trafic de ce projet sont simulées avec SUMO 1.28.0. Elles ne sont pas observées sur le terrain : aucun capteur, aucun comptage réel n'a été utilisé. Les chiffres doivent toujours être présentés avec la mention « Données simulées (SUMO) ».

Le réseau routier et les bâtiments viennent d'OpenStreetMap (licence ODbL). La zone d'étude a été agrandie par décision de l'équipe : la zone initiale (vue 3D) couvre environ 2,25 km², avec 419 nœuds, 744 tronçons dans le graphe OSMnx et 1653 bâtiments, et le réseau simulé est plus étendu (enveloppe d'environ 4 km², voir `zone.md`). Les erreurs ou oublis d'OpenStreetMap se retrouvent dans le modèle.

Le modèle est une approximation de la réalité. Les résultats servent à comparer des scénarios entre eux, pas à prédire des valeurs exactes.

## 2. La demande de trafic

La demande est un échantillon simulé de trajets sur le modèle des heures de pointe du matin. Elle ne reproduit pas des déplacements réellement mesurés. Les résultats valent pour cette demande précise, pas pour un autre jour ou une autre heure.

Les tirages (graines aléatoires) ne font varier que le comportement des conducteurs : les trajets de départ sont les mêmes.

## 3. La fenêtre de simulation et les trajets terminés

La plupart des simulations durent 900 s. Un véhicule qui n'a pas fini son trajet à 900 s n'apparaît pas dans les indicateurs. Les moyennes ne portent donc que sur les trajets terminés, ce qui favorise les trajets courts.

Dans le scénario du pic de trafic, 460 trajets se terminent en 900 s (`kpi_pic.json`). La référence « situation actuelle à la même demande » n'a pas encore été simulée : on ne peut donc pas dire quelle proportion de trajets se termine dans chaque cas, ni comparer les deux.

Le nombre de trajets terminés varie d'un scénario à l'autre (295, 281, 460, 300). Il faut toujours le rappeler avant de comparer des temps de trajet ou des totaux de CO₂.



## 4. Tirage 1 et moyenne de 10 tirages

Les fichiers `kpi_<scénario>.json` correspondent à un seul tirage (graine 1). Ces valeurs sont indicatives, adaptées à la démonstration visuelle, mais elles ne permettent pas à elles seules d'affirmer qu'un scénario est meilleur ou moins bon.

Une conclusion ne s'appuie que sur 10 tirages. Un écart n'est affirmé que s'il dépasse nettement l'écart-type entre tirages. Pour la rue fermée, les 10 tirages existent (`tirages_rue_fermee.json`). Pour la voie réservée dans sa version actuelle (réseau de bus à plusieurs lignes), ils restent à faire.

## 5. Scénario rue fermée : un biais de sélection

Dans le scénario de la rue fermée (axe 4330541, 8 tronçons, 359,8 m), 53 voitures utilisent l'axe en situation actuelle. Une fois la rue fermée, 14 d'entre elles n'ont plus aucun itinéraire et ne circulent plus. 39 sont déviées. Les voitures sans itinéraire disparaissent des moyennes.

Sur les voitures de l'axe, la durée moyenne diminue de 19,6 s en moyenne sur 10 tirages (écart-type 9,3 s ; plus rapide dans 10 tirages sur 10). Cette amélioration n'est pas un gain réel pour les automobilistes : elle vient du fait que seules les voitures qui ont pu passer sont comparées. À 900 s, seules 33 voitures sur 53 sont comparables ; à 1500 s, 39 sur 53.

Sur l'ensemble des voitures, l'écart est nul (−0,0 s, écart-type 2,7 s). La fermeture n'a pas d'effet détectable sur le réseau entier. Il ne faut jamais dire que fermer la rue accélère la circulation.

Le modèle suppose que les conducteurs concernés se déportent ou restent bloqués, sans renoncer à leur trajet, changer d'horaire ou de mode de transport. La fermeture est appliquée dès le début de la simulation, sans transition. Le réseau de la rue fermée diffère légèrement du réseau de base (version de réseau différente) ; l'effet mesuré est inférieur à 2 s.

## 6. Scénario pic de trafic (+30 %)

Le scénario du pic augmente la demande de trafic de 30 % par rapport à la situation actuelle. Les indicateurs du tirage 1 sont : 460 trajets terminés, temps de trajet moyen 163,4 s, vitesse moyenne 33,1 km/h, congestion moyenne 0,277 et CO₂ total 234 105 g (`kpi_pic.json`).

La référence de comparaison (situation actuelle avec la même demande de base) n'existe pas encore : aucune comparaison chiffrée n'est possible, et il ne faut annoncer ni hausse ni baisse du temps de trajet. Comme les trajets non terminés à 900 s sont absents des moyennes, un temps moyen plus bas dans le pic que dans une référence ne prouverait pas que le pic est plus fluide. Pour conclure, il faudrait simuler cette référence, puis faire 10 tirages ou allonger la simulation.

Le CO₂ total du pic dépend surtout du nombre de trajets terminés. Il ne se compare qu'entre scénarios de même durée et de même demande.

## 7. Scénario voie réservée aux bus

Le scénario réserve une voie sur deux aux bus sur l'axe 4330541 ; l'autre reste ouverte aux voitures. La rue n'est pas fermée. Ce sont des hypothèses de modèle et non des mesures : le bus est une approximation du tramway, quatre virages ont été ajoutés depuis la voie publique pour conserver les trajets d'origine, les durées de feux n'ont pas changé et aucune priorité aux feux n'est donnée aux bus. Les 8 tronçons de l'axe font 359,8 m, avec 2 voies pour voitures ; 37 des 300 voitures l'empruntent.

Deux versions du réseau de bus existent et ne doivent pas être mélangées. La version initiale a une seule ligne de 360 m, avec un bus toutes les 5 minutes, soit 5 bus : c'est elle qui a servi aux 10 tirages de 1500 s. La version actuelle a plusieurs lignes (axe, L2, L3, L4), soit 22 bus en situation actuelle et seulement les 4 bus de la ligne de l'axe en voie réservée : c'est elle qui a servi aux fichiers du tirage 1 (`kpi_actuel_bus`, `kpi_voie_reservee`, `kpi_bus_*`).

Résultats sur 10 tirages de 1500 s (version initiale, 300 voitures et 5 bus, 305 trajets terminés sur 305) : la durée moyenne des bus passe de 234,2 s à 213,4 s (−20,8 s, −9 %), leur attente de 156,6 s à 138,2 s (−12 %) et leur vitesse de 7,5 à 8,1 km/h. Les bus sont plus rapides dans 10 tirages sur 10, avec un écart-type d'environ 10 s.

Sur ces mêmes 10 tirages, les 37 voitures de l'axe passent de 318,6 s à 341,0 s (+22,4 s, +7 %), plus lentes dans 10 tirages sur 10, avec un écart-type d'environ 8,5 s. Sur l'ensemble des 300 voitures, l'effet est faible : la durée moyenne passe de 182,4 s à 185,1 s (+2,7 s, +1,5 %) et le CO₂ total de 168,0 kg à 169,1 kg (+0,7 %), car seules 37 voitures sur 300 utilisent l'axe.

Ces résultats reposent sur 5 bus seulement : le gain des bus dépend beaucoup d'un ou deux bus qui évitent un feu rouge. Le bilan en personnes est un ordre de grandeur : avec 1,2 personne par voiture (hypothèse, pas une mesure de la simulation), il faut environ 10 passagers par bus pour compenser la perte des voitures de l'axe.

Résultats du tirage 1 avec le réseau de bus actuel (indicatifs) : les 300 voitures passent de 183,2 s à 182,4 s, la congestion moyenne de 0,315 à 0,310, et la congestion moyenne des 8 tronçons de l'axe de 0,88 à 0,84. Les 4 bus de l'axe passent de 241,8 s à 219,5 s (attente de 169,5 s à 150,2 s). Trois bus sur quatre ont la même durée à 1 s près ; le gain vient d'un seul bus (`bus_axe_A2`, environ −90 s). Ces chiffres ne permettent pas de conclure à un gain général pour les bus. Le fichier `kpi_axe.json` (37 voitures de l'axe, 326,1 s puis 333,7 s) est un tirage 1 dont la version du réseau de bus reste à confirmer.

Dans les fichiers du tirage 1, les voitures roulent avec 18 bus de moins en voie réservée qu'en situation actuelle (4 bus contre 22). Cela fausse la comparaison de l'ensemble des voitures : la durée y baisse de 0,8 s alors qu'elle augmente de 2,7 s sur les 10 tirages de la version initiale. La différence de nombre de bus est une explication plausible, non vérifiée par une simulation. Les 10 tirages avec le réseau de bus actuel restent à faire.

Les indicateurs `bus_termines = 4` et `bus_non_comparables = 18` des fichiers `kpi_bus_*` décrivent le réseau actuel : les 4 bus de l'axe sont comparables, les 18 bus des autres lignes sont absents de la voie réservée. Les 5 bus de la version initiale expliquent l'écart apparent avec les 4 bus terminés.

Les bus attendent surtout aux feux, environ 150 s par trajet. La voie réservée évite les files de voitures mais pas le feu rouge. Une priorité aux feux pour les bus serait la suite à tester.

## 8. Indicateurs

Le taux de congestion d'une rue est la part des intervalles de 60 s où la vitesse relative est inférieure à 0,5 (seuil de modélisation, choisi par l'équipe). Seules les rues avec au moins 3 mesures sont retenues. Une rue peu fréquentée peut afficher 100 % avec très peu de mesures.

Le CO₂ n'est calculé que pour les voitures. Le type bus n'a pas de classe d'émission propre.

## 9. Comment répondre aux questions

Pour toute question de chiffres, il faut citer le scénario, la référence de comparaison, le nombre de trajets terminés et la mention « Données simulées (SUMO) ». Si une valeur vient du tirage 1, elle est présentée comme indicative.

Pour toute question du type « ce scénario est-il meilleur ? », la réponse doit rappeler les limites de la section concernée. Si l'information n'existe pas dans les documents, le chatbot répond qu'il ne sait pas.
