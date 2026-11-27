# Scénario voie réservée aux bus : axe 4330541

Projet : jumeau numérique 3D de mobilité urbaine, Rabat centre. Version du 26 novembre 2026. Les données de trafic sont simulées (SUMO 1.28.0). Les hypothèses et limites sont dans `hypotheses.md` (section 7).

## 1. Objectif et principe

Le scénario teste un aménagement précis : sur l'axe 4330541 de la zone Hassan, une voie sur deux est réservée aux bus et l'autre reste ouverte aux voitures. La rue n'est pas fermée. Les voitures l'empruntent avec une voie de moins, et on mesure deux choses : le coût pour les voitures de l'axe et le gain pour les bus. La situation actuelle et la voie réservée réutilisent exactement les mêmes 300 trajets de voitures, pour que toute différence vienne de l'aménagement.

## 2. Choix de la rue

Parmi 494 rues à 2 voies ou plus, les tronçons ont été regroupés par rue entière et les voitures qui y passent comptées. La rue retenue est la 4330541, la même que la rue fermée du scénario voisin, pour comparer fermeture totale et voie réservée sur le même axe. Elle compte 8 tronçons continus (#3, #7, #9, #10, #11, #12, #15, #18) pour 359,8 m, tous à 2 voies pour voitures. 37 voitures sur 300 utilisent cet axe.

## 3. Construction du réseau

La version 1 du réseau réserve la voie 0 aux bus sur les 8 tronçons : 4 virages deviennent impossibles pour les voitures, ce qui touche 30 voitures. Réparer les trajets automatiquement avec `duarouter --repair` a été abandonné : 27 des 37 voitures de l'axe le contournaient entièrement, ce qui vidait l'axe de 75 % et faussait tout.

La version 2 ajoute 4 connexions depuis la voie publique : plus aucun virage impossible avec les trajets d'origine non modifiés. Les contrôles montrent 8 voies dont les permissions changent (la voie 0 de chaque tronçon), 4 connexions ajoutées, aucune supprimée. Trois carrefours à feux reçoivent des signaux supplémentaires, mais les durées et le nombre de phases sont identiques.

La version 3, retenue, interdit en plus les bus sur la voie publique (voie 1) : les bus ne roulent que sur la voie réservée.

## 4. Le réseau de bus

Les bus roulent dans les deux scénarios : dans la circulation en situation actuelle, sur la voie réservée sinon. Deux versions existent. La version initiale a une seule ligne de 360 m avec un bus toutes les 5 minutes, soit 5 bus par simulation. La version actuelle a plusieurs lignes : axe_A (4 bus), L2 (7), L3 (7) et L4 (4), soit 22 bus en situation actuelle ; en voie réservée, seuls les 4 bus de la ligne de l'axe circulent. Le bus est une approximation du tramway.

## 5. Résultats en résumé

Sur 10 tirages de 1500 s (version initiale, 5 bus), les bus gagnent environ 21 s (234,2 s puis 213,4 s, −9 %) de façon régulière, tandis que les 37 voitures de l'axe perdent environ 22 s (318,6 s puis 341,0 s, +7 %). Sur les 300 voitures, l'effet est faible (+2,7 s, +1,5 %), car seules 37 voitures utilisent l'axe. Le détail et les mises en garde (5 bus seulement, tirage 1 du réseau actuel, 22 bus contre 4) figurent dans `hypotheses.md`.

Les bus restent lents : ils attendent environ 150 s par trajet, surtout aux feux, notamment sur les tronçons #12 et #15 qui se terminent sur des carrefours à feux. La voie réservée évite les files de voitures mais pas le feu rouge.

## 6. Bilan coûts et bénéfices (illustration)

Le bilan en personnes dépend d'un chiffre qui ne vient pas de la simulation : le nombre de personnes par véhicule. Avec 1,2 personne par voiture (hypothèse à remplacer par une source), la perte des voitures de l'axe est d'environ 1000 personnes-secondes, et il faudrait environ 10 passagers par bus pour l'équilibrer. Avec des bus plus fréquents ou plus remplis, le bilan s'inverse. Ce sont des ordres de grandeur.

## 7. Erreurs corrigées en cours de route

La première idée, « les itinéraires restent valides puisque la rue reste ouverte », était fausse : certains virages à droite partaient de la voie réservée. Un gain global de 3 % sur la première version était un artefact de la réparation automatique des trajets, pas un effet de la voie réservée. Le contrôle des entrées par tronçon a révélé que l'axe se vidait de 75 %, d'où l'ajout des connexions. Enfin, une seule simulation ne suffit pas : les conclusions viennent des 10 tirages.

## 8. Suite possible

Tester une priorité aux feux pour les bus, des bus plus fréquents (avec de nouveaux tirages), et mesurer les 263 autres voitures qui n'utilisent pas l'axe.
