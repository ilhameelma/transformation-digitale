"""get_scenario et get_kpi : lecture de fichiers, sans LLM."""
import json
import re
import time
from pathlib import Path
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
AIRFLOW_URL = os.getenv("AIRFLOW_URL", "http://localhost:8080")
DATA = Path("data")
INDEX = DATA / "street_index.json"
SCEN = DATA / "scenarios"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PERIME_S = 1800  # un "running" plus vieux que ça = échec (à aligner avec C.LOCK_TTL_S)


def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _rue_valide(street_id: str) -> bool:
    """Liste blanche : slug correct ET présent dans l'index."""
    return bool(SLUG.match(street_id or "")) and street_id in _json(INDEX)["streets"]


def get_scenario(street_id: str) -> dict:
    if not _rue_valide(street_id):
        return {"statut": "rue_inconnue", "street_id": street_id}
    dossier = SCEN / street_id
    if (dossier / "meta.json").exists():
        return {"statut": "ready", "street_id": street_id}
    f = dossier / "status.json"
    if f.exists():
        st = _json(f)
        if st.get("state") == "running":
            if time.time() - st.get("updated_epoch", 0) > PERIME_S:
                return {"statut": "failed", "street_id": street_id,
                        "erreur": "calcul interrompu (état périmé)"}
            return {"statut": "running", "street_id": street_id,
                    "etape": st.get("step")}
        if st.get("state") == "failed":
            return {"statut": "failed", "street_id": street_id,
                    "erreur": st.get("error")}
    return {"statut": "missing", "street_id": street_id}


EXCLUS = {"actuel", "actuel_old"}   # ne correspondent à aucune simulation du dossier
AVERTISSEMENTS = {
    "pic": "Référence absente (kpi_actuel_500.json pas encore simulé) : aucune comparaison possible.",
}


def get_kpi(street_id: str = None, scenario: str = None) -> dict:
    # cas 1 : rue fermée à la demande
    if street_id:
        if get_scenario(street_id)["statut"] != "ready":
            return {"statut": "non_pret", "street_id": street_id}
        dossier = SCEN / street_id
        kpi = _json(dossier / "kpi_rue_fermee.json")
        kpi.pop("congestion_par_rue", None)   # trop long pour le LLM
        meta = _json(dossier / "meta.json")

        impact = dict(meta.get("impact") or {})
        impact.pop("ids_concernees", None)    # inutile pour le LLM

        val = dict(meta.get("validation") or {})
        a, b = val.get("trajets_termines"), val.get("trajets_termines_actuel")
        if a and b:
            ecart = round(100 * abs(a - b) / b, 1)
            val["ecart_trajets_termines_pct"] = ecart
            val["comparaison_reseau_fiable"] = ecart <= 2

        return {"statut": "ok", "source": f"data/scenarios/{street_id}/",
                "kpi": kpi, "impact": impact, "validation": val,
                "tirage": meta.get("tirage")}
    # cas 2 : scénario global (actuel_ref, pic, ...)
    if scenario:
        dispo = {p.stem[4:] for p in DATA.glob("kpi_*.json")} - EXCLUS
        if scenario not in dispo:
            return {"statut": "inconnu", "scenarios_disponibles": sorted(dispo)}
        kpi = _json(DATA / f"kpi_{scenario}.json")
        kpi.pop("congestion_par_rue", None)
        res = {"statut": "ok", "source": f"data/kpi_{scenario}.json", "kpi": kpi}
        if scenario in AVERTISSEMENTS:
            res["avertissement"] = AVERTISSEMENTS[scenario]
        return res
    return {"statut": "erreur", "message": "Donner street_id ou scenario."}
def trigger_simulation(street_id: str) -> dict:
    """Déclenche le DAG closed_street. Jamais de force=True depuis le chatbot."""
    if not _rue_valide(street_id):                       # liste blanche
        return {"statut": "rue_inconnue", "street_id": street_id}

    etat = get_scenario(street_id)["statut"]
    if etat == "ready":
        return {"statut": "deja_pret", "street_id": street_id}
    if etat == "running":
        return {"statut": "deja_en_cours", "street_id": street_id}

    user = os.getenv("AIRFLOW_ADMIN_USER")
    pwd = os.getenv("AIRFLOW_ADMIN_PASSWORD")
    if not user or not pwd:
        return {"statut": "erreur", "message": "Identifiants Airflow absents du .env."}

    try:
        r = httpx.post(
            f"{AIRFLOW_URL}/api/v1/dags/closed_street/dagRuns",
            json={"conf": {"street_id": street_id, "force": False}},
            auth=(user, pwd),
            timeout=10,
        )
    except httpx.HTTPError:
        return {"statut": "airflow_indisponible"}

    if r.status_code == 200:
        return {"statut": "lance", "street_id": street_id,
                "dag_run_id": r.json().get("dag_run_id")}
    return {"statut": "erreur", "http": r.status_code, "detail": r.text[:200]}