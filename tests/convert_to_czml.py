"""
convert_to_czml.py - trajectoires SUMO (JSON) -> CZML pour la vue Cesium.

Usage (depuis la racine du depot) :
    python tests/convert_to_czml.py                      scenario actuel -> trafic_czml.json (comme avant)
    python tests/convert_to_czml.py --scenario pic       -> trafic_czml_pic.json (vehicules orange)
Options : --max 20 (nombre de vehicules), --out fichier
"""
import argparse
import json

COULEURS = {"actuel": [255, 50, 50], "pic": [255, 160, 0]}  # couleur des points par scenario

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="actuel")
ap.add_argument("--max", type=int, default=20, help="nombre de vehicules (20 = comme avant)")
ap.add_argument("--out")
args = ap.parse_args()
out_file = args.out or ("trafic_czml.json" if args.scenario == "actuel" else f"trafic_czml_{args.scenario}.json")
r, g, b = COULEURS.get(args.scenario, [60, 210, 255])

# 1. Charge les trajets SUMO du scenario
with open(f"data/trajectories_{args.scenario}.json", "r", encoding="utf-8") as f:
    raw_trips = json.load(f)

# On prend seulement les premiers vehicules (pour ne pas surcharger Cesium)
raw_trips = raw_trips[:args.max]

# 2. Prepare le paquet CZML
czml = [
    {
        "id": "document",
        "name": f"Trafic Hassan - {args.scenario}",
        "version": "1.0",
        "clock": {
            "interval": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
            "currentTime": "2024-01-01T00:00:00Z",
            "multiplier": 10,  # Accelere le temps 10x
            "range": "LOOP_STOP",
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    }
]

# 3. Convertit chaque vehicule en entite CZML
for i, trip in enumerate(raw_trips):
    path = trip["path"]
    timestamps = trip.get("timestamps", [p[2] for p in path])

    # Liste des positions horodatees : temps, longitude, latitude, altitude (10 m)
    cartographic_degrees = []
    for p, t in zip(path, timestamps):
        cartographic_degrees.extend([t, p[0], p[1], 10.0])

    czml.append({
        "id": f"vehicule_{i}",
        "availability": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
        "position": {
            "epoch": "2024-01-01T00:00:00Z",
            "cartographicDegrees": cartographic_degrees
        },
        "point": {
            "color": {"rgba": [r, g, b, 255]},
            "pixelSize": 10,
            "outlineColor": {"rgba": [0, 0, 0, 255]},
            "outlineWidth": 2
        },
        "path": {
            "resolution": 1,
            "material": {
                "solidColor": {"color": {"rgba": [r, g, b, 150]}}
            },
            "width": 4,
            "leadTime": 0,
            "trailTime": 120  # Garde une trainee de 120 secondes
        }
    })

# 4. Sauvegarde le fichier CZML
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(czml, f, indent=2)

print(f"Fichier {out_file} genere avec {len(raw_trips)} vehicules.")
