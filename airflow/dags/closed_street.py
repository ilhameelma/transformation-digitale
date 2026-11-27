"""DAG closed_street : simule la fermeture d'une rue (SUMO) et publie les fichiers pour la vue 3D.

Déclenché à la demande, avec le paramètre street_id (clé de data/street_index.json) :

    POST /api/v1/dags/closed_street/dagRuns   {"conf": {"street_id": "avenue-allal-ben-abdellah"}}

prepare   -> contrôle du street_id (liste blanche), cache, verrou, réseau fermé, demande re-routée
simulate  -> SUMO, graine fixe, mêmes réglages que la situation actuelle de référence
export    -> trajectoires, indicateurs, tracé de la rue fermée, contrôles de validité
publish   -> copie dans data/scenarios/<street_id>/ (meta.json en dernier)

Si le scénario existe déjà (cache), prepare s'arrête et les tâches suivantes sont ignorées : aucun recalcul.
La situation actuelle n'est jamais recalculée. Données simulées (SUMO).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Hors Docker (airflow dags test), le dossier include/ n'est pas dans le PYTHONPATH : on l'ajoute.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException, AirflowSkipException
from airflow.models.param import Param

from jumeau import scenario
from jumeau.config import STREET_ID_RE
from jumeau.street_index import StreetError


def street_from_context(context):
    """street_id du run, que la tâche vienne des paramètres ou de la conf du run."""
    sid = (context.get("params") or {}).get("street_id")
    if not sid and context.get("dag_run") is not None:
        sid = (context["dag_run"].conf or {}).get("street_id")
    return sid


def on_failure(context):
    """Dernier échec d'une tâche (ou du run) : état « failed » dans status.json, verrou libéré."""
    scenario.mark_failed(street_from_context(context), context.get("run_id", "run"), context.get("exception") or "échec")


@dag(
    dag_id="closed_street",
    schedule=None,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=4,                      # plusieurs rues à la fois ; un verrou par rue évite les doublons
    dagrun_timeout=timedelta(minutes=10),
    params={
        "street_id": Param(type="string", pattern=STREET_ID_RE.pattern,
                           description="Clé de la rue dans data/street_index.json (liste blanche)"),
        "force": Param(False, type="boolean", description="Recalculer même si le scénario existe déjà"),
    },
    default_args={"retries": 1, "retry_delay": timedelta(seconds=5), "execution_timeout": timedelta(minutes=5),
                  "on_failure_callback": on_failure},
    on_failure_callback=on_failure,
    tags=["jumeau-numerique", "sumo"],
    doc_md=__doc__,
)
def closed_street():
    @task
    def prepare(**context):
        p = context["params"]
        try:
            ctx = scenario.prepare(p["street_id"], context["run_id"], force=p["force"])
        except StreetError as exc:
            raise AirflowFailException(str(exc))        # rue inconnue : inutile de réessayer
        if ctx.get("skip") == scenario.SKIP_CACHE:
            raise AirflowSkipException("scénario déjà calculé (cache) : rien à faire")
        if ctx.get("skip"):
            raise AirflowSkipException("un autre run calcule déjà cette rue")
        return ctx

    @task
    def simulate(ctx):
        return scenario.simulate(ctx)

    @task
    def export(ctx):
        return scenario.export(ctx)

    @task
    def publish(ctx):
        return scenario.publish(ctx)

    publish(export(simulate(prepare())))


closed_street()
