"""
compare_zones.py - compare plusieurs zones extraites (M1).
Usage : python compare_zones.py [dossier_parent]   (defaut : <depot>/data_test)
Cherche <dossier_parent>/<nom>/zone.json et affiche un tableau.
"""
import json
import sys
from pathlib import Path

MAIN_ROADS = ("motorway", "trunk", "primary", "secondary", "tertiary")


def road_stats(edges_file):
    """Longueur totale (km) et part des axes principaux (%), via network_edges.geojson."""
    data = json.loads(edges_file.read_text(encoding="utf-8"))
    total = main = 0.0
    for f in data["features"]:
        pr = f["properties"]
        length = float(pr.get("length") or 0)
        total += length
        if any(t in str(pr.get("highway", "")) for t in MAIN_ROADS):
            main += length
    return total / 1000, (100 * main / total if total else 0)


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data_test"
    zones = sorted(p for p in root.glob("*/zone.json"))
    if not zones:
        raise SystemExit(f"Aucun zone.json trouve dans {root}\\*")

    rows = []
    for z in zones:
        m = json.loads(z.read_text(encoding="utf-8"))
        km, main_pct = road_stats(z.parent / "network_edges.geojson")
        a = m["area_km2"]
        rows.append([z.parent.name, a, m["n_nodes"], m["n_edges"], round(km, 1),
                     round(main_pct), m["n_buildings"], round(m["n_buildings"] / a)])

    head = ["zone", "km2", "carrefours", "troncons", "route km", "% axes princ.", "batiments", "bat./km2"]
    widths = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    line = lambda r: "  ".join(str(v).ljust(w) for v, w in zip(r, widths))
    print(line(head)); print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))
    print("\nA verifier a la main : batiments bien places (geojson.io), axe a fermer + alternatives.")


if __name__ == "__main__":
    main()