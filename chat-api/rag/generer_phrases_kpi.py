#!/usr/bin/env python3
"""Etape 3 du bloc RAG : genere les phrases-modeles des KPI.

Lit les fichiers KPI de data/ (source de verite des chiffres) et ecrit un
fichier texte de phrases, une phrase = un futur chunk Chroma (etape 4).

Usage :  python generer_phrases_kpi.py
Variables optionnelles : DATA_DIR (defaut "data"), OUT_FILE (defaut "docs/phrases_kpi.txt")
Chemins relatifs (Windows).  Aucune dependance hors bibliotheque standard.
"""
import json
import os
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "data"))
OUT = Path(os.environ.get("OUT_FILE", "docs/phrases_kpi.txt"))

TAG = "Données simulées (SUMO)."
AXE_ID = "4330541"          # rue de l'axe de la voie réservée (et de la rue fermée)
NB_RUES = 5                 # rues les plus congestionnées citées
SEUIL_NET = 2.0             # un écart est dit "net" si |moyenne| >= 2 x écart-type (à valider)
SEUIL_TERMINES = 0.02       # alerte si les trajets terminés diffèrent de plus de 2 %

# --- Configuration des scénarios -------------------------------------------
# Chaque scénario est comparé à SA référence (jamais mélangées).
SCENARIOS = {
    "actuel_ref": dict(nom="situation actuelle de référence", ref=None,
                       note="Elle sert de référence au scénario rue fermée."),
    "actuel_bus": dict(nom="situation actuelle avec ligne de bus", ref=None,
                       note="Elle sert de référence au scénario voie réservée."),
    "rue_fermee": dict(nom="rue fermée", ref="actuel_ref",
                       note="L'amélioration apparente est en partie un biais de sélection "
                            "(voitures sans itinéraire écartées, voir hypotheses.md)."),
    "voie_reservee": dict(nom="voie réservée aux bus", ref="actuel_bus",
                          note="Les chiffres du réseau (toutes les voitures) ne mesurent pas l'effet "
                               "sur l'axe : voir les phrases dédiées à l'axe et aux bus."),
    # référence à régénérer avec 500 trajets (point ouvert 2 du bilan) :
    "pic": dict(nom="pic de trafic (+30 %)", ref="actuel_500",
                note="La demande est supérieure de 30 % à celle de la situation actuelle."),
}
# kpi_actuel.json est exclu : il ne correspond à aucune simulation du dossier.
EXCLUS = {"kpi_actuel.json"}

NOMS_REF = {"actuel_ref": "situation actuelle de référence",
            "actuel_bus": "situation actuelle avec ligne de bus",
            "actuel_500": "situation actuelle à 500 trajets"}


# --- Formatage français -----------------------------------------------------
def nb(x, d=1):
    s = f"{x:,.{d}f}".replace(",", "\u202f").replace(".", ",")
    return "0" + s[s.find(","):] if s.startswith("-0,") and float(x) == 0 else s

def sg(x, d=1, unite=""):
    """Nombre signé avec vrai signe moins ; -0,0 devient 0,0."""
    if round(x, d) == 0:
        return f"0{',' + '0' * d if d else ''}{unite}"
    return ("+" if x > 0 else "−") + nb(abs(x), d) + unite

def pct(x, d=1):
    return nb(x * 100, d) + " %"

def rel(new, old):
    return None if not old else (new - old) / old * 100

def lire(nom):
    p = DATA / nom
    if nom in EXCLUS or not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def fin(texte, source):
    return f"{texte} {TAG} Source : {source}."


# --- Noms de rues (optionnel) -----------------------------------------------
def charger_noms():
    p = DATA / "network_edges.geojson"
    if not p.exists():
        return {}
    noms = {}
    for f in json.loads(p.read_text(encoding="utf-8"))["features"]:
        pr = f["properties"]
        n = pr.get("name")
        if isinstance(n, list):
            n = " / ".join(n)
        if n:
            noms[str(pr.get("osmid"))] = n
    return noms

