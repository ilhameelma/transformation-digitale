#!/usr/bin/env python3
"""Etape 5 du bloc RAG : tester la recherche Chroma sans LLM.

Pour chaque question : les 3 morceaux les plus proches sont affiches, et le test est reussi
si l'un d'eux vient d'une source attendue.  La question hors sujet n'a pas de source attendue :
on releve sa distance pour fixer le seuil de l'etape 6.

Usage (depuis la racine du projet) :  python chat-api/rag/tester_recherche_rag.py
Variables optionnelles : CHROMA_DIR.  Chemins relatifs (Windows).
"""
import os
import sys

CHROMA_DIR = os.environ.get("CHROMA_DIR", "data/chroma")
COLLECTION = "jumeau_docs"
K = 3

KPI_BUS = "kpi_bus_voie_reservee.json et kpi_bus_actuel_bus.json"

# (question, sources attendues).  A ADAPTER a tes .md : mets la source qui contient la reponse.
QUESTIONS = [
    ("Pourquoi l'amélioration apparente de la rue fermée est-elle trompeuse ?",
     {"hypotheses.md", "rue_fermee.md", "kpi_axe_rue_fermee.json", "tirages_rue_fermee.json"}),
    ("Combien de temps les bus attendent-ils avec la voie réservée ?",
     {KPI_BUS, "voie_reservee.md", "hypotheses.md"}),
    ("Quelle est la référence de comparaison du scénario pic de trafic ?",
     {"references_comparaison.md", "kpi_pic.json"}),
    ("Quel est le temps de trajet moyen dans le scénario rue fermée ?",
     {"kpi_rue_fermee.json"}),
    ("Quelles sont les limites d'un seul tirage de simulation ?",
     {"hypotheses.md"}),
    ("Quelle est la surface de la zone simulée ?",
     {"zone.md"}),
    ("Combien de bus circulent en situation actuelle et avec la voie réservée ?",
     {"hypotheses.md", "voie_reservee.md", "references_comparaison.md", KPI_BUS}),
    ("Quelles rues sont les plus congestionnées avec le pic de trafic ?",
     {"kpi_pic.json"}),
    ("Comment la voie réservée change-t-elle la durée des voitures sur l'axe ?",
     {"kpi_axe.json", "voie_reservee.md"}),
    # --- hors sujet : aucune source attendue (None) ---
    ("Quelle est la capitale de la France ?", None),
    ("Comment préparer une pizza margherita ?", None),
    ("Qui a gagné la Coupe du monde de football en 2022 ?", None),
    ("Quel temps fait-il demain à Rabat ?", None),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")       # accents et arabe sous Windows
    import chromadb
    from sentence_transformers import SentenceTransformer

    col = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    modele_nom = col.metadata["model"]
    modele = SentenceTransformer(modele_nom)
    prefixe = "query: " if "e5" in modele_nom else ""
    print(f"Collection : {col.count()} morceaux | modèle : {modele_nom}\n")

    reussis, total, dist_ok, dist_hors = 0, 0, [], []
    for i, (q, attendues) in enumerate(QUESTIONS, 1):
        vec = modele.encode([prefixe + q], normalize_embeddings=True).tolist()
        r = col.query(query_embeddings=vec, n_results=K,
                      include=["documents", "metadatas", "distances"])
        print(f"Q{i}. {q}")
        trouve = False
        for rang, (id_, meta, dist, doc) in enumerate(
                zip(r["ids"][0], r["metadatas"][0], r["distances"][0], r["documents"][0]), 1):
            ok = attendues is not None and meta["source"] in attendues
            trouve = trouve or ok
            print(f"   {rang}. {'✔' if ok else ' '} {id_:<32} dist={dist:.3f}  {doc[:90]!r}")
        if attendues is None:
            dist_hors.append(r["distances"][0][0])
            print(f"   → hors sujet : meilleure distance {dist_hors[-1]:.3f}\n")
        else:
            total += 1
            reussis += trouve
            if trouve:
                dist_ok.append(min(d for d, m in zip(r["distances"][0], r["metadatas"][0])
                                   if m["source"] in attendues))
            print(f"   → {'RÉUSSI' if trouve else 'ÉCHEC'}\n")

    print(f"Résultat : {reussis}/{total} questions avec la bonne source dans les {K} premiers.")
    if dist_ok and dist_hors:
        print(f"Distance du bon morceau : de {min(dist_ok):.3f} à {max(dist_ok):.3f} ; "
              f"hors sujet : de {min(dist_hors):.3f} à {max(dist_hors):.3f}")
        milieu = (max(dist_ok) + min(dist_hors)) / 2
        if max(dist_ok) < min(dist_hors):
            print(f"→ séparation nette : seuil possible autour de {milieu:.3f}")
        else:
            print("→ chevauchement : un seuil de distance ne suffira pas à tout séparer")


if __name__ == "__main__":
    main()
