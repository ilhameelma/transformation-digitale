"""Etape 1 : reseau avec la rue fermee (equivalent de make_voie_reservee.py).

Fermeture complete : tronçons de l'avenue + rues transversales des carrefours interieurs (voir common.py).

Lit    : ../hassan.net.xml, data/closure_sumo.json
Ecrit  : hassan_rue_fermee.net.xml   (toutes les voies des rues fermees : disallow="all")
Le reseau de reference n'est jamais modifie.
"""
import json
import re
import sys

from common import DATA, NET_FERME, NET_REF, structure_fermeture, troncons_fermes, troncons_lonlat


def main():
    fermes = set(troncons_fermes())
    texte, trouves, voies = NET_REF.read_text(encoding="utf-8"), set(), 0

    def patch(m):
        nonlocal voies
        if m.group(1) not in fermes:
            return m.group(0)
        trouves.add(m.group(1))
        voies += 1
        tag = re.sub(r'\s(allow|disallow)="[^"]*"', "", m.group(0))
        return tag.replace("<lane", '<lane disallow="all"', 1)

    texte = re.sub(r'<lane id="(.+?)_\d+"[^>]*>', patch, texte)
    if fermes - trouves:
        sys.exit(f"tronçons introuvables : {sorted(fermes - trouves)}")
    NET_FERME.write_text(texte, encoding="utf-8")
    avenue, transv = structure_fermeture()
    print(f"{voies} voies fermees sur {len(fermes)} rues : {len(avenue)} tronçons de l'avenue + "
          f"{len(transv)} rues transversales aux carrefours -> {NET_FERME.name}")

    # Dessin exact des troncons fermes pour la carte (les carrefours entre eux restent ouverts)
    formes = troncons_lonlat(fermes)
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"edge": e, "type": "avenue" if e in avenue else "transversale"}, "geometry": {"type": "LineString", "coordinates": pts}}
        for e, pts in formes.items()]}
    sortie = DATA / "rue_fermee_troncons.geojson"
    sortie.write_text(json.dumps(geo), encoding="utf-8")
    print(f"{len(formes)} troncons dessines -> data/{sortie.name}")


if __name__ == "__main__":
    main()