def nom_rue(edge_id, noms):
    base = edge_id.lstrip("-").split("#")[0]
    return f"{edge_id} ({noms[base]})" if base in noms else f"{edge_id} (sans nom)"


# --- Modèle A : kpi_<scenario>.json ----------------------------------------
def phrases_scenario(sc, noms):
    cfg = SCENARIOS[sc]
    src = f"kpi_{sc}.json"
    k = lire(src)
    if k is None:
        return [(f"{sc}#absent", fin(f"Le scénario « {cfg['nom']} » n'a pas de fichier KPI exploitable.", src))]
    ref_id = cfg["ref"]
    kr = lire(f"kpi_{ref_id}.json") if ref_id else None
    ref_txt = NOMS_REF.get(ref_id)
    out = []

    # 1) résumé
    if ref_id is None:
        deb = f"Scénario « {cfg['nom']} » ({src}) : c'est une situation de référence. {cfg['note']}"
        cmp_ = ""
    elif kr is None:
        deb = (f"Scénario « {cfg['nom']} » ({src}), à comparer à la {ref_txt} "
               f"(kpi_{ref_id}.json) : cette référence n'est pas encore disponible, aucune comparaison "
               f"chiffrée n'est possible. {cfg['note']}")
        cmp_ = ""
    else:
        deb = (f"Scénario « {cfg['nom']} » ({src}), comparé à la {ref_txt} (kpi_{ref_id}.json). "
               f"{cfg['note']}")
        cmp_ = None
    corps = f"{k['trajets_termines']} trajets terminés"
    if kr:
        corps += f" contre {kr['trajets_termines']}"
    corps += ". "
    for lab, cle, d, u in [("Temps de trajet moyen", "temps_trajet_moyen_s", 1, " s"),
                           ("Vitesse moyenne", "vitesse_moyenne_kmh", 1, " km/h"),
                           ("CO₂ total", "co2_total_g", 0, " g")]:
        v = k[cle]
        corps += f"{lab} : {nb(v, d)}{u}"
        if kr:
            e = v - kr[cle]
            r = rel(v, kr[cle])
            if round(e, d) == 0:
                corps += f" ({'identique' if d == 0 else 'inchangé'} par rapport à la référence)"
            else:
                corps += f" contre {nb(kr[cle], d)}{u} ({sg(e, d, u)}" + (f", {sg(r, 1, ' %')}" if r is not None else "") + ")"
        corps += ". "
    if kr:
        a, b = k["trajets_termines"], kr["trajets_termines"]
        if b and abs(a - b) / b > SEUIL_TERMINES:
            corps += ("Attention : les nombres de trajets terminés diffèrent, donc le temps moyen et le CO₂ "
                      "total ne sont pas strictement comparables (le CO₂ total ne se compare qu'à demande "
                      "et durée égales). ")
    corps += "Un seul tirage : résultat indicatif."
    out.append((f"{sc}#resume", fin(deb + " " + corps, src)))

    # 2) congestion moyenne
    c = (f"Scénario « {cfg['nom']} » : congestion moyenne {pct(k['congestion_moyenne'])} "
         f"sur {k['rues_mesurees']} rues mesurées")
    if kr:
        c += (f", contre {pct(kr['congestion_moyenne'])} sur {kr['rues_mesurees']} rues pour la "
              f"{ref_txt} ({sg((k['congestion_moyenne'] - kr['congestion_moyenne']) * 100, 1, ' points')})")
    c += (f". Une rue est dite congestionnée dans un intervalle de 60 s si sa vitesse relative est "
          f"inférieure à {nb(k['seuil_congestion'], 1)} ; seules les rues avec au moins "
          f"{k['min_mesures']} mesures sont comptées. {k['trajets_termines']} trajets terminés. "
          "Le nombre de rues mesurées varie d'un scénario à l'autre : la comparaison est approximative.")
    out.append((f"{sc}#congestion", fin(c, src)))

    # 3) rues les plus congestionnées
    cr = k["congestion_par_rue"]
    tri = sorted(cr.items(), key=lambda kv: (-kv[1], kv[0]))
    n100 = sum(1 for v in cr.values() if v >= 1.0)
    items = []
    for rue, v in tri[:NB_RUES]:
        s = f"{nom_rue(rue, noms)} à {pct(v, 0)}"
        if kr:
            rv = kr["congestion_par_rue"].get(rue)
            s += f" (référence : {pct(rv, 0)})" if rv is not None else " (absente de la référence)"
        items.append(s)
    r = (f"Scénario « {cfg['nom']} » : {n100} rues sont congestionnées en permanence (100 % des intervalles). "
         f"{NB_RUES} d'entre elles, classées par taux puis par identifiant (liste non exhaustive, "
         f"l'ordre entre rues à égalité est arbitraire) : " + " ; ".join(items) + ". "
         f"{k['trajets_termines']} trajets terminés.")
    out.append((f"{sc}#rues", fin(r, src)))
    return out


