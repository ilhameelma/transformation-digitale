"""
extract_zone.py - M1 : telecharge la zone de Rabat depuis OpenStreetMap
et ecrit dans le dossier de sortie (par defaut <depot>/data) :
  - network.graphml        reseau routier
  - network_edges.geojson  rues (lignes)
  - network_nodes.geojson  intersections (points)
  - buildings.geojson      batiments avec une propriete "height" (3D)
  - zone.json              metadonnees (emprise, surface, compteurs)

Choix de la zone, par ordre de priorite :
  1. --bbox "ouest,sud,est,nord"
  2. --zone "Agdal, Rabat, Maroc"  (+ --half-side)
  3. --lat / --lon                 (+ --half-side)

Marche avec des arguments (sans Docker) ou des variables d'environnement
(Docker) : BBOX, ZONE_NAME, CENTER_LAT, CENTER_LON, HALF_SIDE_M,
NETWORK_TYPE, OUTPUT_DIR.
"""
import argparse
import json
import math
import os
import time
from pathlib import Path

import osmnx as ox

DEFAULT_HEIGHT_M = 10.0   # hauteur par defaut si OSM n'a pas l'info
LEVEL_HEIGHT_M = 3.0      # hauteur d'un etage


# Serveurs Overpass publics, essayes a tour de role si l'un est ssature (erreur 502/504)
OVERPASS_SERVERS = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://overpass.private.coffee/api",
]


def with_retry(func, *args, attempts=6, first_wait=10, servers=None, **kwargs):
    """Appelle func ; en cas d'erreur reseau/serveur, attend puis reessaie
    (attente x2 a chaque fois) en changeant de serveur Overpass."""
    servers = servers or OVERPASS_SERVERS
    wait = first_wait
    for i in range(1, attempts + 1):
        ox.settings.overpass_url = servers[(i - 1) % len(servers)]
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # erreurs HTTP, timeout, JSON invalide...
            msg = str(exc).splitlines()[0][:120]
            print(f"  Echec {i}/{attempts} sur {ox.settings.overpass_url} : {msg}")
            if i == attempts:
                raise
            print(f"  Nouvelle tentative dans {wait} s...")
            time.sleep(wait)
            wait = min(wait * 2, 120)


def default_out_dir():
    """OUTPUT_DIR si defini (Docker), sinon <depot>/data (dossier parent de sim/)."""
    env = os.getenv("OUTPUT_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


def compute_bbox(lat, lon, half_side_m):
    """Retourne (ouest, sud, est, nord) autour d'un centre."""
    dlat = half_side_m / 111_320
    dlon = half_side_m / (111_320 * math.cos(math.radians(lat)))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def bbox_area_km2(bbox):
    west, south, east, north = bbox
    mid_lat = (south + north) / 2
    height_km = (north - south) * 111.32
    width_km = (east - west) * 111.32 * math.cos(math.radians(mid_lat))
    return height_km * width_km


def _to_float(value):
    """Convertit '12', '12 m', 12.5 en float ; None si impossible ou NaN."""
    try:
        x = float(str(value).lower().replace("m", "").strip())
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def building_height(row):
    """Hauteur en metres : tag height, sinon building:levels x 3, sinon defaut."""
    h = _to_float(row.get("height"))
    if h is not None and h > 0:
        return h
    levels = _to_float(row.get("building:levels"))
    if levels is not None and levels > 0:
        return levels * LEVEL_HEIGHT_M
    return DEFAULT_HEIGHT_M


def stringify_lists(gdf):
    """GeoJSON n'accepte pas les listes : on les convertit en texte."""
    for col in gdf.columns:
        if col != "geometry" and gdf[col].map(lambda v: isinstance(v, (list, dict))).any():
            gdf[col] = gdf[col].astype(str)
    return gdf


def parse_args():
    e = os.getenv
    p = argparse.ArgumentParser(description="Telecharge reseau + batiments d'une zone (OpenStreetMap).")
    p.add_argument("--bbox", default=e("BBOX"), help='"ouest,sud,est,nord"')
    p.add_argument("--zone", default=e("ZONE_NAME"), help='nom de lieu ou adresse, ex : "Agdal, Rabat, Maroc"')
    p.add_argument("--lat", type=float, default=float(e("CENTER_LAT", "34.0150")))
    p.add_argument("--lon", type=float, default=float(e("CENTER_LON", "-6.8350")))
    p.add_argument("--half-side", type=float, default=float(e("HALF_SIDE_M", "750")),
                   help="demi-cote du carre en metres (750 -> 2,25 km2)")
    p.add_argument("--network-type", default=e("NETWORK_TYPE", "drive"))
    p.add_argument("--overpass-url", default=e("OVERPASS_URL"),
                   help="serveur Overpass force (sinon rotation automatique)")
    p.add_argument("--out", type=Path, default=default_out_dir(), help="dossier de sortie")
    return p.parse_args()


def main():
    args = parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    # 0) Choix de la zone
    if args.bbox:
        bbox = tuple(float(x) for x in args.bbox.split(","))
        if len(bbox) != 4:
            raise SystemExit('--bbox doit etre "ouest,sud,est,nord"')
    else:
        lat, lon = args.lat, args.lon
        if args.zone:
            lat, lon = ox.geocode(args.zone)
            print(f"'{args.zone}' trouve : lat={lat:.5f}, lon={lon:.5f}")
        bbox = compute_bbox(lat, lon, args.half_side)

    area_km2 = bbox_area_km2(bbox)
    print(f"Zone (ouest, sud, est, nord) = {tuple(round(v, 5) for v in bbox)}")
    print(f"Surface = {area_km2:.2f} km2")
    if not 1.0 <= area_km2 <= 3.0:
        print("ATTENTION : surface hors de la fourchette 1 a 3 km2")

    ox.settings.requests_timeout = 180
    servers = [args.overpass_url] if args.overpass_url else None

    # 1) Reseau routier
    print("Telechargement du reseau routier...")
    G = with_retry(ox.graph_from_bbox, bbox, network_type=args.network_type,
                   simplify=True, servers=servers)
    ox.save_graphml(G, out / "network.graphml")
    nodes, edges = ox.graph_to_gdfs(G)
    nodes = stringify_lists(nodes.reset_index())
    edges = stringify_lists(edges.reset_index())
    edges.to_file(out / "network_edges.geojson", driver="GeoJSON")
    nodes.to_file(out / "network_nodes.geojson", driver="GeoJSON")
    print(f"  {len(nodes)} intersections, {len(edges)} troncons")

    # 2) Batiments
    print("Telechargement des batiments...")
    b = with_retry(ox.features_from_bbox, bbox, tags={"building": True}, servers=servers)
    b = b[b.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    b["height"] = b.apply(building_height, axis=1)
    keep = [c for c in ("name", "building", "height") if c in b.columns]
    b = b[keep + ["geometry"]].reset_index(drop=True)
    b.to_file(out / "buildings.geojson", driver="GeoJSON")
    print(f"  {len(b)} batiments")

    # 3) Metadonnees
    west, south, east, north = bbox
    meta = {
        "zone_name": args.zone,
        "center": {"lat": (south + north) / 2, "lon": (west + east) / 2},
        "bbox_west_south_east_north": bbox,
        "area_km2": round(area_km2, 2),
        "network_type": args.network_type,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "n_buildings": len(b),
        "source": "OpenStreetMap contributors (ODbL)",
    }
    (out / "zone.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Termine. Fichiers ecrits dans", out.resolve())


if __name__ == "__main__":
    main()