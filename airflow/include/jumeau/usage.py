"""Classement des rues par usage, pour le précalcul en lot (DAG precompute_top_streets)."""
import xml.etree.ElementTree as ET
from collections import Counter

from . import config as C
from .street_index import load_streets


def rank_streets_by_usage(min_length_m=None):
    """[(street_id, nom, nombre de voitures, longueur)] triées par usage décroissant.

    Usage d'une rue = nombre de voitures de la demande de référence dont l'itinéraire passe par au moins un
    de ses tronçons (une voiture compte une fois par rue). Les rues plus courtes que min_length_m (100 m par
    défaut, comme sim/senario_rue_prive/count_usage.py) sont ignorées.
    """
    min_length_m = C.MIN_LENGTH_M if min_length_m is None else min_length_m
    streets = load_streets()
    edge_to_street = {e: sid for sid, s in streets.items() for e in s["edges"]}
    counts = Counter()
    for _, el in ET.iterparse(C.ROU_REF, events=("end",)):
        if el.tag == "vehicle":
            hit = set()
            for route in el.iter("route"):
                hit |= {edge_to_street[e] for e in (route.get("edges") or "").split() if e in edge_to_street}
            counts.update(hit)
            el.clear()
    rows = [(sid, s.get("name", sid), counts[sid], s.get("length_m", 0)) for sid, s in streets.items()
            if s.get("length_m", 0) >= min_length_m and counts[sid] > 0]
    return sorted(rows, key=lambda r: (-r[2], r[0]))
