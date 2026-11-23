"""Vue 3D du jumeau numérique : bâtiments extrudés + trajets SUMO animés.

Lit les fichiers de l'équipe dans le dossier de données :
  - buildings.geojson          (produit par M1)
  - trajectories_actuel.json   (produit par M2, via fcd_to_json.py)

Dossier de données, dans l'ordre : variable DATA_DIR, /data (Docker), viz/data, ../data (racine du dépôt).
Si un fichier manque, des données factices sont utilisées et signalées à l'écran.
"""
import json
import os
import random
import time
from pathlib import Path

import pydeck as pdk
import streamlit as st

try:  # optionnel : permet le test « voiture dans un bâtiment »
    import numpy as np
    from shapely.geometry import Polygon
    from shapely import STRtree, points as shp_points
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

# --- Config ------------------------------------------------------------------
DEFAULT_LAT, DEFAULT_LON = 34.0209, -6.8416   # Rabat, utilisé seulement sans données
MAP_STYLE = "dark"                            # fond Carto, sans token
COLORS = [[253, 128, 93], [23, 184, 190], [255, 220, 80]]


def find_data_dir() -> Path:
    env = os.getenv("DATA_DIR")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve().parent
    for cand in (Path("/data"), here / "data", here.parent / "data"):
        if cand.exists():
            return cand
    return here / "data"


DATA_DIR = find_data_dir()
BUILDINGS_FILE = DATA_DIR / "buildings.geojson"
TRAJ_FILE = DATA_DIR / "trajectories_actuel.json"
CLOSURE_FILE = DATA_DIR / "closure.geojson"
SCENARIOS = {"Situation actuelle": "actuel", "Rue fermée": "rue_fermee"}

st.set_page_config(page_title="Jumeau numérique 3D", layout="wide")
st.title("Jumeau numérique 3D : test de la vue")


# --- Utilitaires -------------------------------------------------------------
def flat_coords(c):
    if c and isinstance(c[0], (int, float)):
        yield c
    else:
        for s in c:
            yield from flat_coords(s)


def bbox_of_points(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# --- Bâtiments ---------------------------------------------------------------
def fake_buildings(n=14, step=0.0007, size=0.0004):
    random.seed(1)
    feats = []
    for i in range(n):
        for j in range(n):
            x = DEFAULT_LON + (i - n / 2) * step
            y = DEFAULT_LAT + (j - n / 2) * step
            ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]
            feats.append({"type": "Feature",
                          "properties": {"height": random.randint(6, 45)},
                          "geometry": {"type": "Polygon", "coordinates": [ring]}})
    return {"type": "FeatureCollection", "features": feats}


@st.cache_data
def load_buildings(path_str: str, mtime: float):
    path = Path(path_str)
    if path.exists():
        gj = json.loads(path.read_text(encoding="utf-8"))
        source, real = f"GeoJSON réel : {path}", True
    else:
        gj, source, real = fake_buildings(), "bâtiments factices (buildings.geojson introuvable)", False
    random.seed(2)
    n_default = 0
    for f in gj["features"]:
        p = f.get("properties") or {}
        f["properties"] = p
        h = None
        try:
            if p.get("height"):
                h = float(str(p["height"]).replace("m", "").strip())
            elif p.get("building:levels"):
                h = float(p["building:levels"]) * 3
        except ValueError:
            h = None
        if not h:
            h = random.randint(8, 20)
            n_default += 1
        p["height"] = h
    return gj, source, real, n_default


# --- Trajets -----------------------------------------------------------------
def fake_trips(n=60, steps=40, step=0.0007):
    random.seed(3)
    trips = []
    for _ in range(n):
        x = DEFAULT_LON + random.randint(-7, 7) * step
        y = DEFAULT_LAT + random.randint(-7, 7) * step
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        path, ts = [], []
        t0 = random.randint(0, 200)
        for k in range(steps):
            path.append([x, y])
            ts.append(t0 + k * 10)
            if random.random() < 0.2:
                dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            x += dx * step
            y += dy * step
        trips.append({"id": str(len(trips)), "path": path, "timestamps": ts,
                      "color": random.choice(COLORS)})
    return trips


