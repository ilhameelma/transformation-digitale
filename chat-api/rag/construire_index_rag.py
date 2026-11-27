#!/usr/bin/env python3
"""Etape 4 du bloc RAG : decouper, calculer les embeddings, indexer dans Chroma.

Entrees  : docs/*.md  (textes decoupes en morceaux de 300 a 500 mots, chevauchement)
           docs/phrases_kpi.txt  (une phrase KPI = un morceau entier, jamais coupe)
Sortie   : data/chroma  (index jetable : on le reconstruit entierement a chaque lancement)

Usage :
    python construire_index_rag.py --dry-run   # decoupe et compte, sans embeddings ni Chroma
    python construire_index_rag.py             # indexation complete
Variables optionnelles : DOCS_DIR, CHROMA_DIR, EMBED_MODEL.  Chemins relatifs (Windows).
"""
import argparse
import os
import re
from collections import Counter
from pathlib import Path

DOCS = Path(os.environ.get("DOCS_DIR", "docs"))
CHROMA_DIR = os.environ.get("CHROMA_DIR", "data/chroma")
COLLECTION = "jumeau_docs"
# multilingual-e5-small accepte 512 tokens ; paraphrase-multilingual-MiniLM-L12-v2 tronque a 128 tokens
# (soit ~80 mots), ce qui rendrait inutiles des morceaux de 300 a 500 mots.
MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
PREFIX_PASSAGE = "passage: " if "e5" in MODEL else ""

MIN_MOTS, MAX_MOTS, CHEVAUCHEMENT = 160, 240, 40

# Scenario associe a chaque document ; "general" par defaut.
SCENARIO_DOC = {"rue_fermee.md": "rue_fermee", "voie_reservee.md": "voie_reservee", "zone.md": "zone"}


# --- Decoupage --------------------------------------------------------------
def unites(texte):
    """Paragraphes ; un paragraphe de plus de MAX_MOTS est redecoupe par phrases."""
    out = []
    for par in re.split(r"\n\s*\n", texte.strip()):
        par = par.strip()
        if not par:
            continue
        if len(par.split()) <= MAX_MOTS:
            out.append(par)
            continue
        cur = []
        for ph in re.split(r"(?<=[.!?])\s+", par):
            if cur and len(" ".join(cur + [ph]).split()) > MAX_MOTS:
                out.append(" ".join(cur))
                cur = []
            cur.append(ph)
        if cur:
            out.append(" ".join(cur))
    return out


def decouper(texte):
    """Retourne une liste de (section, texte). Chevauchement : derniers mots du morceau precedent."""
    morceaux, cur, nouveaux, section, section_debut = [], [], 0, "", ""

    def vider():
        nonlocal cur, nouveaux, section_debut
        if nouveaux:  # pas de morceau fait uniquement de chevauchement
            morceaux.append((section_debut, "\n\n".join(cur)))
        queue = " ".join(" ".join(cur).split()[-CHEVAUCHEMENT:]) if cur else ""
        cur, nouveaux = ([queue] if queue else []), 0
        section_debut = section

    for u in unites(texte):
        est_titre = u.startswith("#")
        if est_titre:
            section = u.lstrip("# ").strip()
        w = len(u.split())
        mots_cur = len(" ".join(cur).split())
        if cur and nouveaux and (mots_cur + w > MAX_MOTS or (est_titre and mots_cur >= MIN_MOTS)):
            vider()
        if not nouveaux:
            section_debut = section
        cur.append(u)
        nouveaux += w
    vider()
    return morceaux


def lire_phrases_kpi(chemin):
    """Blocs '[id | scenario=... | source=...]' suivis d'une ligne de texte."""
    out = []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(lignes):
        m = re.match(r"\[(.+?) \| scenario=(.+?) \| source=(.+)\]$", l)
        if m:
            out.append((m.group(1), m.group(2), m.group(3), lignes[i + 1].strip()))
    return out


def construire_morceaux():
    """Liste de dicts : id, text, meta (scenario, type, source, section)."""
    res = []
    for f in sorted(DOCS.glob("*.md")):
        for n, (section, txt) in enumerate(decouper(f.read_text(encoding="utf-8"))):
            res.append(dict(id=f"{f.stem}#{n}", text=txt,
                            meta=dict(scenario=SCENARIO_DOC.get(f.name, "general"), type="doc",
                                      source=f.name, section=section)))
    kpi = DOCS / "phrases_kpi.txt"
    if kpi.exists():
        for pid, scen, src, txt in lire_phrases_kpi(kpi):
            res.append(dict(id=f"kpi:{pid}", text=txt,
                            meta=dict(scenario=scen, type="kpi", source=src, section="")))
    return res


# --- Rapport et verification -----------------------------------------------
def rapport(morceaux):
    print(f"\n{len(morceaux)} morceaux au total")
    print("  par type    :", dict(Counter(m["meta"]["type"] for m in morceaux)))
    print("  par scenario:", dict(Counter(m["meta"]["scenario"] for m in morceaux)))
    print("  par source  :", dict(Counter(m["meta"]["source"] for m in morceaux)))
    docs = [len(m["text"].split()) for m in morceaux if m["meta"]["type"] == "doc"]
    if docs:
        print(f"  textes (mots) : min {min(docs)}, max {max(docs)}, moyenne {sum(docs)//len(docs)}")
        trop = [m["id"] for m in morceaux if m["meta"]["type"] == "doc" and len(m["text"].split()) > MAX_MOTS]
        if trop:
            print("  ATTENTION morceaux > %d mots : %s" % (MAX_MOTS, trop))
    kpi = [len(m["text"].split()) for m in morceaux if m["meta"]["type"] == "kpi"]
    if kpi:
        print(f"  phrases KPI (mots) : min {min(kpi)}, max {max(kpi)}")
    ids = [m["id"] for m in morceaux]
    assert len(ids) == len(set(ids)), "identifiants en double"


def indexer(morceaux):
    import chromadb
    from sentence_transformers import SentenceTransformer

    modele = SentenceTransformer(MODEL)
    print(f"\nModele : {MODEL} (longueur max {modele.max_seq_length} tokens)")
    # --- vérification de troncature (à ajouter) ---
    tronques = 0
    for m in morceaux:
        n = len(modele.tokenizer.encode(PREFIX_PASSAGE + m["text"]))
        if n > modele.max_seq_length:
            tronques += 1
            print(f"  TRONQUE : {m['id']} ({n} tokens)")
    print(f"  {tronques} morceau(x) tronqué(s) sur {len(morceaux)}")
    # ----------------------------------------------
    vecteurs = modele.encode([PREFIX_PASSAGE + m["text"] for m in morceaux],
                             normalize_embeddings=True, show_progress_bar=True).tolist()
    Path(CHROMA_DIR).parent.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION)   # index jetable : reconstruit a chaque lancement
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine", "model": MODEL})
    col.add(ids=[m["id"] for m in morceaux], documents=[m["text"] for m in morceaux],
            embeddings=vecteurs, metadatas=[m["meta"] for m in morceaux])
    print(f"Indexes dans Chroma ({CHROMA_DIR}) : {col.count()} / {len(morceaux)} attendus")
    assert col.count() == len(morceaux), "le nombre de morceaux indexes ne correspond pas"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="decouper et compter seulement")
    args = ap.parse_args()
    morceaux = construire_morceaux()
    if not morceaux:
        raise SystemExit(f"Aucun morceau : verifier {DOCS}/ (fichiers .md et phrases_kpi.txt)")
    rapport(morceaux)
    if not args.dry_run:
        indexer(morceaux)


if __name__ == "__main__":
    main()
