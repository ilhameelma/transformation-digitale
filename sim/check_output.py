"""
check_output.py - verifie que le livrable M1 est correct.
Usage : python check_output.py [--out dossier]
Code de sortie 0 = OK, 1 = probleme.
"""
import argparse
import json
import os
import sys
from pathlib import Path

FILES = ["network.graphml", "network_edges.geojson", "network_nodes.geojson",
         "buildings.geojson", "zone.json"]


def default_out_dir():
    env = os.getenv("OUTPUT_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=default_out_dir())
    out = p.parse_args().out

    errors = []
    for f in FILES:
        path = out / f
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"fichier manquant ou vide : {f}")
    if errors:
        print("\n".join("ERREUR " + e for e in errors))
        sys.exit(1)

    meta = json.loads((out / "zone.json").read_text(encoding="utf-8"))
    if not 1.0 <= meta["area_km2"] <= 3.0:
        errors.append(f"surface {meta['area_km2']} km2 hors de 1 a 3 km2")
    if meta["n_edges"] < 10:
        errors.append(f"trop peu de rues ({meta['n_edges']})")
    if meta["n_buildings"] < 10:
        errors.append(f"trop peu de batiments ({meta['n_buildings']})")

    b = json.loads((out / "buildings.geojson").read_text(encoding="utf-8"))
    bad = [x for x in b["features"] if not isinstance(x["properties"].get("height"), (int, float))]
    if bad:
        errors.append(f"{len(bad)} batiments sans hauteur valide")

    if errors:
        print("\n".join("ERREUR " + e for e in errors))
        sys.exit(1)
    print(f"OK : {meta['area_km2']} km2, {meta['n_nodes']} intersections, "
          f"{meta['n_edges']} troncons, {meta['n_buildings']} batiments")


if __name__ == "__main__":
    main()