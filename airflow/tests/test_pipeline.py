import json
import os
import sys
import time

import pytest

from conftest import REPO, needs_sumo
from jumeau import config as C
from jumeau import scenario as S
from jumeau.street_index import StreetError, get_street
from jumeau.usage import rank_streets_by_usage

ALLAL = "avenue-allal-ben-abdellah"


def section_allal():
    """Les 8 tronçons du scénario déjà simulé par l'équipe (data/closure_sumo.json)."""
    return json.loads((REPO / "data" / "closure_sumo.json").read_text(encoding="utf-8"))["edges"]


# ------------------------------------------------------------------------------------------ index des rues
def test_index_ids_valides_et_tronconts_uniques(env):
    streets = json.loads(C.STREET_INDEX.read_text(encoding="utf-8"))["streets"]
    assert all(C.STREET_ID_RE.match(sid) for sid in streets)
    tous = [e for s in streets.values() for e in s["edges"]]
    assert len(tous) == len(set(tous)), "un tronçon appartient à une seule rue"
    nets = S._edge_nodes()
    assert set(tous) <= set(nets), "tous les tronçons de l'index existent dans le réseau"
    assert set(section_allal()) <= set(streets[ALLAL]["edges"])


@pytest.mark.parametrize("bad", ["../x", "a/b", "A", "a b", "", None, "x" * 80, "a;rm -rf /", "-abc", ".hidden"])
def test_street_id_invalide_refuse_sans_rien_creer(env, bad):
    with pytest.raises(StreetError):
        S.prepare(bad, "run1")
    S.mark_failed(bad, "run1", "x")             # ne doit rien créer non plus
    assert not C.SCENARIOS.exists()


def test_street_id_inconnu_refuse(env):
    with pytest.raises(StreetError):
        get_street("rue-qui-nexiste-pas")
    assert not C.SCENARIOS.exists()


# ------------------------------------------------------------------------------------ règle de fermeture
def test_fermeture_identique_a_celle_de_l_equipe(env, monkeypatch):
    """Même ensemble de rues fermées que sim/senario_rue_fermee/common.py sur la section déjà simulée."""
    monkeypatch.setenv("DATA_DIR", str(REPO / "data"))
    monkeypatch.syspath_prepend(str(REPO / "sim" / "senario_rue_fermee"))
    sys.modules.pop("common", None)
    import common
    rue, transv = S.compute_closure(section_allal(), close_crossings=True)
    assert set(rue) | set(transv) == set(common.troncons_fermes())
    sys.modules.pop("common", None)


def test_sans_fermer_les_carrefours_seule_la_rue_est_fermee(env):
    rue, transv = S.compute_closure(section_allal(), close_crossings=False)
    assert rue == sorted(section_allal()) and transv == []


def test_demi_tour_aux_extremites_n_est_pas_un_carrefour_interieur(env, monkeypatch):
    """Rue à double sens A-B-C : seul B (traversé) ferme ses rues transversales, pas les extrémités A et C."""
    reseau = {"AB": ("A", "B"), "BA": ("B", "A"), "BC": ("B", "C"), "CB": ("C", "B"),     # la rue
              "XB": ("X", "B"), "BX": ("B", "X"),                                           # transversale en B
              "YA": ("Y", "A"), "AY": ("A", "Y"), "ZC": ("Z", "C"), "CZ": ("C", "Z")}       # extrémités
    monkeypatch.setattr(S, "_edge_nodes", lambda: reseau)
    rue, transv = S.compute_closure(["AB", "BA", "BC", "CB"], close_crossings=True)
    assert rue == ["AB", "BA", "BC", "CB"]
    assert transv == ["BX", "XB"]


def test_rue_a_sens_unique_ferme_ses_carrefours_interieurs(env, monkeypatch):
    """Rue à sens unique A->B->C->D : les rues transversales de B et C sont fermées, pas celles de A et D."""
    reseau = {"AB": ("A", "B"), "BC": ("B", "C"), "CD": ("C", "D"),
              "XB": ("X", "B"), "CY": ("C", "Y"), "PA": ("P", "A"), "DQ": ("D", "Q")}
    monkeypatch.setattr(S, "_edge_nodes", lambda: reseau)
    assert S.compute_closure(["AB", "BC", "CD"], close_crossings=True)[1] == ["CY", "XB"]


# --------------------------------------------------------------------------------------------- simulation
@needs_sumo
def test_regression_reproduit_les_resultats_de_l_equipe(env):
    """Rejoue la section déjà simulée par l'équipe : mêmes indicateurs, mêmes trajectoires, mêmes écarts."""
    res = S.run_pipeline(ALLAL, "regression", edges=section_allal())
    assert res["state"] == "ready"
    d = C.SCENARIOS / ALLAL
    mine = json.loads((d / "kpi_rue_fermee.json").read_text(encoding="utf-8"))
    theirs = json.loads((REPO / "data" / "kpi_rue_fermee.json").read_text(encoding="utf-8"))
    for k in ("trajets_termines", "temps_trajet_moyen_s", "vitesse_moyenne_kmh", "co2_total_g",
              "congestion_moyenne", "rues_mesurees", "congestion_par_rue"):
        assert mine[k] == theirs[k], k
    assert json.loads((d / "trajectories_rue_fermee.json").read_text(encoding="utf-8")) == \
        json.loads((REPO / "data" / "trajectories_rue_fermee.json").read_text(encoding="utf-8"))
    axe = json.loads((REPO / "data" / "kpi_axe_rue_fermee.json").read_text(encoding="utf-8"))
    imp = json.loads((d / "meta.json").read_text(encoding="utf-8"))["impact"]
    assert (imp["voitures_concernees"], imp["deviees"], imp["sans_itineraire"], imp["comparables"]) == \
        (axe["voitures_axe"], axe["deviees"], axe["sans_itineraire"], axe["comparables"])
    assert imp["duree_moyenne_actuel_s"] == axe["actuel_ref"]["duree_moyenne_s"]
    assert imp["duree_moyenne_rue_fermee_s"] == axe["rue_fermee"]["duree_moyenne_s"]


