import json
import datetime

# 1. Charge tes trajets SUMO
with open("data/trajectories_actuel.json", "r") as f:
    raw_trips = json.load(f)

# On prend seulement les 20 premiers véhicules pour le test (pour ne pas surcharger)
raw_trips = raw_trips[:20]

# 2. Prépare le paquet CZML
czml = [
    {
        "id": "document",
        "name": "Trafic Hassan",
        "version": "1.0",
        "clock": {
            "interval": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
            "currentTime": "2024-01-01T00:00:00Z",
            "multiplier": 10,  # Accélère le temps 10x
            "range": "LOOP_STOP",
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    }
]

# 3. Convertit chaque véhicule en entité CZML
for i, trip in enumerate(raw_trips):
    path = trip["path"]
    timestamps = trip.get("timestamps", [p[2] for p in path])
    
    # Construit la liste des positions horodatées
    cartographic_degrees = []
    for p, t in zip(path, timestamps):
        # p[0] = longitude, p[1] = latitude. L'altitude est fixée à 10m.
        cartographic_degrees.extend([t, p[0], p[1], 10.0])
    
    # Ajoute l'entité du véhicule
    czml.append({
        "id": f"vehicule_{i}",
        "availability": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
        "position": {
            "epoch": "2024-01-01T00:00:00Z",
            "cartographicDegrees": cartographic_degrees
        },
        # On utilise un point lumineux au lieu d'un modèle 3D pour le test
        "point": {
            "color": {"rgba": [255, 50, 50, 255]},  # Cyan
            "pixelSize": 10,
            "outlineColor": {"rgba": [0, 0, 0, 255]},
            "outlineWidth": 2
        },
        # Ajoute une traînée derrière le véhicule
        "path": {
            "resolution": 1,
            "material": {
                "solidColor": {"color": {"rgba": [255, 50, 50, 150]}}
            },
            "width": 4,
            "leadTime": 0,
            "trailTime": 120 # Garde une traînée de 120 secondes
        }
    })

# 4. Sauvegarde le fichier CZML
with open("trafic_czml.json", "w") as f:
    json.dump(czml, f, indent=2)

print(f"Fichier trafic_czml.json généré avec {len(raw_trips)} véhicules.")