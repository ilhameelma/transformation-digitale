"""Fixtures : un dossier data/ temporaire (index des rues, références) et la bibliothèque jumeau importable.

Les tests utilisent le vrai SUMO (celui du PATH). Sans SUMO, les tests de simulation sont ignorés.
"""
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "airflow" / "include"))
sys.path.insert(0, str(REPO / "airflow" / "tools"))

from jumeau import config as C  # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("sumo") is None or shutil.which("duarouter") is None,
                                reason="SUMO absent du PATH")


@pytest.fixture(scope="session")
def street_index_file(tmp_path_factory):
    """street_index.json généré une fois pour toute la session, depuis le réseau du dépôt."""
    import json
    import build_street_index
    index, _, _ = build_street_index.build(REPO / "sim" / "hassan.net.xml", REPO / "data" / "network_edges.geojson")
    f = tmp_path_factory.mktemp("index") / "street_index.json"
    f.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return f


@pytest.fixture
def env(tmp_path, monkeypatch, street_index_file):
    """Dossier data/ temporaire : index, situation actuelle de référence, sorties vides."""
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(street_index_file, data / "street_index.json")
    for name in ("tripinfo_actuel_ref.xml", "kpi_actuel_ref.json"):
        shutil.copy(REPO / "data" / name, data / name)
    for attr, value in {"DATA": data, "SIM": REPO / "sim", "TRAFFIC": REPO / "traffic",
                        "NET_REF": REPO / "sim" / "hassan.net.xml", "ROU_REF": REPO / "sim" / "hassan.rou.xml",
                        "STREET_INDEX": data / "street_index.json", "REF_TRIPINFO": data / "tripinfo_actuel_ref.xml",
                        "REF_KPI": data / "kpi_actuel_ref.json", "SCENARIOS": data / "scenarios"}.items():
        monkeypatch.setattr(C, attr, value)
    return data