@st.cache_data
def load_trips(path_str: str, mtime: float):
    """Convertit [{id, path:[[lon,lat,t],...]}] en format TripsLayer (path + timestamps)."""
    path = Path(path_str)
    if not path.exists():
        return fake_trips(), "trajets factices (trajectories_actuel.json introuvable)", False
    raw = json.loads(path.read_text(encoding="utf-8"))
    trips = []
    for i, v in enumerate(raw):
        if "timestamps" in v:
            pts, ts = [p[:2] for p in v["path"]], list(v["timestamps"])
        else:
            pts, ts = [[p[0], p[1]] for p in v["path"]], [p[2] for p in v["path"]]
        if len(pts) >= 2:
            trips.append({"id": str(v.get("id", i)), "path": pts, "timestamps": ts,
                          "color": COLORS[i % len(COLORS)]})
    return trips, f"SUMO réel : {path}", True


# --- Chargement --------------------------------------------------------------
def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


buildings, b_source, b_real, b_default_h = load_buildings(str(BUILDINGS_FILE), mtime(BUILDINGS_FILE))
trips, t_source, t_real = load_trips(str(TRAJ_FILE), mtime(TRAJ_FILE))

b_pts = [p for f in buildings["features"] for p in flat_coords(f["geometry"]["coordinates"])]
b_bbox = bbox_of_points(b_pts)

# Centre : variables d'environnement, sinon centre des bâtiments
center_lon = float(os.getenv("CENTER_LON", (b_bbox[0] + b_bbox[2]) / 2))
center_lat = float(os.getenv("CENTER_LAT", (b_bbox[1] + b_bbox[3]) / 2))

t_min = min(t for tr in trips for t in tr["timestamps"])
t_max = int(max(t for tr in trips for t in tr["timestamps"]))

view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=15.5, pitch=55, bearing=20)


def building_layer():
    return pdk.Layer("GeoJsonLayer", buildings, extruded=True, wireframe=False,
                     get_elevation="properties.height", get_fill_color=[160, 170, 190, 220],
                     pickable=True)


def trips_layer(t, data=None):
    return pdk.Layer("TripsLayer", data if data is not None else trips,
                     get_path="path", get_timestamps="timestamps",
                     get_color="color", width_min_pixels=4, rounded=True,
                     trail_length=150, current_time=t)


@st.cache_data
def load_closure(path_str: str, mtime: float):
    path = Path(path_str)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def closure_layer(closure):
    """Section de rue fermee, en rouge epais."""
    return pdk.Layer("GeoJsonLayer", closure, stroked=True, filled=False,
                     get_line_color=[255, 40, 40], line_width_min_pixels=8,
                     get_line_width=10)


def load_kpi(scenario):
    p = DATA_DIR / f"kpi_{scenario}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def deck(layers):
    return pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto",
                    map_style=MAP_STYLE, tooltip={"text": "Hauteur : {height} m"})


# --- Contrôles ---------------------------------------------------------------
def run_checks():
    res = []  # (niveau, texte) ; niveau : ok / warn / err

    # Bâtiments
    types = {f["geometry"]["type"] for f in buildings["features"]}
    res.append(("ok" if b_real else "warn", f"{len(buildings['features'])} bâtiments, géométries : {sorted(types)}"))
    res.append(("ok" if b_default_h == 0 else "warn",
                f"{b_default_h} bâtiment(s) sans hauteur (valeur aléatoire 8-20 m appliquée)"))
    hs = sorted({f["properties"]["height"] for f in buildings["features"]})
    if len(hs) <= 25:
        res.append(("warn", f"Seulement {len(hs)} hauteurs différentes : probablement des valeurs par défaut, à signaler dans le rapport"))
    lon_ok = all(-180 <= p[0] <= 180 for p in b_pts) and all(-90 <= p[1] <= 90 for p in b_pts)
    swapped = (b_bbox[0] > 30 and b_bbox[1] < 0)  # lon/lat inversés pour le Maroc
    res.append(("err" if (not lon_ok or swapped) else "ok", "Ordre des coordonnées [lon, lat] valide"))

    # Trajets
    pts = [p for tr in trips for p in tr["path"]]
    res.append(("ok" if t_real else "warn",
                f"{len(trips)} véhicules, {len(pts)} points, temps de {t_min:.0f} à {t_max} s"))
    bad_order = sum(1 for tr in trips if any(b < a for a, b in zip(tr["timestamps"], tr["timestamps"][1:])))
    res.append(("ok" if bad_order == 0 else "err", f"{bad_order} trajet(s) avec temps non croissants"))

    # Emprise
    tx0, ty0, tx1, ty1 = bbox_of_points(pts)
    m = 0.0003  # marge ~30 m
    inside = sum(1 for p in pts if b_bbox[0] - m <= p[0] <= b_bbox[2] + m and b_bbox[1] - m <= p[1] <= b_bbox[3] + m)
    pct = 100 * inside / len(pts)
    res.append(("ok" if pct >= 99 else "warn" if pct >= 90 else "err",
                f"{pct:.1f} % des points de trajet sont dans la zone des bâtiments "
                f"(trajets : lat {ty0:.4f}-{ty1:.4f}, lon {tx0:.4f}-{tx1:.4f} ; "
                f"bâtiments : lat {b_bbox[1]:.4f}-{b_bbox[3]:.4f}, lon {b_bbox[0]:.4f}-{b_bbox[2]:.4f})"))

    # Voitures dans les bâtiments
    if HAS_SHAPELY:
        polys = [Polygon(f["geometry"]["coordinates"][0]) for f in buildings["features"]
                 if f["geometry"]["type"] == "Polygon"]
        sample = pts[::5]
        tree = STRtree(polys)
        arr = np.array(sample)
        hit = tree.query(shp_points(arr[:, 0], arr[:, 1]), predicate="within")
        n_in = len(set(hit[0].tolist()))
        p_in = 100 * n_in / len(sample)
        res.append(("ok" if p_in < 2 else "warn" if p_in < 10 else "err",
                    f"{p_in:.1f} % des points (échantillon) tombent dans un bâtiment"))
    else:
        res.append(("warn", "shapely non installé : test « voiture dans un bâtiment » ignoré (pip install shapely)"))
    return res


