# Scénario rue fermée : avenue Allal Ben Abdellah

Projet : jumeau numérique 3D de mobilité urbaine, Rabat centre. Version du 26 novembre 2026. Les données de trafic sont simulées (SUMO). Les limites de ce scénario sont détaillées dans `hypotheses.md` (section 5) et ses références dans `references_comparaison.md`.

## 1. Quelle rue est fermée

Le scénario ferme une portion de l'avenue Allal Ben Abdellah (identifiant OpenStreetMap 4330541), un axe secondaire à sens unique d'environ 1 km. La section fermée est centrée sur la rue : 400 m demandés, 486 m couverts dans OSMnx (7 tronçons, 502 m). Dans le réseau SUMO, la même portion compte 8 tronçons (#3, #7, #9, #10, #11, #12, #15, #18) pour 359,8 m, avec 2 voies chacun. La différence de longueur vient de la fusion des carrefours lors de la conversion. Ce sont les valeurs SUMO qui font référence.

## 2. Comment la fermeture est modélisée

Dans le réseau de la rue fermée, les voies des 8 tronçons sont interdites à tous les véhicules dès le début de la simulation. Les voitures dont l'itinéraire passait par l'axe sont déviées si une autre route existe ; sinon elles ne partent pas. La demande n'est pas modifiée : personne ne renonce à son trajet ni ne change de mode de transport.

La simulation dure 900 s avec la graine 1 pour le tirage de démonstration, et 1500 s pour les 10 tirages. La référence de comparaison est `actuel_ref` (300 voitures, départs de 0 à 598 s).

## 3. Résultats du tirage 1 (900 s, indicatifs)

La situation de référence termine 295 trajets : temps de trajet moyen 174,7 s, vitesse moyenne 32,8 km/h, CO₂ total 162 072 g, congestion moyenne 0,308. La rue fermée termine 281 trajets : 170,7 s, 33,6 km/h, 152 794 g, congestion moyenne 0,304.

Ces chiffres ne montrent pas une amélioration réelle. Les 14 trajets de moins expliquent à eux seuls la baisse du CO₂ et une partie des écarts. Sur les 53 voitures qui utilisent l'axe, 14 n'ont plus d'itinéraire et 39 sont déviées ; seules 33 sont comparables à 900 s. Leur durée passe de 269,4 s à 243,1 s, un écart qui vient de la sélection des voitures comparées.

## 4. Résultats sur 10 tirages (1500 s)

Sur les 10 tirages, 300 trajets sont terminés en situation de référence contre 286 en rue fermée. Sur les voitures comparables de l'axe, la durée diminue de 19,6 s en moyenne (écart-type 9,3 s, plus rapide dans 10 tirages sur 10). Sur l'ensemble des voitures, l'écart est nul : −0,0 s, avec un écart-type de 2,7 s. La fermeture n'a donc pas d'effet détectable sur le réseau entier.

## 5. Quoi retenir

Fermer cette portion n'accélère pas la circulation : elle supprime les trajets qui ne peuvent plus passer, et l'écart sur l'axe est un biais de sélection. Le même axe sert au scénario de la voie réservée aux bus, ce qui permet de comparer fermeture totale et voie réservée.
