"""Verifie les fichiers de data/ utilises par l'app, et ce que le conteneur react-viz sert vraiment.
Usage : python tests/verif_donnees.py            (depuis la racine du depot)
Le conteneur doit tourner : docker compose up -d react-viz
"""
import json
import os
import time
import urllib.request
from collections import Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
URL = "http://localhost:5173/data/"

TRAJ = ["actuel", "pic", "rue_fermee", "voie_reservee", "actuel_ref", "actuel_bus"]
AUTRES = [
    "buildings.geojson", "network_edges.geojson",
    "axe_4330541.geojson", "rue_fermee_troncons.geojson", "closure.geojson",
    "kpi_actuel.json", "kpi_pic.json", "kpi_rue_fermee.json", "kpi_voie_reservee.json",
    "kpi_actuel_ref.json", "kpi_actuel_bus.json", "kpi_bus_actuel_bus.json",
    "kpi_bus_voie_reservee.json", "kpi_axe.json", "kpi_axe_rue_fermee.json",
    "tirages_rue_fermee.json",
]


def age(path):
    h = (time.time() - os.path.getmtime(path)) / 3600
    return f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} j"


def http_size(name):
    try:
        with urllib.request.urlopen(URL + name, timeout=5) as r:
            body = r.read()
            if body[:15].lstrip().lower().startswith(b"<!doctype"):
                return "HTML (fichier absent : nginx renvoie index.html)"
            return len(body)
    except Exception as e:
        return f"ERREUR {str(e)[:40]}"


def check_file(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None, "ABSENT en local"
    local = os.path.getsize(p)
    srv = http_size(name)
    ok = "OK" if srv == local else f"DIFFERENT (serveur: {srv})"
    return local, f"{local/1e6:.2f} Mo, modifie il y a {age(p)}, volume: {ok}"


print("=" * 70, "\nTRAJECTOIRES\n" + "=" * 70)
for s in TRAJ:
    for prefix in ("trajectories_", "trafic_czml_"):
        name = f"{prefix}{s}.json"
        local, info = check_file(name)
        print(f"{name:<38} {info}")
        if local is None or prefix == "trafic_czml_":
            continue
        d = json.load(open(os.path.join(DATA, name), encoding="utf-8"))
        types = Counter(v.get("type", "SANS_TYPE") for v in d)
        tmax = max(p[2] for v in d for p in v["path"])
        print(f"{'':<38} -> {len(d)} vehicules, types: {dict(types)}, t max: {tmax:.0f} s")

print("\n" + "=" * 70, "\nAUTRES FICHIERS\n" + "=" * 70)
for name in AUTRES:
    local, info = check_file(name)
    print(f"{name:<38} {info}")

print("\nLegende : 'volume: OK' = le conteneur sert exactement le meme fichier que data/ en local.")
print("'SANS_TYPE' = pas de champ type : les bus ne seront pas distingues des voitures.")