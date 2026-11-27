#!/usr/bin/env python3
"""Etape 6 du bloc RAG : outil `search_docs` du chatbot (recherche dans Chroma, avec seuil).

Fonction a appeler depuis chat-api :
    from rag.search_docs import search_docs
    res = search_docs("pourquoi les bus attendent autant ?")
    res = search_docs("limites du pic", scenario="pic")          # filtre optionnel
    res["status"]  -> "ok" ou "aucun_resultat"

Test en ligne de commande (depuis la racine du projet) :
    python chat-api/rag/search_docs.py "pourquoi les bus attendent autant ?"
Variables optionnelles : CHROMA_DIR, RAG_SEUIL (distance cosinus maximale), RAG_K.
"""
import os
import sys

CHROMA_DIR = os.environ.get("CHROMA_DIR", "data/chroma")
COLLECTION = "jumeau_docs"
SEUIL = float(os.environ.get("RAG_SEUIL", "0.18"))   # provisoire : voir tester_recherche_rag.py
K = int(os.environ.get("RAG_K", "5"))
RAPPEL = "Données simulées (SUMO)."

_cache = {}

# --- Description de l'outil, donnee au LLM (a adapter au format de ton fournisseur) ----------
TOOL_NAME = "search_docs"
TOOL_DESCRIPTION = (
    "Recherche dans les documents écrits du projet (rapport, hypothèses, limites, description "
    "de la zone et des scénarios, phrases de résultats). À utiliser pour les explications, "
    "hypothèses, limites et résultats écrits, par exemple : « pourquoi les bus attendent autant ? », "
    "« quelles sont les limites de la rue fermée ? ». Ne pas utiliser pour lancer une simulation "
    "(outil trigger_simulation) ni pour obtenir la valeur exacte d'un indicateur (outil get_kpi). "
    "Renvoie jusqu'à 5 extraits avec leur source, ou un message indiquant qu'aucun passage "
    "pertinent n'a été trouvé."
)
TOOL_PARAMETERS = {   # schéma JSON des arguments
    "type": "object",
    "properties": {
        "question": {"type": "string",
                     "description": "La question de l'utilisateur, reformulée si besoin en une phrase complète."},
        "scenario": {"type": "string",
                     "enum": ["rue_fermee", "voie_reservee", "pic", "actuel_ref", "actuel_bus", "zone", "general"],
                     "description": "Optionnel : limiter la recherche à un scénario."},
    },
    "required": ["question"],
}
MESSAGE_VIDE = ("Aucun passage pertinent n'a été trouvé dans les documents du projet. "
                "Réponds que tu n'as pas cette information.")


def _charger():
    """Charge le modele et la collection une seule fois (le modele met quelques secondes)."""
    if not _cache:
        import chromadb
        from sentence_transformers import SentenceTransformer
        col = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
        nom = col.metadata["model"]            # meme modele que a l'indexation
        _cache.update(col=col, modele=SentenceTransformer(nom),
                      prefixe="query: " if "e5" in nom else "")
    return _cache["modele"], _cache["col"], _cache["prefixe"]


def search_docs(question, scenario=None, type_=None, k=K, seuil=SEUIL):
    """Retourne les morceaux les plus proches de la question, ceux plus loin que `seuil` sont ecartes.

    scenario : filtre optionnel (rue_fermee, voie_reservee, pic, actuel_ref, actuel_bus, zone, general)
    type_    : filtre optionnel ("doc" ou "kpi")
    """
    question = (question or "").strip()
    base = {"question": question, "seuil": seuil, "rappel": RAPPEL}
    if not question:
        return {**base, "status": "aucun_resultat", "resultats": [], "message": MESSAGE_VIDE}

    modele, col, prefixe = _charger()
    filtres = [{"scenario": scenario}] if scenario else []
    if type_:
        filtres.append({"type": type_})
    where = filtres[0] if len(filtres) == 1 else ({"$and": filtres} if filtres else None)

    vec = modele.encode([prefixe + question], normalize_embeddings=True).tolist()
    r = col.query(query_embeddings=vec, n_results=k, where=where,
                  include=["documents", "metadatas", "distances"])
    resultats = []
    for id_, doc, meta, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
        if dist <= seuil:
            resultats.append({"id": id_, "texte": doc, "source": meta["source"],
                              "scenario": meta["scenario"], "type": meta["type"],
                              "section": meta.get("section", ""), "distance": round(dist, 3)})
    if not resultats:
        return {**base, "status": "aucun_resultat", "resultats": [], "message": MESSAGE_VIDE}
    return {**base, "status": "ok", "resultats": resultats}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    q = " ".join(sys.argv[1:]) or "pourquoi les bus attendent autant ?"
    res = search_docs(q)
    print(f"Question : {q}\nStatut : {res['status']} (seuil {res['seuil']})\n")
    for x in res["resultats"]:
        print(f"- {x['id']}  [{x['type']} | {x['scenario']} | {x['source']}]  dist={x['distance']}")
        print(f"  {x['texte'][:160]!r}\n")
