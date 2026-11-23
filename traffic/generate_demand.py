"""
generate_demand.py - M4 : demande de trafic simulee (pics du matin et du soir).

Lit    : data/hassan.net.xml (reseau SUMO)
Ecrit  : data/demand.csv  (colonnes : id, depart, origin_edge, destination_edge, periode)
         data/demand.rou.xml (optionnel, trips SUMO a passer a duarouter)

Profil horaire : un vehicule est tire au hasard selon un poids par heure.
Pic du matin 7h-9h, pic du soir 17h-19h, trafic faible le reste du temps.
La simulation SUMO ne dure que quelques minutes : on la cale sur une fenetre
(WINDOW_START .. WINDOW_START + DURATION) de la journee, par defaut le pic du matin.

Usage : python generate_demand.py [--n 500] [--window morning|evening|day] [--scale 1.0] [--seed 42]
"""
import argparse
import csv
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path

DATA = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

# Poids relatif de la demande par heure (0..23) : valeurs simulees, a documenter dans docs/
HOURLY_WEIGHT = {
    0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.2, 5: 0.5, 6: 1.5,
    7: 4.0, 8: 5.0, 9: 3.0,            # pic du matin
    10: 2.0, 11: 2.0, 12: 2.5, 13: 2.5, 14: 2.0, 15: 2.2, 16: 3.0,
    17: 4.5, 18: 5.0, 19: 3.0,         # pic du soir
    20: 1.5, 21: 1.0, 22: 0.6, 23: 0.3,
}
WINDOWS = {"morning": (7, 9), "evening": (17, 19), "day": (0, 24)}


def drivable_edges(net_path):
    """Rues utilisables par une voiture (hors edges internes aux carrefours)."""
    edges = []
    for _, el in ET.iterparse(net_path):
        if el.tag == "edge" and el.get("function") != "internal":
            lanes = el.findall("lane")
            ok = any(l.get("allow") is None or "passenger" in l.get("allow") for l in lanes)
            if lanes and ok and float(lanes[0].get("length", 0)) > 20:
                edges.append(el.get("id"))
            el.clear()
    return edges


def classify(hour):
    if 7 <= hour < 9:
        return "pic_matin"
    if 17 <= hour < 19:
        return "pic_soir"
    return "hors_pic"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="vehicules avant mise a l'echelle")
    ap.add_argument("--window", choices=WINDOWS, default="morning")
    ap.add_argument("--duration", type=int, default=900, help="duree simulee (s), comme hassan.sumocfg")
    ap.add_argument("--scale", type=float, default=1.0, help="1.3 = scenario pic de trafic +30 %%")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(DATA / "demand.csv"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    edges = drivable_edges(DATA / "hassan.net.xml")
    if len(edges) < 2:
        raise SystemExit("Reseau vide ou introuvable : lance d'abord le conteneur sim (M1).")

    h0, h1 = WINDOWS[args.window]
    hours = list(range(h0, h1))
    weights = [HOURLY_WEIGHT[h] for h in hours]
    total = round(args.n * args.scale)

    rows = []
    for _ in range(total):
        hour = rng.choices(hours, weights)[0]
        minute = rng.random() * 60
        # depart en secondes depuis le debut de la fenetre, replie sur la duree simulee
        depart = ((hour - h0) * 3600 + minute * 60) % args.duration
        o, d = rng.sample(edges, 2)
        rows.append((depart, o, d, classify(hour)))
    rows.sort()

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "depart", "origin_edge", "destination_edge", "periode"])
        for i, (t, o, d, p) in enumerate(rows):
            w.writerow([i, f"{t:.1f}", o, d, p])

    trips = Path(args.out).with_suffix(".trips.xml")
    with open(trips, "w", encoding="utf-8") as f:
        f.write('<routes>\n')
        for i, (t, o, d, _) in enumerate(rows):
            f.write(f'    <trip id="{i}" depart="{t:.1f}" from="{o}" to="{d}"/>\n')
        f.write('</routes>\n')

    print(f"{len(rows)} vehicules ({args.window}, x{args.scale}) -> {args.out}")
    print(f"trips SUMO -> {trips}  (duarouter -n hassan.net.xml --route-files {trips.name} -o demand.rou.xml --ignore-errors)")


if __name__ == "__main__":
    main()