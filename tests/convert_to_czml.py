import json
import os
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, "..", "data")

SCENARIOS = ["actuel", "pic", "rue_fermee", "voie_reservee"]
COLORS = {
    "actuel": [60, 210, 255, 255],
    "pic": [255, 170, 40, 255],
    "rue_fermee": [60, 210, 255, 255],       # voitures en cyan, la rue fermée est en rouge
    "voie_reservee": [60, 210, 255, 255],    # voitures en cyan, bus en orange
}
BUS_COLOR = [255, 150, 0, 255]
MAX_CARS = 80          # on garde tous les bus
START = datetime(2024, 1, 1, tzinfo=timezone.utc)

# Fichier de trajectoires à utiliser pour chaque scénario
SOURCE = {"actuel": "actuel", "pic": "pic", "rue_fermee": "rue_fermee", "voie_reservee": "voie_reservee"}


def iso(seconds):
    return (START + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


for scenario in SCENARIOS:
    input_path = os.path.join(data_dir, f"trajectories_{SOURCE[scenario]}.json")
    if not os.path.exists(input_path):
        print(f"Fichier introuvable pour {scenario} : {input_path}")
        continue

    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    buses = [t for t in raw if t.get("type") == "bus"]
    cars = [t for t in raw if t.get("type") != "bus"][:MAX_CARS]
    trips = cars + buses

    t_max = max((p[2] for t in trips for p in t["path"]), default=600)
    interval = f"{iso(0)}/{iso(t_max)}"

    czml = [{
        "id": "document", "name": f"Trafic {scenario}", "version": "1.0",
        "clock": {"interval": interval, "currentTime": iso(0), "multiplier": 10,
                  "range": "LOOP_STOP", "step": "SYSTEM_CLOCK_MULTIPLIER"},
    }]

    for i, trip in enumerate(trips):
        is_bus = trip.get("type") == "bus"
        color = BUS_COLOR if is_bus else COLORS[scenario]
        trail = list(color); trail[3] = 150
        coords = []
        for p in trip["path"]:
            coords.extend([p[2], p[0], p[1], 10.0])
        czml.append({
            "id": f"{'bus' if is_bus else 'voiture'}_{scenario}_{i}",
            "availability": interval,
            "position": {"epoch": iso(0), "cartographicDegrees": coords},
            "point": {"color": {"rgba": color}, "pixelSize": 14 if is_bus else 9,
                      "outlineColor": {"rgba": [0, 0, 0, 255]}, "outlineWidth": 2},
            "path": {"resolution": 1, "material": {"solidColor": {"color": {"rgba": trail}}},
                     "width": 6 if is_bus else 3, "leadTime": 0, "trailTime": 120},
        })

    out = os.path.join(data_dir, f"trafic_czml_{scenario}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(czml, f)
    print(f"{scenario} : {len(cars)} voitures + {len(buses)} bus, {t_max:.0f} s -> {out}")