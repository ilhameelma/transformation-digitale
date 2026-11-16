"""
download_osm.py - telecharge les routes de la zone au format .osm (pour SUMO/netconvert).
Lit la bbox dans <data>/zone.json et ecrit <data>/hassan.osm.
<data> = OUTPUT_DIR si defini (Docker), sinon <depot>/data.
"""
import json
import os
import time
from pathlib import Path

import requests

DATA = Path(os.getenv("OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "data")
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HEADERS = {"User-Agent": "jumeau-numerique-rabat/1.0 (projet etudiant ENSAH)"}

west, south, east, north = json.loads((DATA / "zone.json").read_text(encoding="utf-8"))["bbox_west_south_east_north"]
query = f'[out:xml][timeout:180];(way["highway"]({south},{west},{north},{east});>;);out meta;'

wait = 10
for i in range(1, 7):
    url = SERVERS[(i - 1) % len(SERVERS)]
    try:
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=200)
        r.raise_for_status()
        out = DATA / "hassan.osm"
        out.write_bytes(r.content)
        print(f"OK : {len(r.content) / 1e6:.2f} Mo ecrits dans {out}")
        break
    except Exception as exc:
        print(f"Echec {i}/6 sur {url} : {str(exc)[:120]}")
        if i == 6:
            raise SystemExit("Echec : reessayez dans quelques minutes.")
        print(f"  Nouvelle tentative dans {wait} s...")
        time.sleep(wait)
        wait = min(wait * 2, 120)