# --- Interface ---------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["1. Bâtiments 3D", "2. Trajets animés", "3. Contrôles"])

with tab1:
    st.caption(f"Source : {b_source} ({len(buildings['features'])} bâtiments)")
    st.pydeck_chart(deck([building_layer()]))

with tab2:
    choix = st.radio("Situation", list(SCENARIOS), horizontal=True)
    scen = SCENARIOS[choix]
    if scen == "actuel":
        sc_trips, sc_source, sc_real = trips, t_source, t_real
    else:
        f = DATA_DIR / f"trajectories_{scen}.json"
        if not f.exists():
            st.warning(f"{f.name} introuvable : lance `docker compose run --rm traffic "
                       f"python run_scenario.py {scen}` puis recharge la page.")
            st.stop()
        sc_trips, sc_source, sc_real = load_trips(str(f), mtime(f))
    sc_tmax = int(max(t for tr in sc_trips for t in tr["timestamps"]))

    closure = load_closure(str(CLOSURE_FILE), mtime(CLOSURE_FILE)) if scen == "rue_fermee" else None
    if scen == "rue_fermee":
        if closure:
            st.error("🚧 Avenue Allal Ben Abdellah fermée (section en rouge sur la carte)")
        else:
            st.warning("closure.geojson introuvable : la rue fermée ne peut pas être dessinée.")

    kpi = load_kpi(scen)
    if kpi:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temps de trajet moyen", f"{kpi['temps_trajet_moyen_s']:.0f} s")
        c2.metric("Vitesse moyenne", f"{kpi['vitesse_moyenne_kmh']:.1f} km/h")
        c3.metric("Congestion moyenne", f"{kpi['congestion_moyenne'] * 100:.0f} %")
        c4.metric("CO₂ total", f"{kpi['co2_total_g'] / 1000:.0f} kg")

    st.caption(f"Source : {sc_source} ({len(sc_trips)} véhicules)")
    t = st.slider("Temps (s)", 0, sc_tmax, 0, step=5, key=f"t_{scen}")

    def layers_at(tt):
        ls = [building_layer()]
        if closure:
            ls.append(closure_layer(closure))
        ls.append(trips_layer(tt, sc_trips))
        return ls

    slot = st.empty()
    slot.pydeck_chart(deck(layers_at(t)))
    if st.button("▶ Lecture automatique"):
        for tt in range(0, sc_tmax, 5):
            slot.pydeck_chart(deck(layers_at(tt)))
            time.sleep(0.15)

with tab3:
    st.caption(f"Dossier de données : {DATA_DIR}")
    icons = {"ok": "✅", "warn": "⚠️", "err": "❌"}
    for level, text in run_checks():
        st.write(f"{icons[level]} {text}")