"""Vue 3D du jumeau numérique : bâtiments extrudés, rues colorées par congestion,
trafic SUMO animé (traînées colorées selon la vitesse), étiquettes KPI sur les rues les plus
congestionnées, ambiances jour / nuit / coucher de soleil, mode comparaison actuel / simulé.

Lit les fichiers de l'équipe dans le dossier de données :
  - buildings.geojson            (M1) bâtiments avec hauteur
  - hassan.net.xml               (M1) réseau SUMO : géométrie exacte des rues
  - network_edges.geojson        (M1) noms de rues (liés par l'identifiant OSM)
  - trajectories_<scenario>.json (M2) trajets des véhicules
  - kpi_<scenario>.json          (M4) indicateurs et congestion par rue
  - edgedata.xml                 (M2) sortie SUMO : vitesse moyenne et passages de véhicules par rue

Dossier de données, dans l'ordre : variable DATA_DIR, /data (Docker), viz/data, ../data (racine du dépôt).
Si un fichier manque, la couche correspondante est simplement absente (ou factice pour bâtiments/trajets).
"""
import ast
import json
import math
import os
import random
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
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

try:  # nécessaire pour placer les rues du réseau SUMO sur la carte
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

# --- Config ------------------------------------------------------------------
DEFAULT_LAT, DEFAULT_LON = 34.0209, -6.8416   # Rabat, utilisé seulement sans données
COLORS = [[253, 128, 93], [23, 184, 190], [255, 220, 80]]
HEIGHT_REF_M = 30.0        # hauteur à partir de laquelle la couleur des bâtiments est « au maximum »
SEG_POINTS = 4             # un trajet est découpé en tronçons de 4 points (~8 s) colorés selon leur vitesse
N_TOP = 5                  # nombre de rues mises en avant (étiquettes sur la carte + panneau)
POINT_STEP = 2             # on garde 1 point sur 2 (SUMO donne 1 point/s) pour alléger l'affichage

# Seuils d'étiquettes de congestion (part des intervalles de 60 s où la rue roule à moins de 50 % de sa vitesse libre)
CONGESTION_LEVELS = [(0.25, "Faible"), (0.5, "Modérée"), (0.75, "Élevée"), (1.01, "Sévère")]

# Ambiances : fond de carte, palette des bâtiments (bas -> haut), rue sans mesure, lumière
MODES = {
    "Nuit": dict(map_style="dark", b_lo=[52, 60, 84], b_hi=[135, 155, 205], b_alpha=235,
                 road_idle=[95, 105, 130, 110], sun=[170, 190, 255], sun_i=0.8, amb=0.55,
                 shadow=[0, 0, 20, 0.6]),
    "Jour": dict(map_style="light", b_lo=[214, 204, 188], b_hi=[150, 146, 142], b_alpha=240,
                 road_idle=[150, 150, 150, 120], sun=[255, 244, 225], sun_i=2.0, amb=0.9,
                 shadow=[40, 30, 20, 0.45]),
    "Coucher de soleil": dict(map_style="dark", b_lo=[96, 66, 78], b_hi=[255, 168, 112], b_alpha=235,
                              road_idle=[120, 100, 110, 110], sun=[255, 150, 80], sun_i=1.8, amb=0.5,
                              shadow=[30, 10, 20, 0.55]),
}


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
NET_FILE = DATA_DIR / "hassan.net.xml"
EDGES_FILE = DATA_DIR / "network_edges.geojson"

st.set_page_config(page_title="Jumeau numérique 3D", layout="wide")
st.title("Jumeau numérique 3D : Rabat Hassan")
st.caption("Données de trafic **simulées** (SUMO), pas des mesures réelles. "
           "Prototype pédagogique — Transformation digitale, Rabat.")


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


def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def lerp_color(c0, c1, t):
    t = max(0.0, min(1.0, t))
    return [round(a + (b - a) * t) for a, b in zip(c0, c1)]


def congestion_color(rate):
    """Bleu (fluide) -> orange -> rouge (saturé), comme une carte de trafic."""
    if rate < 0.4:
        return lerp_color([0, 200, 255], [255, 190, 0], rate / 0.4) + [230]
    return lerp_color([255, 190, 0], [255, 40, 40], (rate - 0.4) / 0.4) + [240]


def congestion_label(rate):
    for limit, label in CONGESTION_LEVELS:
        if rate < limit:
            return label
    return "Sévère"