@needs_sumo
def test_rue_entiere_publie_les_fichiers_et_aucune_voiture_sur_la_rue_fermee(env):
    S.run_pipeline("avenue-chellah", "run1")
    d = C.SCENARIOS / "avenue-chellah"
    assert all((d / f).is_file() for f in C.FILES)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    assert meta["donnees"] == "simulees (SUMO)" and meta["tirage"]["statut"] == "tirage 1, indicatif"
    assert meta["validation"]["positions_sur_rues_fermees"] == 0
    assert meta["sumo_version"] == "1.28.0"
    geo = json.loads((d / "closed_edges.geojson").read_text(encoding="utf-8"))
    assert {f["properties"]["type"] for f in geo["features"]} <= {"rue", "transversale"}
    assert S.read_status("avenue-chellah")["state"] == "ready"
    assert [p.name for p in d.iterdir() if p.name.startswith(".")] == [], "ni verrou ni dossier de travail"


@needs_sumo
def test_cache_deuxieme_run_ne_recalcule_pas(env):
    S.run_pipeline("avenue-chellah", "run1")
    f = C.SCENARIOS / "avenue-chellah" / "kpi_rue_fermee.json"
    avant = f.stat().st_mtime_ns
    res = S.run_pipeline("avenue-chellah", "run2")
    assert res["state"] == S.SKIP_CACHE and f.stat().st_mtime_ns == avant


@needs_sumo
def test_force_recalcule(env):
    S.run_pipeline("avenue-chellah", "run1")
    S.run_pipeline("avenue-chellah", "run2", force=True)
    meta = json.loads((C.SCENARIOS / "avenue-chellah" / "meta.json").read_text(encoding="utf-8"))
    assert meta["dag_run_id"] == "run2"


# ----------------------------------------------------------------------- verrou, état, échec
def test_verrou_un_seul_calcul_par_rue(env):
    d = C.SCENARIOS / "avenue-chellah"
    d.mkdir(parents=True)
    assert S._acquire_lock(d, "A")
    assert S._acquire_lock(d, "A"), "reprise du même run (nouvelle tentative)"
    assert not S._acquire_lock(d, "B"), "un autre run attend"
    assert S.prepare("avenue-chellah", "B") == {"skip": S.SKIP_BUSY}
    S._release_lock(d, "B")
    assert (d / ".lock").exists(), "B ne libère pas le verrou de A"
    old = time.time() - C.LOCK_TTL_S - 60
    os.utime(d / ".lock", (old, old))
    assert S._acquire_lock(d, "B"), "verrou abandonné : repris"


def test_etat_manquant_puis_en_cours_puis_perime(env):
    assert S.read_status("avenue-chellah") == {"street_id": "avenue-chellah", "state": "missing"}
    d = C.SCENARIOS / "avenue-chellah"
    d.mkdir(parents=True)
    S._set_status("avenue-chellah", "A", "running", "simulate")
    assert S.read_status("avenue-chellah")["state"] == "running"
    st = json.loads((d / "status.json").read_text(encoding="utf-8"))
    st["updated_epoch"] = time.time() - C.LOCK_TTL_S - 60
    (d / "status.json").write_text(json.dumps(st), encoding="utf-8")
    assert S.read_status("avenue-chellah")["state"] == "failed"


def test_echec_note_l_etat_et_libere_le_verrou(env):
    idx = json.loads(C.STREET_INDEX.read_text(encoding="utf-8"))
    idx["streets"]["rue-cassee"] = {"name": "Rue cassée", "aliases": [], "type": "autre", "length_m": 500,
                                    "edges": ["nexiste-pas#1"]}
    C.STREET_INDEX.write_text(json.dumps(idx), encoding="utf-8")
    with pytest.raises(StreetError):
        S.run_pipeline("rue-cassee", "run1")
    st = S.read_status("rue-cassee")
    assert st["state"] == "failed" and "nexiste-pas#1" in st["error"]
    assert [p.name for p in (C.SCENARIOS / "rue-cassee").iterdir()] == ["status.json"]


@needs_sumo
def test_echec_apres_publication_garde_les_anciens_fichiers(env, monkeypatch):
    """Un recalcul forcé qui échoue ne casse pas le scénario déjà publié."""
    S.run_pipeline("avenue-chellah", "run1")
    monkeypatch.setattr(S, "simulate", lambda ctx: (_ for _ in ()).throw(RuntimeError("panne SUMO")))
    with pytest.raises(RuntimeError):
        S.run_pipeline("avenue-chellah", "run2", force=True)
    assert S.read_status("avenue-chellah")["state"] == "ready"
    assert json.loads((C.SCENARIOS / "avenue-chellah" / "meta.json").read_text(encoding="utf-8"))["dag_run_id"] == "run1"


# ----------------------------------------------------------------------------------- précalcul en lot
def test_classement_par_usage(env):
    rows = rank_streets_by_usage()
    assert rows and all(r[3] >= C.MIN_LENGTH_M for r in rows)
    assert [r[2] for r in rows] == sorted((r[2] for r in rows), reverse=True)
