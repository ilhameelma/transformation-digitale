"""
compute_kpi.py - M4 : les 4 indicateurs a partir des sorties SUMO.

Lit    : data/tripinfo.xml, data/edgedata.xml
Ecrit  : data/kpi_<scenario>.json

Indicateurs (voir README, section 7) :
  1. temps_trajet_moyen_s   = moyenne de `duration` (tripinfo)
  2. vitesse_moyenne_kmh    = moyenne de routeLength/duration * 3,6 (tripinfo)
  3. congestion_par_rue     = part des intervalles de 60 s ou speedRelative < SEUIL,
                              parmi les intervalles ou la rue a eu des vehicules ;
                              rues avec moins de MIN_MESURES intervalles ignorees
  4. co2_total_g            = somme de CO2_abs (mg) / 1000

Usage : python compute_kpi.py [--scenario actuel] [--seuil 0.5] [--min-mesures 3]
"""
import argparse
import json
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

DATA = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parent.parent / "data")


def trip_kpi(path):
    n = 0
    duree = vitesse = co2_mg = 0.0
    for _, el in ET.iterparse(path):
        if el.tag == "tripinfo":
            d = float(el.get("duration"))
            if d > 0:
                n += 1
                duree += d
                vitesse += float(el.get("routeLength")) / d * 3.6
                em = el.find("emissions")
                if em is not None:
                    co2_mg += float(em.get("CO2_abs", 0))
            el.clear()
    if n == 0:
        raise SystemExit("Aucun trajet termine dans tripinfo.xml")
    return {
        "trajets_termines": n,
        "temps_trajet_moyen_s": round(duree / n, 1),
        "vitesse_moyenne_kmh": round(vitesse / n, 1),
        "co2_total_g": round(co2_mg / 1000),
    }


def congestion(path, seuil, min_mesures):
    mesures, lents = defaultdict(int), defaultdict(int)
    for _, el in ET.iterparse(path):
        if el.tag == "edge" and el.get("speedRelative") is not None:
            e = el.get("id")
            mesures[e] += 1
            if float(el.get("speedRelative")) < seuil:
                lents[e] += 1
            el.clear()
    taux = {e: round(lents[e] / m, 3) for e, m in mesures.items() if m >= min_mesures}
    moy = round(sum(taux.values()) / len(taux), 3) if taux else None
    return {"congestion_moyenne": moy, "rues_mesurees": len(taux), "congestion_par_rue": taux}


def pick(nom, scenario):
    """Fichier propre au scenario s'il existe, sinon le fichier SUMO par defaut."""
    p = DATA / f"{nom}_{scenario}.xml"
    return p if p.exists() else DATA / f"{nom}.xml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="actuel")
    ap.add_argument("--seuil", type=float, default=0.5)
    ap.add_argument("--min-mesures", type=int, default=3)
    ap.add_argument("--tripinfo", help="defaut : tripinfo_<scenario>.xml, sinon tripinfo.xml")
    ap.add_argument("--edgedata", help="defaut : edgedata_<scenario>.xml, sinon edgedata.xml")
    args = ap.parse_args()

    kpi = {"scenario": args.scenario, "donnees": "simulees (SUMO)",
           "seuil_congestion": args.seuil, "min_mesures": args.min_mesures}
    trip = Path(args.tripinfo) if args.tripinfo else pick("tripinfo", args.scenario)
    edge = Path(args.edgedata) if args.edgedata else pick("edgedata", args.scenario)
    kpi.update(trip_kpi(trip))
    kpi.update(congestion(edge, args.seuil, args.min_mesures))

    out = DATA / f"kpi_{args.scenario}.json"
    out.write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{kpi['trajets_termines']} trajets | duree moy. {kpi['temps_trajet_moyen_s']} s | "
          f"vitesse moy. {kpi['vitesse_moyenne_kmh']} km/h | CO2 {kpi['co2_total_g']} g | "
          f"congestion moy. {kpi['congestion_moyenne']} sur {kpi['rues_mesurees']} rues")
    print(f"-> {out}")


if __name__ == "__main__":
    main()