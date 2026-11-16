"""
compare_map.py - cree UNE carte HTML pour comparer visuellement les zones.
Usage : python compare_map.py [dossier_parent]   (defaut : <depot>/data_test)
Lit <dossier_parent>/<zone>/{network_edges,buildings}.geojson et ecrit
<dossier_parent>/comparaison.html  (a ouvrir par double-clic ; internet requis pour le fond de carte).
"""
import json
import sys
from pathlib import Path

MAIN = ("motorway", "trunk", "primary", "secondary", "tertiary")
COLORS = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e"]


def slim(path, keep):
    data = json.loads(path.read_text(encoding="utf-8"))
    feats = []
    for f in data["features"]:
        props = {k: f["properties"].get(k) for k in keep}
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": feats}


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data_test"
    zones = sorted(p.parent for p in root.glob("*/zone.json"))
    if not zones:
        raise SystemExit(f"Aucune zone trouvee dans {root}")

    payload = []
    for i, z in enumerate(zones):
        meta = json.loads((z / "zone.json").read_text(encoding="utf-8"))
        payload.append({
            "name": z.name,
            "color": COLORS[i % len(COLORS)],
            "bbox": meta["bbox_west_south_east_north"],
            "info": f'{meta["n_edges"]} troncons, {meta["n_buildings"]} batiments',
            "edges": slim(z / "network_edges.geojson", ["name", "highway", "length"]),
            "buildings": slim(z / "buildings.geojson", ["height"]),
        })

    html = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False)).replace("__MAIN__", json.dumps(MAIN))
    out = root / "comparaison.html"
    out.write_text(html, encoding="utf-8")
    print("Carte creee :", out.resolve())
    print("Double-cliquez dessus pour l'ouvrir dans le navigateur.")


HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Comparaison des zones - Rabat</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>html,body,#map{height:100%;margin:0} .info{background:#fff;padding:8px 10px;border-radius:6px;font:13px sans-serif;box-shadow:0 1px 4px #0004}</style>
</head><body><div id="map"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const ZONES = __DATA__, MAIN = __MAIN__;
const map = L.map('map');
// Le serveur de tuiles d'OpenStreetMap bloque les pages ouvertes en fichier local (403) : on utilise CARTO.
const carto = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
}).addTo(map);
const blank = L.tileLayer('data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==', {maxZoom: 19});
const baseLayers = {'Fond de carte (CARTO)': carto, 'Fond blanc (sans internet)': blank};
const overlays = {}; const all = [];
ZONES.forEach(z => {
  const [w, s, e, n] = z.bbox;
  const box = L.rectangle([[s, w], [n, e]], {color: z.color, weight: 2, fill: false, dashArray: '6 4'})
    .bindTooltip(z.name + ' : ' + z.info, {sticky: true});
  const roads = L.geoJSON(z.edges, {
    style: f => {
      const main = MAIN.some(t => String(f.properties.highway).includes(t));
      return {color: main ? z.color : '#777', weight: main ? 4 : 1.5, opacity: 0.9};
    },
    onEachFeature: (f, l) => l.bindPopup((f.properties.name || '(sans nom)') + '<br>' + f.properties.highway + '<br>' + Math.round(f.properties.length) + ' m')
  });
  const bld = L.geoJSON(z.buildings, {style: {color: z.color, weight: 0.5, fillColor: z.color, fillOpacity: 0.35}});
  overlays[z.name + ' - cadre'] = box;
  overlays[z.name + ' - rues (epaisses = axes principaux)'] = roads;
  roads.addTo(map);
  overlays[z.name + ' - batiments'] = bld;
  all.push(box);
});
L.control.layers(baseLayers, overlays, {collapsed: false}).addTo(map);
const fg = L.featureGroup(all); fg.addTo(map);
map.fitBounds(fg.getBounds());
const info = L.control({position: 'bottomleft'});
info.onAdd = () => { const d = L.DomUtil.create('div', 'info'); d.innerHTML = 'Cochez une zone a droite.<br>Clic sur une rue : nom et longueur.'; return d; };
info.addTo(map);
</script></body></html>
"""

if __name__ == "__main__":
    main()