# --- Modèle B : kpi_axe*.json, kpi_bus_*.json ------------------------------
def phrases_axe_bus():
    out = []
    # voie réservée : durées sur l'axe
    ax = lire("kpi_axe.json")
    if ax:
        a, v = ax["actuel_bus"], ax["voie_reservee"]
        e = v["duree_moyenne_s"] - a["duree_moyenne_s"]
        r = rel(v["duree_moyenne_s"], a["duree_moyenne_s"])
        t = (f"Scénario « voie réservée aux bus », axe {AXE_ID} : {v['n']} voitures de l'axe terminées "
             f"(contre {a['n']} en situation actuelle avec ligne de bus). Durée moyenne {nb(v['duree_moyenne_s'])} s "
             f"contre {nb(a['duree_moyenne_s'])} s pour la référence « actuel_bus » ({sg(e, 1, ' s')}, {sg(r, 1, ' %')}). "
             "Un seul tirage, sans écart-type : résultat indicatif, aucun écart n'est affirmé. "
             "[À VÉRIFIER : version du réseau de bus de kpi_axe.json.]")
        out.append(("axe_voie_reservee", fin(t, "kpi_axe.json")))
    # voie réservée : bus
    bu, bv = lire("kpi_bus_actuel_bus.json"), lire("kpi_bus_voie_reservee.json")
    if bu and bv:
        e = bv["axe_duree_moyenne_s"] - bu["axe_duree_moyenne_s"]
        ea = bv["axe_attente_moyenne_s"] - bu["axe_attente_moyenne_s"]
        r = rel(bv["axe_duree_moyenne_s"], bu["axe_duree_moyenne_s"])
        t = (f"Scénario « voie réservée aux bus », bus de l'axe {AXE_ID} : {bv['axe_bus_termines']} bus "
             f"comparables terminés (contre {bu['axe_bus_termines']} en situation actuelle avec ligne de bus ; "
             f"{bv['bus_non_comparables']} autres bus non comparables, écartés). "
             f"Durée moyenne {nb(bv['axe_duree_moyenne_s'])} s contre {nb(bu['axe_duree_moyenne_s'])} s "
             f"({sg(e, 1, ' s')}, {sg(r, 1, ' %')}). Attente moyenne {nb(bv['axe_attente_moyenne_s'])} s "
             f"contre {nb(bu['axe_attente_moyenne_s'])} s ({sg(ea, 1, ' s')}). "
             "Échantillon très petit et un seul tirage : résultat indicatif. "
             "L'attente des bus vient surtout des feux, que la voie réservée n'évite pas.")
        out.append(("bus_voie_reservee",
                    fin(t, "kpi_bus_voie_reservee.json et kpi_bus_actuel_bus.json")))
    # rue fermée : axe
    af = lire("kpi_axe_rue_fermee.json")
    if af:
        a, f = af["actuel_ref"], af["rue_fermee"]
        e = f["duree_moyenne_s"] - a["duree_moyenne_s"]
        t = (f"Scénario « rue fermée », axe {AXE_ID} : {af['voitures_axe']} voitures empruntent l'axe en "
             f"situation actuelle ; {af['sans_itineraire']} n'ont plus d'itinéraire et {af['deviees']} sont "
             f"déviées. Sur les {f['n']} voitures comparables terminées, durée moyenne {nb(f['duree_moyenne_s'])} s "
             f"contre {nb(a['duree_moyenne_s'])} s pour la référence « actuel_ref » ({sg(e, 1, ' s')}). "
             "Cette baisse est un biais de sélection : les voitures sans itinéraire sont exclues de la "
             "comparaison, elle ne prouve pas un gain. Un seul tirage : résultat indicatif.")
        out.append(("axe_rue_fermee", fin(t, "kpi_axe_rue_fermee.json")))
    return out