def speed_color(kmh):
    """Rouge à l'arrêt/lent, orange, jaune, puis cyan quand ça roule bien."""
    if kmh < 8:
        return [255, 50, 50]
    if kmh < 20:
        return [255, 150, 40]
    if kmh < 35:
        return [255, 225, 80]
    return [60, 210, 255]


def meters_between(p, q):
    dx = (q[0] - p[0]) * 111_320 * math.cos(math.radians(p[1]))
    dy = (q[1] - p[1]) * 110_540
    return math.hypot(dx, dy)


def ascii_fold(text):
    """Enlève les accents : le texte des étiquettes sur la carte (TextLayer) ne supporte que l'ASCII par défaut."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def clean_street_name(raw):
    """Garde la partie latine du nom OSM (enlève l'arabe et les listes Python)."""
    if raw in (None, "", "nan", "None"):
        return ""
    s = str(raw).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            s = " / ".join(str(x) for x in ast.literal_eval(s))
        except (ValueError, SyntaxError):
            s = s.strip("[]")
    s = re.sub(r"[؀-ۿ]+", "", s)
    return re.sub(r"\s+", " ", s).strip(" /")


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
def load_buildings(path_str: str, mt: float):
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
        p["t"] = round(min(h / HEIGHT_REF_M, 1.0), 3)   # 0..1, précalculé
        p["tip"] = f"Bâtiment · hauteur {h:.0f} m"
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
def load_trips(path_str: str, mt: float):
    """Convertit [{id, path:[[lon,lat,t],...]}] en format TripsLayer (path + timestamps)."""
    path = Path(path_str)
    if not path.exists():
        return fake_trips(), "trajets factices (fichier de trajets introuvable)", False
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


@st.cache_data
def speed_segments(trips, seg_points=SEG_POINTS):
    """Découpe chaque trajet en petits tronçons, chacun coloré selon sa vitesse moyenne."""
    segs = []
    for tr in trips:
        idx = list(range(0, len(tr["path"]), POINT_STEP))
        if idx[-1] != len(tr["path"]) - 1:
            idx.append(len(tr["path"]) - 1)
        pts, ts = [tr["path"][i] for i in idx], [tr["timestamps"][i] for i in idx]
        for s in range(0, len(pts) - 1, seg_points):
            e = min(s + seg_points, len(pts) - 1)
            sp, st_ = pts[s:e + 1], ts[s:e + 1]
            dt = st_[-1] - st_[0]
            if dt <= 0:
                continue
            dist = sum(meters_between(a, b) for a, b in zip(sp, sp[1:]))
            kmh = dist / dt * 3.6
            segs.append({"path": [[round(p[0], 5), round(p[1], 5)] for p in sp],
                         "timestamps": [round(t, 1) for t in st_],
                         "color": speed_color(kmh), "kmh": round(kmh, 1)})
    return segs


# --- Réseau routier + congestion --------------------------------------------
def read_net_location(net_path: Path):
    """Lit netOffset et la projection dans l'en-tête du fichier .net.xml."""
    head = net_path.read_text(encoding="utf-8", errors="ignore")[:6000]
    loc = re.search(r"<location\s+([^>]*)/>", head)
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', loc.group(1))) if loc else {}
    ox, oy = (float(v) for v in attrs["netOffset"].split(","))
    return ox, oy, attrs["projParameter"]


def osmids_of(value):
    return re.findall(r"\d+", str(value))


def load_edge_stats(path: Path):
    """Par rue : vitesse moyenne (km/h) et nombre de véhicules entrés, d'après edgedata.xml (SUMO)."""
    if not path.exists():
        return {}
    acc = {}
    for _, el in ET.iterparse(str(path), events=("end",)):
        if el.tag == "edge" and el.get("speed") is not None:
            a = acc.setdefault(el.get("id"), [0.0, 0.0, 0])
            sec = float(el.get("sampledSeconds", 0))
            a[0] += float(el.get("speed")) * sec
            a[1] += sec
            a[2] += int(el.get("entered", 0))
            el.clear()
    return {e: {"kmh": (a[0] / a[1] * 3.6) if a[1] > 0 else None, "veh": a[2]} for e, a in acc.items()}


@st.cache_data
def load_network(net_str, edges_str, kpi_str, edata_str, mt_net, mt_edges, mt_kpi, mt_edata):
    """Rues du réseau SUMO (géométrie exacte) + congestion + vitesse + véhicules + nom."""
    net_path, edges_path, kpi_path = Path(net_str), Path(edges_str), Path(kpi_str)
    if not net_path.exists():
        return [], 0, 0, 0, "hassan.net.xml introuvable"
    if not HAS_PYPROJ:
        return [], 0, 0, 0, "pyproj non installé (pip install pyproj)"

    cong = {}
    if kpi_path.exists():
        cong = json.loads(kpi_path.read_text(encoding="utf-8")).get("congestion_par_rue", {})
    stats = load_edge_stats(Path(edata_str)) if edata_str else {}

    names = {}
    if edges_path.exists():
        for f in json.loads(edges_path.read_text(encoding="utf-8"))["features"]:
            p = f["properties"]
            nm = clean_street_name(p.get("name"))
            for oid in osmids_of(p.get("osmid")):
                if nm:
                    names.setdefault(oid, nm)

    off_x, off_y, proj = read_net_location(net_path)
    to_wgs = Transformer.from_crs(proj, "EPSG:4326", always_xy=True)

    streets, n_cong, n_unnamed, n_stats = [], 0, 0, 0
    for _, el in ET.iterparse(str(net_path), events=("end",)):
        if el.tag != "edge":
            continue
        if el.get("function") != "internal":
            lane0 = el.find("lane")
            shape = el.get("shape") or (lane0.get("shape") if lane0 is not None else None)
            if shape:
                xy = [tuple(float(c) for c in pt.split(",")) for pt in shape.split()]
                lonlat = [list(to_wgs.transform(x - off_x, y - off_y)) for x, y in xy]
                lonlat = [[round(a, 6), round(b, 6)] for a, b in lonlat]
                eid = el.get("id")
                orig = None
                param = el.find("lane/param[@key='origId']")
                if param is not None:
                    orig = osmids_of(param.get("value"))
                name = names.get(orig[0], "") if orig else ""
                if not name:
                    n_unnamed += 1
                kind = (el.get("type") or "").replace("highway.", "")
                width = {"primary": 9, "secondary": 8, "tertiary": 6}.get(kind, 4)
                limit = float(lane0.get("speed")) * 3.6 if lane0 is not None and lane0.get("speed") else None
                length = float(lane0.get("length", 0)) if lane0 is not None else 0.0
                rate = cong.get(eid)
                es = stats.get(eid, {})
                kmh, veh = es.get("kmh"), es.get("veh")
                label, color = None, None
                if rate is not None:
                    n_cong += 1
                    label = congestion_label(rate)
                    tip = (f"<b>{name or 'Rue sans nom'}</b><br/>Congestion : {label} "
                           f"({rate * 100:.0f} % du temps ralenti)")
                    if kmh is not None and limit:
                        n_stats += 1
                        tip += f"<br/>Vitesse moyenne : {kmh:.0f} / {limit:.0f} km/h · {veh} véhicules"
                    color = congestion_color(rate)
                else:
                    tip = f"<b>{name or 'Rue sans nom'}</b><br/>Pas de mesure (peu de véhicules)"
                streets.append({"id": eid, "path": lonlat, "rate": rate, "color": color, "width": width,
                                "tip": tip, "name": name, "label": label, "kmh": kmh, "limit": limit,
                                "veh": veh or 0, "length": length})
        el.clear()
    return streets, n_cong, n_unnamed, n_stats, ""


@st.cache_data
def load_kpi(path_str: str, mt: float):
    path = Path(path_str)
    if not path.exists():
        return None
    kpi = json.loads(path.read_text(encoding="utf-8"))
    kpi.pop("congestion_par_rue", None)
    return kpi


# --- Barre latérale ----------------------------------------------------------
scenarios = sorted(p.stem.replace("trajectories_", "") for p in DATA_DIR.glob("trajectories_*.json")) or ["actuel"]
st.sidebar.header("Affichage")
scenario = st.sidebar.selectbox("Scénario", scenarios,
                                index=scenarios.index("actuel") if "actuel" in scenarios else 0)
compare_mode = st.sidebar.checkbox("Mode comparaison (actuel vs simulé)", False,
                                   help="Affiche deux cartes côte à côte avec les KPI comparés. "
                                        "Nécessite au moins deux scénarios.")
if compare_mode and len(scenarios) < 2:
    st.sidebar.warning("Un seul scénario disponible : le mode comparaison est désactivé.")
    compare_mode = False
scenario_b = None
if compare_mode:
    others = [s for s in scenarios if s != scenario]
    scenario_b = st.sidebar.selectbox("Scénario simulé à comparer", others, index=0)

mode_name = st.sidebar.radio("Ambiance", list(MODES), index=0)
mode = MODES[mode_name]
show_buildings = st.sidebar.checkbox("Bâtiments", True)
show_roads = st.sidebar.checkbox("Rues colorées par congestion", True)
show_traffic = st.sidebar.checkbox("Trafic animé", True)
show_labels = st.sidebar.checkbox("Étiquettes KPI sur la carte", True)
show_glow = st.sidebar.checkbox("Effet néon (halo) sur rues et trafic", True,
                                help="Deux couches superposées pour un rendu lumineux. "
                                     "Désactiver si la carte rame.")
use_light = st.sidebar.checkbox("Lumière et ombres (expérimental)", False,
                                help="Si la carte devient vide ou plante, décoche cette case.")
top_by_impact = st.sidebar.checkbox("Top 5 par impact (congestion × longueur)", False,
                                    help="Une longue avenue modérément congestionnée peut impacter "
                                         "plus de monde qu'une petite rue saturée.")
trail = st.sidebar.slider("Longueur des traînées (s)", 20, 300, 120, step=10)
pitch = st.sidebar.slider("Inclinaison de la vue", 0, 75, 58)
bearing = st.sidebar.slider("Rotation de la vue", -180, 180, 20)

TRAJ_FILE = DATA_DIR / f"trajectories_{scenario}.json"
KPI_FILE = DATA_DIR / f"kpi_{scenario}.json"
EDGEDATA_FILE = next((f for f in (DATA_DIR / f"edgedata_{scenario}.xml",
                                  DATA_DIR / "edgedata.xml" if scenario == "actuel" else None)
                      if f is not None and f.exists()), None)

# Fichiers du scénario B (comparaison)
TRAJ_FILE_B = DATA_DIR / f"trajectories_{scenario_b}.json" if scenario_b else None
KPI_FILE_B = DATA_DIR / f"kpi_{scenario_b}.json" if scenario_b else None
EDGEDATA_FILE_B = None
if scenario_b:
    EDGEDATA_FILE_B = next((f for f in (DATA_DIR / f"edgedata_{scenario_b}.xml",
                                        DATA_DIR / "edgedata.xml" if scenario_b == "actuel" else None)
                            if f is not None and f.exists()), None)

# --- Chargement --------------------------------------------------------------
buildings, b_source, b_real, b_default_h = load_buildings(str(BUILDINGS_FILE), mtime(BUILDINGS_FILE))
trips, t_source, t_real = load_trips(str(TRAJ_FILE), mtime(TRAJ_FILE))
segments = speed_segments(trips)
streets, n_cong, n_unnamed, n_stats, net_error = load_network(
    str(NET_FILE), str(EDGES_FILE), str(KPI_FILE), str(EDGEDATA_FILE or ""),
    mtime(NET_FILE), mtime(EDGES_FILE), mtime(KPI_FILE), mtime(EDGEDATA_FILE) if EDGEDATA_FILE else 0.0)
kpi = load_kpi(str(KPI_FILE), mtime(KPI_FILE))

trips_b, segments_b, kpi_b = None, None, None
if compare_mode and scenario_b:
    trips_b, _, _ = load_trips(str(TRAJ_FILE_B), mtime(TRAJ_FILE_B))
    segments_b = speed_segments(trips_b)
    kpi_b = load_kpi(str(KPI_FILE_B), mtime(KPI_FILE_B))

b_pts = [p for f in buildings["features"] for p in flat_coords(f["geometry"]["coordinates"])]
b_bbox = bbox_of_points(b_pts)

center_lon = float(os.getenv("CENTER_LON", (b_bbox[0] + b_bbox[2]) / 2))
center_lat = float(os.getenv("CENTER_LAT", (b_bbox[1] + b_bbox[3]) / 2))

t_min = min(t for tr in trips for t in tr["timestamps"])
t_max = int(max(t for tr in trips for t in tr["timestamps"]))

view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=15.3, pitch=pitch, bearing=bearing)


