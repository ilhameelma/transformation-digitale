"""
enrich_buildings.py - enrichit buildings.geojson avec les hauteurs de Google Open Buildings 2.5D Temporal.

Etapes :
  1. lit <data>/buildings.geojson (doit contenir osm_id, height, height_source : voir extract_zone.py)
  2. pour chaque batiment, calcule la hauteur mediane des pixels `building_height` de l'annee choisie
     (pixels filtres par `building_presence`) via Google Earth Engine
  3. VALIDATION : compare Google aux hauteurs OSM reelles (height_source == "osm_height")
  4. remplace seulement les hauteurs "default" par la valeur Google (height_source = "google_2.5d")
  5. ecrit <data>/buildings_enriched.geojson et <data>/enrich_report.json (chiffres pour le rapport)

Le fichier d'origine n'est jamais modifie.

Prerequis (hors requirements.txt, script optionnel) :
  pip install earthengine-api
  earthengine authenticate
  un projet Google Cloud enregistre pour Earth Engine (--project ou variable EE_PROJECT)

Usage :
  python enrich_buildings.py --data ../data/test_height --project mon-projet-gcp
  python enrich_buildings.py --data ../data/test_height --project mon-projet-gcp --validate-only

Donnees : Open Buildings 2.5D Temporal (Google Research), CC-BY 4.0 / ODbL. A citer dans le rapport.
"""
import argparse
import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import mapping

COLLECTION = "GOOGLE/Research/open-buildings-temporal/v1"


def default_data_dir():
    env = os.getenv("OUTPUT_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


def init_earth_engine(project):
    try:
        import ee
    except ImportError:
        raise SystemExit("earthengine-api manquant : pip install earthengine-api")
    try:
        ee.Initialize(project=project)
    except Exception as exc:
        raise SystemExit(
            f"Earth Engine non initialise ({str(exc)[:150]}).\n"
            "Lancez d'abord : earthengine authenticate\n"
            "et donnez un projet Google Cloud enregistre pour Earth Engine (--project ou EE_PROJECT)."
        )
    return ee


def sample_heights(ee, gdf, year, scale, presence_min, batch):
    """Retourne {osm_id: (hauteur mediane ou None, nombre de pixels utilises)}."""
    col = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year + 1}-01-01")
    if col.size().getInfo() == 0:
        raise SystemExit(f"Aucune image Open Buildings pour {year} (donnees disponibles de 2016 a 2023).")
    img = col.mosaic()
    height = img.select("building_height").updateMask(img.select("building_presence").gte(presence_min))
    reducer = ee.Reducer.median().combine(ee.Reducer.count(), sharedInputs=True)

    feats = []
    for osm_id, geom in zip(gdf["osm_id"], gdf.geometry):
        g = ee.Geometry(json.loads(json.dumps(mapping(geom))), None, False)
        feats.append(ee.Feature(g, {"osm_id": osm_id}))

    out = {}
    for i in range(0, len(feats), batch):
        fc = ee.FeatureCollection(feats[i:i + batch])
        res = height.reduceRegions(collection=fc, reducer=reducer, scale=scale).getInfo()
        for f in res["features"]:
            p = f["properties"]
            out[p["osm_id"]] = (p.get("median"), int(p.get("count") or 0))
        print(f"  {min(i + batch, len(feats))}/{len(feats)} batiments traites", flush=True)
    return out


