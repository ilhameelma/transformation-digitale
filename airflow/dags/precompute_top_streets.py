"""DAG precompute_top_streets : précalcule, en lot, les N rues les plus utilisées.

Lancé une fois (ou relancé : les rues déjà prêtes sont sautées). Les rues sont classées par nombre de voitures
de la demande de référence qui les empruntent. Chaque rue est une tâche dynamique (dynamic task mapping),
2 au plus en parallèle. Mêmes étapes et mêmes fichiers que le DAG closed_street (même bibliothèque).

Paramètres : n (nombre de rues, 5 par défaut), force (recalculer aussi les rues déjà prêtes).
Données simulées (SUMO).
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))

from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException
from airflow.models.param import Param
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule

from jumeau import config, scenario
from jumeau.usage import rank_streets_by_usage


@dag(
    dag_id="precompute_top_streets",
    schedule=None,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=1),
    params={
        "n": Param(5, type="integer", minimum=1, maximum=50, description="Nombre de rues à précalculer"),
        "force": Param(False, type="boolean", description="Recalculer aussi les rues déjà prêtes"),
    },
    tags=["jumeau-numerique", "sumo"],
    doc_md=__doc__,
)
def precompute_top_streets():
    @task
    def select_streets(**context):
        """Les N rues les plus utilisées qui ne sont pas encore prêtes (ou toutes, avec force)."""
        n, force = context["params"]["n"], context["params"]["force"]
        ranking = rank_streets_by_usage()
        for sid, nom, voitures, longueur in ranking[:n + 10]:
            print(f"{sid:40} {voitures:4} voitures  {longueur:8.1f} m  prête={scenario.is_ready(sid)}")
        chosen = [sid for sid, *_ in ranking if force or not scenario.is_ready(sid)][:n]
        if not chosen:
            raise AirflowSkipException("les rues demandées sont déjà prêtes")
        print("à calculer :", chosen)
        return chosen

    @task(max_active_tis_per_dag=2, retries=1, retry_delay=timedelta(seconds=5),
          execution_timeout=timedelta(minutes=10), map_index_template="{{ street_id }}")
    def run_street(street_id, **context):
        get_current_context()["street_id"] = street_id          # nom de l'instance dans l'interface
        res = scenario.run_pipeline(street_id, context["run_id"], force=context["params"]["force"])
        print(res)
        return res

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def report(results, **context):
        """Trace du lot : une ligne par rue, écrite à côté des scénarios."""
        rows = [r for r in (results or []) if r]
        out = config.SCENARIOS / "precompute_report.json"
        config.SCENARIOS.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"dag_run_id": context["run_id"], "rues": rows}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"{len(rows)} rues traitées -> {out}")

    report(run_street.expand(street_id=select_streets()))


precompute_top_streets()
