"""
check_closure_sumo.py - retrouve dans le reseau SUMO la chaine d'aretes de la section fermee.
Part du noeud de depart et du noeud d'arrivee de data/closure.json, puis suit la voie.
Ecrit data/closure_sumo.json.
"""
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib

DATA = Path(__file__).resolve().parent.parent / "data"
closure = json.loads((DATA / "closure.json").read_text(encoding="utf-8"))
osm = {str(e["osmid"]) for e in closure["edges"]}
us = {str(e["u"]) for e in closure["edges"]}
vs = {str(e["v"]) for e in closure["edges"]}
start_node = (us - vs).pop()   # noeud OSM de depart de la section
end_node = (vs - us).pop()     # noeud OSM d'arrivee


def tokens(node_id):
    """Les ids OSM contenus dans un id de noeud SUMO (simple ou 'cluster_a_b_c_#2more')."""
    return set(node_id.split("_"))


net = sumolib.net.readNet(str(DATA / "hassan.net.xml"))
cand = [e for e in net.getEdges(withInternal=False) if e.getID().split("#")[0] in osm]

starts = [e for e in cand if start_node in tokens(e.getFromNode().getID())]
if not starts:
    raise SystemExit(f"Aucune arete ne part du noeud {start_node}")

chain = [starts[0]]
for _ in range(50):
    cur = chain[-1]
    if end_node in tokens(cur.getToNode().getID()):
        break
    nxt = [e for e in cur.getOutgoing() if e.getID().split("#")[0] in osm and e not in chain]
    if not nxt:
        raise SystemExit(f"Chaine interrompue apres {cur.getID()}")
    chain.append(nxt[0])
else:
    raise SystemExit("Chaine trop longue : verifier le reseau")

total = sum(e.getLength() for e in chain)
print(f"Depart : noeud OSM {start_node} / arrivee : noeud OSM {end_node}\n")
for e in chain:
    lat1 = net.convertXY2LonLat(*e.getFromNode().getCoord())[1]
    lat2 = net.convertXY2LonLat(*e.getToNode().getCoord())[1]
    print(f"  {e.getID():<14} {e.getLength():7.1f} m  {e.getLaneNumber()} voie(s)  lat {lat1:.5f} -> {lat2:.5f}")
print(f"\nSection fermee dans SUMO : {len(chain)} aretes, {total:.0f} m (attendu ~486 m)")
first = net.convertXY2LonLat(*chain[0].getFromNode().getCoord())[1]
last = net.convertXY2LonLat(*chain[-1].getToNode().getCoord())[1]
print(f"Sens : vers le {'nord' if last > first else 'sud'} (attendu : nord)")

(DATA / "closure_sumo.json").write_text(
    json.dumps({"edges": [e.getID() for e in chain], "total_length_m": round(total, 1)}, indent=2),
    encoding="utf-8")
print("Ecrit : data/closure_sumo.json")