def validate(gdf):
    """Compare Google aux hauteurs OSM reelles. Retourne un dict de statistiques (ou None)."""
    ref = gdf[(gdf["height_source"] == "osm_height") & gdf["height_google"].notna()]
    if len(ref) < 5:
        print("Validation impossible : moins de 5 batiments avec hauteur OSM et valeur Google.")
        return None
    err = ref["height_google"] - ref["height"]
    stats = {
        "n_compares": int(len(ref)),
        "biais_moyen_m": round(float(err.mean()), 2),
        "erreur_absolue_moyenne_m": round(float(err.abs().mean()), 2),
        "erreur_absolue_mediane_m": round(float(err.abs().median()), 2),
        "part_ecart_inf_3m_pct": round(100 * float((err.abs() <= 3).mean())),
        "correlation": round(float(np.corrcoef(ref["height"], ref["height_google"])[0, 1]), 2),
    }
    print("\n=== Validation : Google vs hauteurs OSM reelles ===")
    print(f"  batiments compares        : {stats['n_compares']}")
    print(f"  biais moyen (Google - OSM): {stats['biais_moyen_m']} m  (negatif = Google sous-estime)")
    print(f"  erreur absolue moyenne    : {stats['erreur_absolue_moyenne_m']} m")
    print(f"  erreur absolue mediane    : {stats['erreur_absolue_mediane_m']} m")
    print(f"  ecart <= 3 m              : {stats['part_ecart_inf_3m_pct']} %")
    print(f"  correlation               : {stats['correlation']}")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=default_data_dir(), help="dossier contenant buildings.geojson")
    ap.add_argument("--project", default=os.getenv("EE_PROJECT"), help="projet Google Cloud pour Earth Engine")
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--scale", type=float, default=4, help="echelle d'echantillonnage en m (resolution effective : 4)")
    ap.add_argument("--presence-min", type=float, default=0.5, help="seuil de confiance building_presence")
    ap.add_argument("--min-pixels", type=int, default=3, help="pixels minimum dans le batiment pour accepter la valeur")
    ap.add_argument("--min-height", type=float, default=3.0, help="hauteur minimale acceptee (m)")
    ap.add_argument("--batch", type=int, default=400)
    ap.add_argument("--validate-only", action="store_true", help="calcule la validation sans remplacer de hauteur")
    args = ap.parse_args()

    src = args.data / "buildings.geojson"
    gdf = gpd.read_file(src)
    for col in ("osm_id", "height", "height_source"):
        if col not in gdf.columns:
            raise SystemExit(f"Colonne '{col}' absente de {src} : regenerez les batiments avec extract_zone.py modifie.")
    print(f"{len(gdf)} batiments lus dans {src}")
    print("Sources avant :", gdf["height_source"].value_counts().to_dict())

    ee = init_earth_engine(args.project)
    print(f"Interrogation d'Open Buildings 2.5D Temporal ({args.year})...")
    res = sample_heights(ee, gdf, args.year, args.scale, args.presence_min, args.batch)

    gdf["height_google"] = [res.get(i, (None, 0))[0] for i in gdf["osm_id"]]
    gdf["height_google_pixels"] = [res.get(i, (None, 0))[1] for i in gdf["osm_id"]]
    gdf["height_google"] = gdf["height_google"].astype(float).round(1)
    n_found = int(gdf["height_google"].notna().sum())
    print(f"\nHauteur Google trouvee pour {n_found}/{len(gdf)} batiments")

    stats = validate(gdf)

    n_replaced = 0
    if not args.validate_only:
        ok = (
            (gdf["height_source"] == "default")
            & gdf["height_google"].notna()
            & (gdf["height_google_pixels"] >= args.min_pixels)
            & (gdf["height_google"] >= args.min_height)
        )
        n_replaced = int(ok.sum())
        gdf.loc[ok, "height"] = gdf.loc[ok, "height_google"]
        gdf.loc[ok, "height_source"] = "google_2.5d"
        print(f"\nHauteurs 'default' remplacees par Google : {n_replaced}")

    after = gdf["height_source"].value_counts().to_dict()
    print("Sources apres :", {k: f"{v} ({100 * v / len(gdf):.0f} %)" for k, v in after.items()})

    out = args.data / "buildings_enriched.geojson"
    gdf.to_file(out, driver="GeoJSON")
    report = {
        "annee": args.year, "seuil_presence": args.presence_min, "pixels_min": args.min_pixels,
        "n_batiments": len(gdf), "n_hauteur_google_trouvee": n_found, "n_default_remplaces": n_replaced,
        "sources_apres": after, "validation_vs_osm": stats,
        "source": "Open Buildings 2.5D Temporal, Google Research (CC-BY 4.0 / ODbL)",
    }
    (args.data / "enrich_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEcrit : {out}\nEcrit : {args.data / 'enrich_report.json'}")


if __name__ == "__main__":
    main()
