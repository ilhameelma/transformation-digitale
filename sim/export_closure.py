"""
export_closure.py - definit la fermeture de rue du scenario 2.
Selectionne un troncon (section) d'une rue et ecrit :
  - data/closure.json     identifiants des troncons a fermer (pour M2 / SUMO)
  - data/closure.geojson  les memes troncons seuls
  - data/closure_preview.geojson  toutes les rues en gris + la section en rouge (pour geojson.io)
  - data/closure_map.html  la meme chose dans une page a ouvrir par double-clic

Usage :
  python export_closure.py --street "Allal Ben Abdellah" --length 400
  python export_closure.py --street "Mohamed V" --length 500 --start 0.3

  --street  morceau du nom (insensible a la casse ; marche avec la partie arabe aussi)
  --length  longueur de la section a fermer, en metres (defaut 400)
  --start   position du centre de la section le long de la rue, de 0 a 1 (defaut 0.5 = milieu)
  --list    affiche seulement les noms de rues qui correspondent
"""
import argparse
import ast
import json
import math
import os
from pathlib import Path


def default_data_dir():
    env = os.getenv("OUTPUT_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data"


def clean_name(raw):
    if raw in (None, "", "nan", "None"):
        return ""
    s = str(raw).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            return " / ".join(str(x) for x in ast.literal_eval(s))
        except (ValueError, SyntaxError):
            return s.strip("[]")
    return s


def centroid_m(geom, lat0):
    """Centre du troncon en metres (x, y) approximatifs."""
    pts = geom["coordinates"]
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lon * 111_320 * math.cos(math.radians(lat0)), lat * 111_320


def principal_axis(points):
    """Direction principale (ux, uy) des points, par ACP 2D."""
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    syy = sum((p[1] - my) ** 2 for p in points)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return math.cos(theta), math.sin(theta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--street", required=True)
    ap.add_argument("--length", type=float, default=400)
    ap.add_argument("--start", type=float, default=0.5)
    ap.add_argument("--data", type=Path, default=default_data_dir())
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    feats = json.loads((a.data / "network_edges.geojson").read_text(encoding="utf-8"))["features"]
    q = a.street.lower()
    sel = [f for f in feats if q in clean_name(f["properties"].get("name")).lower()]
    if not sel:
        raise SystemExit(f"Aucune rue ne contient '{a.street}'. Essayez list_streets.py pour voir les noms.")

    names = sorted({clean_name(f["properties"].get("name")) for f in sel})
    print("Rues correspondantes :")
    for n in names:
        print("  -", n)
    if a.list:
        return
    if len(names) > 1:
        print("ATTENTION : plusieurs noms correspondent ; precisez --street pour n'en garder qu'un.")

    lat0 = sum(f["geometry"]["coordinates"][0][1] for f in sel) / len(sel)
    cents = [centroid_m(f["geometry"], lat0) for f in sel]
    ux, uy = principal_axis(cents)
    pos = [c[0] * ux + c[1] * uy for c in cents]          # position le long de la rue (m)
    lo, hi = min(pos), max(pos)
    span = hi - lo
    center = lo + a.start * span

    # On ajoute les troncons les plus proches du centre (avec leur "jumeau" de sens inverse,
    # qui a la meme position) jusqu'a couvrir la longueur demandee.
    lens = [float(f["properties"].get("length") or 0) for f in sel]
    order = sorted(range(len(sel)), key=lambda i: abs(pos[i] - center))
    idx, lo_e, hi_e = [], None, None
    for i in order:
        if i in idx:
            continue
        for j in range(len(sel)):
            if j not in idx and abs(pos[j] - pos[i]) < 5:
                idx.append(j)
                a_, b_ = pos[j] - lens[j] / 2, pos[j] + lens[j] / 2
                lo_e = a_ if lo_e is None else min(lo_e, a_)
                hi_e = b_ if hi_e is None else max(hi_e, b_)
        if hi_e - lo_e >= a.length:
            break
    chosen = [(sel[i], pos[i]) for i in idx]
    covered = hi_e - lo_e

    edges, total = [], 0.0
    for f, p in chosen:
        pr = f["properties"]
        length = float(pr.get("length") or 0)
        total += length
        edges.append({"u": pr.get("u"), "v": pr.get("v"), "key": pr.get("key"),
                      "osmid": pr.get("osmid"), "name": clean_name(pr.get("name")),
                      "highway": pr.get("highway"), "oneway": pr.get("oneway"), "length_m": round(length, 1)})

    closure = {
        "scenario": "rue_fermee",
        "street_query": a.street,
        "section_requested_m": a.length,
        "section_covered_m": round(covered),
        "section_center_fraction": a.start,
        "street_span_m": round(span),
        "n_edges": len(edges),
        "total_edge_length_m": round(total, 1),
        "note": "total_edge_length_m compte chaque sens de circulation ; osmid = identifiant OSM de la voie "
                "(les ids SUMO issus de netconvert --osm sont de la forme <osmid>#<n>, a verifier par M2).",
        "edges": edges,
    }
    (a.data / "closure.json").write_text(json.dumps(closure, indent=2, ensure_ascii=False), encoding="utf-8")
    (a.data / "closure.geojson").write_text(json.dumps({"type": "FeatureCollection",
        "features": [f for f, _ in chosen]}, ensure_ascii=False), encoding="utf-8")

    # Apercu colore (norme "simplestyle" lue par geojson.io) : section rouge epaisse, reste gris fin
    chosen_ids = {(f["properties"].get("u"), f["properties"].get("v"), f["properties"].get("key")) for f, _ in chosen}
    preview = []
    for f in feats:
        pr = f["properties"]
        is_closed = (pr.get("u"), pr.get("v"), pr.get("key")) in chosen_ids
        style = ({"stroke": "#e00000", "stroke-width": 7, "stroke-opacity": 1}
                 if is_closed else {"stroke": "#8a8a8a", "stroke-width": 2, "stroke-opacity": 0.8})
        preview.append({"type": "Feature", "geometry": f["geometry"],
                        "properties": {"name": clean_name(pr.get("name")), **style}})
    preview.sort(key=lambda x: x["properties"]["stroke-width"])  # rouge dessine en dernier
    (a.data / "closure_preview.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": preview}, ensure_ascii=False), encoding="utf-8")

    # Page HTML a ouvrir par double-clic (comme comparaison.html)
    bpath = a.data / "buildings.geojson"
    buildings = []
    if bpath.exists():
        buildings = [{"type": "Feature", "geometry": b["geometry"], "properties": {}}
                     for b in json.loads(bpath.read_text(encoding="utf-8"))["features"]]
    page = (HTML.replace("__ROADS__", json.dumps({"type": "FeatureCollection", "features": preview}, ensure_ascii=False))
                .replace("__BUILDINGS__", json.dumps({"type": "FeatureCollection", "features": buildings}))
                .replace("__INFO__", json.dumps(f"{a.street} : section de ~{round(covered)} m, {len(edges)} troncons", ensure_ascii=False)))
    (a.data / "closure_map.html").write_text(page, encoding="utf-8")

    print(f"\nSection retenue : ~{round(covered)} m de rue, {len(edges)} troncons "
          f"({round(total)} m cumules, tous sens confondus)")
    print(f"(la rue entiere s'etale sur ~{round(span)} m)")
    print("Fichiers : closure.json (pour M2), closure.geojson, closure_preview.geojson")
    print("A OUVRIR PAR DOUBLE-CLIC : data\\closure_map.html  (section en rouge, rues en gris)")


HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Section de rue fermee</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>html,body,#map{height:100%;margin:0;background:#fff}
.box{background:#fff;padding:8px 12px;border-radius:6px;font:14px sans-serif;box-shadow:0 1px 4px #0004;line-height:1.5}
.sw{display:inline-block;width:28px;height:0;vertical-align:middle;margin-right:6px}
.red{border-top:7px solid #e00000}.grey{border-top:2px solid #8a8a8a}</style>
</head><body><div id="map"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
function show(msg) {
  var d = document.createElement("div");
  d.style.cssText = "position:absolute;z-index:9999;top:10px;left:60px;background:#ffecec;border:2px solid #d00;padding:10px;font:14px sans-serif;max-width:70%";
  d.textContent = msg;
  document.body.appendChild(d);
}
window.onerror = function (m, src, line) { show("Erreur JavaScript : " + m + " (ligne " + line + ")"); };
if (typeof L === "undefined") {
  show("Leaflet na pas pu etre charge : verifiez la connexion internet puis actualisez (F5).");
} else {
  var ROADS = __ROADS__, BUILDINGS = __BUILDINGS__, INFO = __INFO__;
  var map = L.map("map");

  // 1) legende d abord (elle doit toujours apparaitre)
  var legend = L.control({position: "bottomleft"});
  legend.onAdd = function () {
    var d = L.DomUtil.create("div", "box");
    d.innerHTML = '<b>' + INFO + '</b><br><span class="sw red"></span>Section FERMEE<br><span class="sw grey"></span>Autres rues (ouvertes)';
    return d;
  };
  legend.addTo(map);

  // 2) vue initiale sure : section fermee, sinon toutes les rues, sinon centre de Rabat
  var closedLayer = L.geoJSON(ROADS, {filter: function (f) { return f.properties.stroke === "#e00000"; }});
  var allRoads = L.geoJSON(ROADS);
  var b = closedLayer.getBounds();
  if (!b.isValid()) { b = allRoads.getBounds(); }
  if (b.isValid()) { map.fitBounds(b.pad(1.2)); } else { map.setView([34.018, -6.831], 15); }

  // 3) couches : chacune protegee, une erreur n arrete pas les autres
  var overlays = {};
  try {
    var bat = L.geoJSON(BUILDINGS, {style: {color: "#c9c9c9", weight: 0.5, fillColor: "#dcdcdc", fillOpacity: 0.6}}).addTo(map);
    overlays["Batiments"] = bat;
  } catch (e) { show("Batiments non affiches : " + e.message); }
  try {
    var roads = L.geoJSON(ROADS, {
      style: function (f) { var p = f.properties; return {color: p.stroke, weight: p["stroke-width"], opacity: p["stroke-opacity"]}; },
      onEachFeature: function (f, l) { l.bindPopup(f.properties.name || "(sans nom)"); }
    }).addTo(map);
    overlays["Rues"] = roads;
  } catch (e) { show("Rues non affichees : " + e.message); }
  try { L.control.layers(null, overlays, {collapsed: false}).addTo(map); } catch (e) { show(e.message); }
}
</script></body></html>
"""

if __name__ == "__main__":
    main()