import json
import os

# 1. Déterminer le dossier data/
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, "..", "data")

scenarios = ["actuel", "pic", "rue_fermee", "voie_reservee"]

# 2. Définir une couleur pour chaque scénario (Rouge, Vert, Bleu, Orange)
COLORS = {
    "actuel": [60, 210, 255, 255],       # Bleu cyan (comme la vue analytique)
    "pic": [255, 170, 40, 255],          # Orange (comme la vue analytique)
    "rue_fermee": [255, 75, 75, 255],    # Rouge
    "voie_reservee": [75, 211, 123, 255] # Vert
}

for scenario in scenarios:
    input_path = os.path.join(data_dir, f"trajectories_{scenario}.json")
    
    if not os.path.exists(input_path):
        print(f"⚠️ Fichier introuvable pour {scenario} : {input_path}")
        continue

    with open(input_path, "r") as f:
        raw_trips = json.load(f)

    raw_trips = raw_trips[:30] 

    # Récupérer la couleur (par défaut rouge si le scénario n'est pas dans le dico)
    main_color = COLORS.get(scenario, [255, 50, 50, 255])
    trail_color = list(main_color)
    trail_color[3] = 150 # On baisse l'opacité de la traînée pour faire joli

    czml = [
        {
            "id": "document",
            "name": f"Trafic {scenario}",
            "version": "1.0",
            "clock": {
                "interval": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
                "currentTime": "2024-01-01T00:00:00Z",
                "multiplier": 10,
                "range": "LOOP_STOP",
                "step": "SYSTEM_CLOCK_MULTIPLIER"
            }
        }
    ]

    for i, trip in enumerate(raw_trips):
        path = trip["path"]
        timestamps = trip.get("timestamps", [p[2] for p in path])
        
        cartographic_degrees = []
        for p, t in zip(path, timestamps):
            cartographic_degrees.extend([t, p[0], p[1], 10.0])
        
        czml.append({
            "id": f"vehicule_{scenario}_{i}",
            "availability": "2024-01-01T00:00:00Z/2024-01-01T00:10:00Z",
            "position": {
                "epoch": "2024-01-01T00:00:00Z",
                "cartographicDegrees": cartographic_degrees
            },
            "point": {
                "color": {"rgba": main_color}, # Utilisation de la couleur
                "pixelSize": 10,
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 2
            },
            "path": {
                "resolution": 1,
                "material": {"solidColor": {"color": {"rgba": trail_color}}},
                "width": 4,
                "leadTime": 0,
                "trailTime": 120
            }
        })

    output_path = os.path.join(data_dir, f"trafic_czml_{scenario}.json")
    with open(output_path, "w") as f:
        json.dump(czml, f, indent=2)
    
    print(f"✅ {scenario} : {len(raw_trips)} véhicules -> {output_path}")