# --- Modèle C : tirages_rue_fermee.json ------------------------------------
def phrase_tirages():
    d = lire("tirages_rue_fermee.json")
    if not d:
        return []
    tir = d["tirages"]
    fa = sorted({x["finis_actuel"] for x in tir})
    ff = sorted({x["finis_fermee"] for x in tir})
    comp = sorted({x["axe_comparables"] for x in tir})
    plage = lambda L: str(L[0]) if len(L) == 1 else f"{L[0]} à {L[-1]}"

    def verdict(m, s):
        return "écart net" if s and abs(m) >= SEUIL_NET * s else "écart non net (inférieur à 2 fois l'écart-type)"

    m, s = d["ecart_moyen_axe_s"], d["ecart_type_axe_s"]
    mt, st = d["ecart_moyen_tous_s"], d["ecart_type_tous_s"]
    t = (f"Scénario « rue fermée » sur {d['n_tirages']} tirages (graines 1 à {d['n_tirages']}, "
         f"{d['fin_simulation_s']} s), comparé à la situation actuelle : {plage(ff)} trajets terminés "
         f"contre {plage(fa)} par tirage. Sur l'axe ({d['voitures_axe']} voitures, dont {plage(comp)} "
         f"comparables par tirage), écart moyen {sg(m, 1, ' s')}, écart-type {nb(s)} s, "
         f"plus rapide dans {d['plus_rapide']} tirages sur {d['n_tirages']} et plus lent dans {d['plus_lent']} : "
         f"{verdict(m, s)}. Sur l'ensemble des voitures, écart moyen {sg(mt, 1, ' s')}, "
         f"écart-type {nb(st)} s : {verdict(mt, st)}. "
         "Le gain sur l'axe est à lire avec le biais de sélection des voitures sans itinéraire.")
    return [("tirages_rue_fermee", fin(t, "tirages_rue_fermee.json"))]


SCENARIO_SPECIAL = {"axe_voie_reservee": "voie_reservee", "bus_voie_reservee": "voie_reservee",
                    "axe_rue_fermee": "rue_fermee", "tirages_rue_fermee": "rue_fermee"}

def scenario_de(pid):
    """Scénario de la phrase, pour les métadonnées Chroma (étape 4)."""
    return SCENARIO_SPECIAL.get(pid) or pid.split("#")[0]

def source_de(txt):
    """Fichier(s) source cité(s) à la fin de la phrase."""
    return txt.rsplit("Source : ", 1)[1].rstrip(".")


def main():
    noms = charger_noms()
    blocs = [("MODÈLE A : un fichier kpi_<scenario>.json (3 phrases par scénario)", [])]
    for sc in SCENARIOS:
        blocs[0][1].extend(phrases_scenario(sc, noms))
    blocs.append(("MODÈLE B : kpi_axe*.json et kpi_bus_*.json (axe et bus)", phrases_axe_bus()))
    blocs.append(("MODÈLE C : tirages_rue_fermee.json", phrase_tirages()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lignes = ["# Phrases-modèles des KPI (généré par generer_phrases_kpi.py, ne pas éditer à la main)",
              f"# Exclus : {', '.join(sorted(EXCLUS))}. {TAG}", ""]
    n = 0
    for titre, phr in blocs:
        lignes += [f"## {titre}", ""]
        for pid, txt in phr:
            lignes += [f"[{pid} | scenario={scenario_de(pid)} | source={source_de(txt)}]", txt, ""]
            n += 1
    OUT.write_text("\n".join(lignes), encoding="utf-8")
    print(f"{n} phrases écrites dans {OUT}")


if __name__ == "__main__":
    main()
