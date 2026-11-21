"""Géométrie de l'axe 4330541 en longitude/latitude (pour la vue 3D).
À lancer dans sim/senario_rue_prive. Utilise sumolib (installé avec SUMO)."""
import json
import sumolib

NET = "../hassan.net.xml"  # réseau de référence, lu seulement
TRONCONS = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
            "4330541#11", "4330541#12", "4330541#15", "4330541#18"]

net = sumolib.net.readNet(NET)

def lonlat(shape):
    return [list(net.convertXY2LonLat(x, y)) for x, y in shape]

features = []
for eid in TRONCONS:
    edge = net.getEdge(eid)
    features.append({"type": "Feature", "properties": {"kind": "axe", "edge": eid},
                     "geometry": {"type": "LineString", "coordinates": lonlat(edge.getShape())}})
    # voie 0 = voie réservée aux bus dans le scénario
    lane0 = edge.getLanes()[0]
    features.append({"type": "Feature", "properties": {"kind": "voie_reservee", "edge": eid},
                     "geometry": {"type": "LineString", "coordinates": lonlat(lane0.getShape())}})

with open("runs/axe_4330541.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f)
print(len(features), "éléments écrits -> runs/axe_4330541.geojson")