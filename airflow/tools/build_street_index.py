"""Génère data/street_index.json : les rues entières (tronçons SUMO regroupés par nom de rue).

hassan.net.xml ne contient aucun nom de rue. Le nom vient de data/network_edges.geojson (OpenStreetMap) :
un tronçon SUMO "4330541#3" ou "-4330541#3" appartient à la voie OSM 4330541, dont le nom est dans le geojson.
Les rues sans nom ne sont pas indexées (on ne peut pas les demander par leur nom).

Ce script fixe le FORMAT lu par les DAG (voir jumeau/street_index.py). Si l'index est généré autrement
(étape 1 du plan : street_index.json + resolve_street), il suffit de garder ce format.

Usage : python build_street_index.py [--net ../sim/hassan.net.xml] [--edges ../data/network_edges.geojson]
                                     [--out ../data/street_index.json]
"""
import argparse
import ast
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ("motorway", "trunk", "primary", "secondary", "tertiary")
ARABIC = re.compile(r"[؀-ۿ]")


def clean_name(raw):
    """'Avenue X', "['Avenue X', 'Rue Y']" ou None -> texte. Même règle que sim/list_streets.py."""
    if raw in (None, "", "nan", "None"):
        return ""
    s = str(raw).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            s = " / ".join(str(x) for x in ast.literal_eval(s))
        except (ValueError, SyntaxError):
            s = s.strip("[]")
    return s.strip()


def split_aliases(name):
    """Noms bilingues : 'Avenue X شارع س' -> ['Avenue X', 'شارع س'] (pour la recherche approchée)."""
    out = []
    for part in name.split(" / "):
        m = ARABIC.search(part)
        latin, arabic = (part[:m.start()], part[m.start():]) if m else (part, "")
        out += [x.strip() for x in (latin, arabic) if x.strip()]
    return list(dict.fromkeys(out))


def slugify(text):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def osm_ids(raw):
    """osmid du geojson : un entier, un texte, ou une liste (voies fusionnées)."""
    if isinstance(raw, list):
        return [str(x) for x in raw]
    s = str(raw)
    if s.startswith("["):
        try:
            return [str(x) for x in ast.literal_eval(s)]
        except (ValueError, SyntaxError):
            pass
    return [s]


def build(net, edges_geojson):
    names, kinds = {}, {}
    for f in json.loads(edges_geojson.read_text(encoding="utf-8"))["features"]:
        p = f["properties"]
        name = clean_name(p.get("name"))
        for oid in osm_ids(p.get("osmid")):
            if name and oid not in names:
                names[oid] = name
            kinds.setdefault(oid, str(p.get("highway")))

    groups = defaultdict(lambda: {"edges": [], "length": 0.0, "osm": set(), "kinds": set()})
    sans_nom = non_osm = 0
    for _, el in ET.iterparse(net, events=("end",)):
        if el.tag == "edge":
            eid = el.get("id")
            if el.get("function") != "internal" and el.get("from"):
                m = re.fullmatch(r"-?(\d+)(#\d+)?", eid)
                if not m:
                    non_osm += 1
                elif m.group(1) not in names:
                    sans_nom += 1
                else:
                    g = groups[names[m.group(1)]]
                    g["edges"].append(eid)
                    g["length"] += float(el.find("lane").get("length"))
                    g["osm"].add(m.group(1))
                    g["kinds"].add(kinds.get(m.group(1), ""))
            el.clear()

    streets, used = {}, set()
    for name in sorted(groups, key=lambda n: -groups[n]["length"]):
        g = groups[name]
        latin = split_aliases(name)[0] if split_aliases(name) else name
        base = slugify(latin) or f"rue-{sorted(g['osm'])[0]}"
        sid, k = base, 2
        while sid in used:
            sid, k = f"{base}-{k}", k + 1
        used.add(sid)
        kinds_txt = " ".join(g["kinds"])
        streets[sid] = {"name": name, "aliases": split_aliases(name),
                        "type": next((t for t in MAIN if t in kinds_txt), "autre"),
                        "length_m": round(g["length"], 1), "edges": sorted(g["edges"]),
                        "osm_ids": sorted(g["osm"])}
    return {"version": 1, "network": net.name, "streets": streets,
            "note": "length_m = somme des longueurs des tronçons, tous sens confondus"}, sans_nom, non_osm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, default=ROOT / "sim" / "hassan.net.xml")
    ap.add_argument("--edges", type=Path, default=ROOT / "data" / "network_edges.geojson")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "street_index.json")
    a = ap.parse_args()
    index, sans_nom, non_osm = build(a.net, a.edges)
    a.out.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    n_edges = sum(len(s["edges"]) for s in index["streets"].values())
    print(f"{len(index['streets'])} rues, {n_edges} tronçons -> {a.out}")
    print(f"ignorés : {sans_nom} tronçons sans nom, {non_osm} tronçons sans identifiant OSM")


if __name__ == "__main__":
    main()
