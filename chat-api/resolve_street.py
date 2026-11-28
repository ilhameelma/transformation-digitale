"""resolve_street : texte libre -> street_id (liste blanche)."""
import json
import re
import sys
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

INDEX_PATH = Path("data/street_index.json")
SEUIL_TROUVE = 90     # score minimum pour dire "trouvé"
ECART_MIN = 8         # écart minimum avec la 2e rue pour dire "trouvé"
SEUIL_CANDIDAT = 75   # en dessous, on ne propose pas la rue

ROMAINS = {"1": "i", "2": "ii", "5": "v", "6": "vi"}
TYPES = {"avenue", "rue", "boulevard", "place", "impasse", "route"}
# mots qui ne servent pas à identifier une rue
GENERIQUES = TYPES | {"av", "bd", "de", "la", "le", "les", "des", "du", "d"}


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("mohammed", "mohamed").replace("benabdellah", "ben abdellah")
    t = re.sub(r"[^\w\s]", " ", t)  # \w garde aussi les lettres arabes
    return " ".join(ROMAINS.get(m, m) for m in t.split())


def _utile(norm: str) -> str:
    return " ".join(m for m in norm.split() if m not in GENERIQUES)


def _type(norm: str):
    return next((m for m in norm.split() if m in TYPES), None)


def _charger() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))["streets"]


def resolve_street(texte: str) -> dict:
    streets = _charger()
    req = normaliser(texte)
    req_utile = _utile(req)
    if not req_utile:
        return {"statut": "introuvable", "message": "Aucun nom de rue reconnaissable."}
    type_req = _type(req)

    meilleur = {}  # meilleur score par street_id
    for sid, s in streets.items():
        for nom in [s["name"]] + list(s.get("aliases", [])):
            cle = normaliser(nom)
            cle_utile = _utile(cle)
            if not cle_utile:
                continue
            score = fuzz.token_set_ratio(req_utile, cle_utile)
            type_cle = _type(cle)
            if type_req and type_cle and type_req != type_cle:
                score -= 10  # "avenue" demandé, "place" trouvé
            if score > meilleur.get(sid, 0):
                meilleur[sid] = score

    classes = sorted(meilleur.items(), key=lambda kv: kv[1], reverse=True)
    candidats = [
        {"street_id": sid, "name": streets[sid]["name"],
         "length_m": streets[sid].get("length_m"), "score": round(sc, 1)}
        for sid, sc in classes if sc >= SEUIL_CANDIDAT
    ][:5]

    if not candidats:
        return {"statut": "introuvable", "message": "Aucune rue ne correspond."}

    ecart = candidats[0]["score"] - (candidats[1]["score"] if len(candidats) > 1 else 0)
    if candidats[0]["score"] >= SEUIL_TROUVE and ecart >= ECART_MIN:
        c = candidats[0]
        return {"statut": "trouve", "street_id": c["street_id"],
                "name": c["name"], "score": c["score"]}
    return {"statut": "ambigu", "candidats": candidats}


if __name__ == "__main__":
    print(json.dumps(resolve_street(" ".join(sys.argv[1:])),
                     ensure_ascii=False, indent=2))