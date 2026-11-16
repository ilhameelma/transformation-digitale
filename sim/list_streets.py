"""
list_streets.py - liste les rues principales de la zone pour choisir celle a fermer
(scenario 2). Lit data/network_edges.geojson, regroupe les troncons par nom de rue
et affiche un classement. Ecrit aussi data/rues_principales.csv.

Usage : python list_streets.py [--data dossier] [--top 20] [--all]
"""
import argparse
import ast
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

MAIN = ("motorway", "trunk", "primary", "secondary", "tertiary")


def default_data_dir():
    env = os.getenv("OUTPUT_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


def clean_name(raw):
    """'Avenue X', "['Avenue X', 'Rue Y']" ou None -> chaine lisible (apostrophes conservees)."""
    if raw in (None, "", "nan", "None"):
        return "(sans nom)"
    s = str(raw).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            parts = ast.literal_eval(s)
            s = " / ".join(str(x) for x in parts)
        except (ValueError, SyntaxError):
            s = s.strip("[]")
    return s.strip() or "(sans nom)"


def best_type(highway):
    """Type le plus important trouve dans la valeur (peut etre une liste en texte)."""
    h = str(highway)
    for t in MAIN:
        if t in h:
            return t
    return "autre"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=default_data_dir())
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--all", action="store_true", help="inclure aussi les petites rues")
    args = p.parse_args()

    edges = json.loads((args.data / "network_edges.geojson").read_text(encoding="utf-8"))["features"]
    streets = defaultdict(lambda: {"length": 0.0, "n": 0, "type": "autre", "oneway": 0})
    for f in edges:
        pr = f["properties"]
        t = best_type(pr.get("highway"))
        if t == "autre" and not args.all:
            continue
        s = streets[clean_name(pr.get("name"))]
        s["length"] += float(pr.get("length") or 0)
        s["n"] += 1
        if t != "autre" and (s["type"] == "autre" or MAIN.index(t) < MAIN.index(s["type"])):
            s["type"] = t
        if str(pr.get("oneway")).lower() == "true":
            s["oneway"] += 1

    rows = sorted(streets.items(), key=lambda kv: (kv[1]["type"] == "autre",
                  MAIN.index(kv[1]["type"]) if kv[1]["type"] != "autre" else 9, -kv[1]["length"]))
    out = []
    for name, s in rows:
        out.append([name, s["type"], round(s["length"]), s["n"], f'{100 * s["oneway"] // max(s["n"], 1)}%'])

    csv_path = args.data / "rues_principales.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["rue", "type", "longueur_m", "troncons", "sens_unique"])
        w.writerows(out)

    head = ["#", "rue", "type", "longueur (m)", "troncons", "sens unique"]
    shown = out[: args.top]
    table = [[i + 1] + r for i, r in enumerate(shown)]
    widths = [max(len(str(r[i])) for r in [head] + table) for i in range(len(head))]
    fmt = lambda r: "  ".join(str(v).ljust(w) for v, w in zip(r, widths))
    print(fmt(head)); print("  ".join("-" * w for w in widths))
    for r in table:
        print(fmt(r))
    print(f"\n{len(out)} rues au total -> liste complete : {csv_path}")
    print("Pour le scenario 'rue fermee', cherchez un axe PRIMARY ou SECONDARY, long (>= 500 m),")
    print("avec des rues paralleles proches. Verifiez-le sur comparaison.html (clic sur la rue).")


if __name__ == "__main__":
    main()