# --- Couches -----------------------------------------------------------------
@st.cache_resource
def building_layer():
    lo, hi = mode["b_lo"], mode["b_hi"]
    color = "[" + ", ".join(f"{lo[i]} + {hi[i] - lo[i]} * properties.t" for i in range(3)) + f", {mode['b_alpha']}]"
    return pdk.Layer("GeoJsonLayer", buildings, extruded=True, wireframe=False,
                     get_elevation="properties.height", get_fill_color=color, pickable=True,
                     material={"ambient": 0.45, "diffuse": 0.7, "shininess": 24})


@st.cache_resource
def roads_layer():
    data = [dict(s, color=s["color"] or mode["road_idle"]) for s in streets]
    return pdk.Layer("PathLayer", data, get_path="path", get_color="color", get_width="width",
                     width_min_pixels=2, width_max_pixels=14, cap_rounded=True, joint_rounded=True,
                     pickable=True)


@st.cache_resource
def roads_glow_layer():
    """Halo large et translucide sous les rues : effet néon."""
    data = [dict(s, color=(s["color"][:3] + [70]) if s["color"] else mode["road_idle"][:3] + [40])
            for s in streets]
    return pdk.Layer("PathLayer", data, get_path="path", get_color="color", get_width="width",
                     width_min_pixels=6, width_max_pixels=30, cap_rounded=True, joint_rounded=True,
                     pickable=False)


