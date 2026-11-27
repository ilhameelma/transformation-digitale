"""Lecture de data/street_index.json et liste blanche des street_id.

Le street_id reçu par un DAG (donc, en bout de chaîne, le texte d'un utilisateur) n'est jamais utilisé
tel quel : il doit exister dans l'index. Les tronçons à fermer viennent de l'index, jamais de la requête.

Format attendu (voir tools/build_street_index.py) :
{"version": 1, "streets": {"<street_id>": {"name": str, "aliases": [str], "type": str,
                                            "length_m": float, "edges": ["4330541#3", ...]}}}
"""
import json

from . import config as C


class StreetError(ValueError):
    """street_id invalide ou inconnu. Erreur définitive : inutile de réessayer."""


def load_streets(path=None):
    path = path or C.STREET_INDEX
    if not path.exists():
        raise StreetError(f"{path} introuvable : générer l'index (tools/build_street_index.py)")
    data = json.loads(path.read_text(encoding="utf-8"))
    streets = data.get("streets")
    if not isinstance(streets, dict) or not streets:
        raise StreetError(f"{path} : clé 'streets' absente ou vide")
    return streets


def is_valid_id(street_id):
    return isinstance(street_id, str) and bool(C.STREET_ID_RE.match(street_id))


def get_street(street_id):
    """Rue de l'index, ou StreetError. Premier contrôle : la forme ; second : l'appartenance à l'index."""
    if not is_valid_id(street_id):
        raise StreetError("street_id invalide (attendu : minuscules, chiffres et tirets, 64 caractères au plus)")
    street = load_streets().get(street_id)
    if street is None:
        raise StreetError(f"street_id inconnu : {street_id!r} (absent de street_index.json)")
    if not street.get("edges"):
        raise StreetError(f"{street_id} : aucun tronçon dans l'index")
    return street