def top_congested(n=N_TOP, min_length_m=40, by_impact=False):
    """Les n rues nommées les plus congestionnées (une seule par nom de rue, tronçons trop courts ignorés).
    by_impact : tri par congestion × longueur, plus parlant pour un décideur."""
    best = {}
    for st_ in streets:
        if st_["rate"] is None or not st_["name"] or st_["length"] < min_length_m:
            continue
        cur = best.get(st_["name"])
        if cur is None or (st_["rate"], st_["veh"]) > (cur["rate"], cur["veh"]):
            best[st_["name"]] = st_
    if by_impact:
        return sorted(best.values(), key=lambda x: x["rate"] * x["length"], reverse=True)[:n]
    return sorted(best.values(), key=lambda x: (x["rate"], x["veh"]), reverse=True)[:n]


def kpi_line(st_):
    if st_["kmh"] is None or not st_["limit"]:
        return None
    return f"{st_['kmh']:.0f} / {st_['limit']:.0f} km/h · {st_['veh']} véh."


def labels_layers(top):
    """Étiquettes façon Spotnik : nom de la rue, niveau de congestion, vitesse moyenne / limite, véhicules."""
    data = []
    for st_ in top:
        mid = st_["path"][len(st_["path"]) // 2]
        line = kpi_line(st_)
        text = f"{st_['name']}\nCongestion : {st_['label']}" + (f"\n{line.replace('·', '|')}" if line else "")
        data.append({"position": [mid[0], mid[1], 30], "text": ascii_fold(text),
                     "color": congestion_color(st_["rate"])[:3] + [255]})
    no_depth = {"depthTest": False}   # l'étiquette reste visible devant les bâtiments
    dots = pdk.Layer("ScatterplotLayer", data, get_position="position", get_fill_color="color",
                     get_radius=8, radius_min_pixels=5, radius_max_pixels=9, parameters=no_depth)
    text = pdk.Layer("TextLayer", data, get_position="position", get_text="text", get_color="color",
                     get_size=15, get_text_anchor='"middle"', get_alignment_baseline='"bottom"',
                     get_pixel_offset=[0, -22], background=True, get_background_color=[8, 10, 18, 225],
                     background_padding=[8, 5], parameters=no_depth)
    return [dots, text]


def pulse_layer(top, t, max_t):
    """Marqueurs pulsés sur les rues les plus congestionnées : le rayon varie avec le temps."""
    if not top:
        return None
    phase = (t % 60) / 60.0
    radius = 40 + 60 * math.sin(phase * math.pi) ** 2
    data = []
    for st_ in top:
        mid = st_["path"][len(st_["path"]) // 2]
        data.append({"position": [mid[0], mid[1], 20],
                     "color": congestion_color(st_["rate"])[:3] + [180]})
    return pdk.Layer("ScatterplotLayer", data, get_position="position", get_fill_color="color",
                     get_radius=radius, radius_min_pixels=6, radius_max_pixels=40,
                     opacity=0.5, parameters={"depthTest": False})


def trips_layer(t, segments_data=None):
    segs = segments_data if segments_data is not None else segments
    return pdk.Layer("TripsLayer", segs, get_path="path", get_timestamps="timestamps",
                     get_color="color", width_min_pixels=4, rounded=True,
                     trail_length=trail, current_time=t)


def trips_glow_layer(t, segments_data=None):
    """Halo large et translucide sous les traînées : effet lumineux."""
    segs = segments_data if segments_data is not None else segments
    if not show_glow:
        return None
    return pdk.Layer("TripsLayer", segs, get_path="path", get_timestamps="timestamps",
                     get_color="color", width_min_pixels=12, rounded=True,
                     trail_length=trail, current_time=t, opacity=0.35)


def lighting_effects():
    """Soleil directionnel + lumière ambiante (+ ombres). Expérimental selon la version de pydeck/Streamlit."""
    return [{
        "@@type": "LightingEffect",
        "shadowColor": mode["shadow"],
        "ambientLight": {"@@type": "AmbientLight", "color": [255, 255, 255], "intensity": mode["amb"]},
        "directionalLights": [{"@@type": "DirectionalLight", "color": mode["sun"], "intensity": mode["sun_i"],
                               "direction": [-1.5, -2.5, -2.0], "_shadow": True}],
    }]


TOP = top_congested(by_impact=top_by_impact)


def build_deck(t, segments_data=None, top=None):
    top = top if top is not None else TOP
    layers = []
    if show_roads and streets:
        if show_glow:
            layers.append(roads_glow_layer())
        layers.append(roads_layer())
    if show_buildings:
        layers.append(building_layer())
    if show_traffic:
        if show_glow:
            glow = trips_glow_layer(t, segments_data)
            if glow is not None:
                layers.append(glow)
        layers.append(trips_layer(t, segments_data))
    if show_labels and top:
        layers.extend(labels_layers(top))
        pulse = pulse_layer(top, t, t_max)
        if pulse is not None:
            layers.append(pulse)
    kwargs = {"effects": lighting_effects()} if use_light else {}
    return pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto",
                    map_style=mode["map_style"], tooltip={"html": "{tip}"}, **kwargs)


def show_deck(slot, deck):
    slot.pydeck_chart(deck, height=720)


# --- Contrôles ---------------------------------------------------------------
def run_checks():
    res = []
    types = {f["geometry"]["type"] for f in buildings["features"]}
    res.append(("ok" if b_real else "warn",
                f"{len(buildings['features'])} bâtiments, géométries : {sorted(types)}"))
    pct_default = 100 * b_default_h / max(len(buildings["features"]), 1)
    res.append(("ok" if b_default_h == 0 else "warn",
                f"{b_default_h} bâtiment(s) sans hauteur ({pct_default:.0f} %) — valeur aléatoire 8-20 m appliquée"))
    hs = sorted({f["properties"]["height"] for f in buildings["features"]})
    if len(hs) <= 25:
        res.append(("warn", f"Seulement {len(hs)} hauteurs différentes : probablement des valeurs par défaut"))
    lon_ok = all(-180 <= p[0] <= 180 for p in b_pts) and all(-90 <= p[1] <= 90 for p in b_pts)
    swapped = (b_bbox[0] > 30 and b_bbox[1] < 0)
    res.append(("err" if (not lon_ok or swapped) else "ok", "Ordre des coordonnées [lon, lat] valide"))

    pts = [p for tr in trips for p in tr["path"]]
    res.append(("ok" if t_real else "warn",
                f"{len(trips)} véhicules, {len(pts)} points, temps de {t_min:.0f} à {t_max} s "
                f"({len(segments)} tronçons colorés par vitesse)"))
    bad_order = sum(1 for tr in trips if any(b < a for a, b in zip(tr["timestamps"], tr["timestamps"][1:])))
    res.append(("ok" if bad_order == 0 else "err", f"{bad_order} trajet(s) avec temps non croissants"))

    tx0, ty0, tx1, ty1 = bbox_of_points(pts)
    m = 0.0003
    inside = sum(1 for p in pts if b_bbox[0] - m <= p[0] <= b_bbox[2] + m and b_bbox[1] - m <= p[1] <= b_bbox[3] + m)
    pct = 100 * inside / len(pts)
    res.append(("ok" if pct >= 99 else "warn" if pct >= 90 else "err",
                f"{pct:.1f} % des points de trajet sont dans la zone des bâtiments"))

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
        res.append(("warn", "shapely non installé : test « voiture dans un bâtiment » ignoré"))

    if net_error:
        res.append(("warn", f"Rues non affichées : {net_error}"))
    else:
        res.append(("ok" if streets else "warn", f"{len(streets)} rues du réseau SUMO placées sur la carte"))
        cong_total = len(json.loads(KPI_FILE.read_text(encoding="utf-8")).get("congestion_par_rue", {})) if KPI_FILE.exists() else 0
        if KPI_FILE.exists():
            res.append(("ok" if n_cong == cong_total else "warn",
                        f"{n_cong} / {cong_total} rues avec congestion reliées à la géométrie"))
        else:
            res.append(("warn", f"{KPI_FILE.name} introuvable : pas de congestion à afficher"))
        if EDGEDATA_FILE is None:
            res.append(("warn", "edgedata.xml introuvable : pas de vitesse ni de nombre de véhicules par rue"))
        else:
            res.append(("ok", f"{n_stats} rues avec vitesse moyenne et véhicules ({EDGEDATA_FILE.name}) ; "
                              f"{len(TOP)} rues mises en avant"))
        n_high_limit = sum(1 for s in streets if s["limit"] and s["limit"] > 70)
        res.append(("warn" if n_high_limit else "ok",
                    f"{n_high_limit} rue(s) avec limite > 70 km/h (réseau SUMO irréaliste en ville, "
                    f"gonfle la congestion)"))
        res.append(("ok" if n_unnamed < 0.25 * max(len(streets), 1) else "warn",
                    f"{n_unnamed} rue(s) sans nom (info absente de network_edges.geojson)"))
    return res


# --- Panneau « Top rues congestionnées » -------------------------------------
def render_top_panel(top):
    st.markdown(f"**Top {len(top)} des rues les plus congestionnées**")
    if not top:
        st.caption("Aucune rue nommée avec une mesure de congestion.")
        return
    for i, st_ in enumerate(top, 1):
        r, g, b = congestion_color(st_["rate"])[:3]
        line = kpi_line(st_) or "vitesse non mesurée"
        st.markdown(
            f"<div style='border-left:4px solid rgb({r},{g},{b});padding:2px 10px;margin:10px 0'>"
            f"<b>{i}. {st_['name']}</b><br/>"
            f"<span style='color:rgb({r},{g},{b})'>Congestion : {st_['label']} ({st_['rate'] * 100:.0f} %)</span><br/>"
            f"<small>{line}</small></div>", unsafe_allow_html=True)
    st.caption(f"Vitesse moyenne / limite ; véhicules = passages pendant les {t_max // 60} min de simulation.")


# --- Export du rapport -------------------------------------------------------
def build_report_markdown():
    lines = [
        "# Rapport de simulation — Jumeau numérique 3D, Rabat Hassan",
        f"\nGénéré le {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "\n## Scénario affiché",
        f"- Scénario : **{scenario}**",
        f"- Ambiance : {mode_name}",
        f"- Temps de simulation : {t_max} s ({t_max // 60} min)",
        f"- Véhicules : {len(trips)}",
    ]
    if kpi:
        lines += [
            "\n## Indicateurs clés",
            f"- Temps de trajet moyen : {kpi.get('temps_trajet_moyen_s', 0):.0f} s",
            f"- Vitesse moyenne : {kpi.get('vitesse_moyenne_kmh', 0):.1f} km/h",
            f"- Congestion moyenne : {(kpi.get('congestion_moyenne') or 0) * 100:.0f} %",
            f"- CO₂ total : {kpi.get('co2_total_g', 0) / 1000:.0f} kg",
        ]
    if TOP:
        lines.append("\n## Rues les plus congestionnées")
        for i, st_ in enumerate(TOP, 1):
            lines.append(f"{i}. **{st_['name']}** — {st_['label']} ({st_['rate'] * 100:.0f} %), "
                         f"{kpi_line(st_) or 'vitesse non mesurée'}")
    lines += [
        "\n## Limites du prototype",
        "- Les données de trafic sont **simulées** (SUMO), pas mesurées.",
        "- Les limites de vitesse du réseau SUMO sont irréalistes en ville (tronçons à 100 km/h).",
        "- Une partie des hauteurs de bâtiments est estimée (données OSM manquantes).",
        "\n---\n*Prototype pédagogique — Transformation digitale, Rabat.*",
    ]
    return "\n".join(lines)


# --- Interface ---------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Vue 3D", "Comparaison", "Contrôles"])

with tab1:
    if kpi:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temps de trajet moyen", f"{kpi.get('temps_trajet_moyen_s', 0):.0f} s")
        c2.metric("Vitesse moyenne", f"{kpi.get('vitesse_moyenne_kmh', 0):.1f} km/h")
        c3.metric("Congestion moyenne", f"{(kpi.get('congestion_moyenne') or 0) * 100:.0f} %")
        c4.metric("CO₂ total", f"{kpi.get('co2_total_g', 0) / 1000:.0f} kg")
        st.caption("Données simulées (SUMO), pas des mesures réelles.")

    col_map, col_top = st.columns([3, 1])
    with col_map:
        t = st.slider("Temps de simulation (s)", 0, t_max, 0, step=5)
        slot = st.empty()
        show_deck(slot, build_deck(t))
        st.markdown(
            "**Trafic** : <span style='color:#3cd2ff'>●</span> fluide &nbsp; "
            "<span style='color:#ffe150'>●</span> modéré &nbsp; "
            "<span style='color:#ff9628'>●</span> lent &nbsp; "
            "<span style='color:#ff3232'>●</span> arrêt &nbsp;|&nbsp; "
            "**Rues** : bleu = fluide → rouge = congestionnée",
            unsafe_allow_html=True)
        if st.button("▶ Lecture automatique"):
            for tt in range(0, t_max, 10):
                show_deck(slot, build_deck(tt))
                time.sleep(0.15)
    with col_top:
        render_top_panel(TOP)
        st.download_button("📄 Exporter le rapport (Markdown)",
                           data=build_report_markdown(),
                           file_name=f"rapport_{scenario}.md",
                           mime="text/markdown")

with tab2:
    if not compare_mode:
        st.info("Active le **mode comparaison** dans la barre latérale pour afficher deux scénarios côte à côte.")
    else:
        st.subheader(f"Comparaison : **{scenario}** vs **{scenario_b}**")
        if kpi and kpi_b:
            c1, c2, c3, c4 = st.columns(4)
            d1 = kpi_b.get("temps_trajet_moyen_s", 0) - kpi.get("temps_trajet_moyen_s", 0)
            d2 = kpi_b.get("vitesse_moyenne_kmh", 0) - kpi.get("vitesse_moyenne_kmh", 0)
            d3 = (kpi_b.get("congestion_moyenne") or 0) - (kpi.get("congestion_moyenne") or 0)
            d4 = kpi_b.get("co2_total_g", 0) / 1000 - kpi.get("co2_total_g", 0) / 1000
            c1.metric("Temps de trajet moyen", f"{kpi_b.get('temps_trajet_moyen_s', 0):.0f} s",
                      delta=f"{d1:+.0f} s", delta_color="inverse")
            c2.metric("Vitesse moyenne", f"{kpi_b.get('vitesse_moyenne_kmh', 0):.1f} km/h",
                      delta=f"{d2:+.1f} km/h")
            c3.metric("Congestion moyenne", f"{(kpi_b.get('congestion_moyenne') or 0) * 100:.0f} %",
                      delta=f"{d3 * 100:+.0f} %", delta_color="inverse")
            c4.metric("CO₂ total", f"{kpi_b.get('co2_total_g', 0) / 1000:.0f} kg",
                      delta=f"{d4:+.0f} kg", delta_color="inverse")
            st.caption("Delta = scénario simulé − situation actuelle. Rouge = dégradation, vert = amélioration.")
        t_cmp = st.slider("Temps de simulation (s)", 0, t_max, 0, step=5, key="t_cmp")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**{scenario}** (actuel)")
            show_deck(col_a.empty(), build_deck(t_cmp))
        with col_b:
            st.markdown(f"**{scenario_b}** (simulé)")
            show_deck(col_b.empty(), build_deck(t_cmp, segments_data=segments_b))

with tab3:
    st.caption(f"Dossier de données : {DATA_DIR} · Bâtiments : {b_source} · Trajets : {t_source}")
    icons = {"ok": "✅", "warn": "⚠️", "err": "❌"}
    for level, text in run_checks():
        st.write(f"{icons[level]} {text}")