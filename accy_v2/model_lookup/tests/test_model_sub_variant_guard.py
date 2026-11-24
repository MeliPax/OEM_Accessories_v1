"""Sub-variant guard: a bare model search ("gv80") must not return a sub-variant
model line ("GV80 Coupe") unless the sub-variant word ("coupe") was searched.

Uses a small sample CSV (not the live vehicle DB) and the real Genesis configs.
Run: python -m pytest accy_v2/model_lookup/tests/test_model_sub_variant_guard.py
"""

import copy
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ACCY_V2 = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ACCY_V2.parent), str(ACCY_V2)]

from model_lookup.models.manufacture_module import search_models_by_description  # noqa: E402

CONFIGS_DIR = str(ACCY_V2 / "model_lookup" / "configs")
COLUMNS = ["Description", "Drivetrain", "Manufacturer", "ModelName", "ModelNumber",
           "ModelYear", "Package", "PassDoors", "TrimName", "engine_type"]
ROWS = [
    ("3.5t Prestige Awd 7-Passenger", "V8CW7K3BGP00", "GV80", "3.5T Prestige", "1001"),
    ("3.5t Prestige Awd 7-Passenger Black-Package", "V8CW7K3BGPBL", "GV80", "3.5T Prestige Black", "1002"),
    ("3.5t Awd", "V8CW7K3BXX00", "GV80", "3.5T", "1003"),
    ("3.5t Electric Awd", "V8CC7K3BGP00", "GV80 Coupe", "3.5T e-SC", "1004"),
    ("3.5t Electric Prestige Black-Package Awd", "V8CC7K3BGPBL", "GV80 Coupe", "3.5T e-SC Prestige Black", "1005"),
]


@pytest.fixture(scope="module")
def csv_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "vehicles.csv"
    pd.DataFrame(
        [(d, "ALL_WHEEL_DRIVE", "GENESIS", m, n, "2026", p, "4", t, "3.5t") for d, n, m, t, p in ROWS],
        columns=COLUMNS,
    ).to_csv(path, index=False)
    return str(path)


@pytest.fixture(scope="module")
def genesis_rules():
    cfg = yaml.safe_load(open(ACCY_V2 / "oems/genesis/config/enrichment.yaml", encoding="utf-8"))
    rules = cfg["model_lookup"]["brands"]["Genesis"]
    assert rules["model_sub_variant_tokens"] == ["coupe"]
    return rules


def _search(keywords, csv_path, rules):
    df = search_models_by_description("Genesis", 2026, list(keywords), csv_path=csv_path,
                                      configs_dir=CONFIGS_DIR, oem_config=copy.deepcopy(rules))
    return sorted(df["ModelNumber"]) if len(df) else []


def test_trim_search_excludes_coupe(csv_path, genesis_rules):
    """The fixed case: a trim word ("prestige") used to switch the guard off."""
    assert _search(["gv80", "3.5t", "prestige"], csv_path, genesis_rules) == ["V8CW7K3BGP00", "V8CW7K3BGPBL"]
    assert _search(["gv80", "3.5t", "prestige", "black-package"], csv_path, genesis_rules) == ["V8CW7K3BGPBL"]


def test_coupe_search_returns_coupe(csv_path, genesis_rules):
    assert _search(["gv80", "coupe", "3.5t", "prestige", "black-package"], csv_path, genesis_rules) == ["V8CC7K3BGPBL"]


def test_no_trim_word_trim_check_still_applies(csv_path, genesis_rules):
    """Without a trim word: Prestige rows dropped by the trim check (unchanged), Coupe by the guard."""
    assert _search(["gv80", "3.5t"], csv_path, genesis_rules) == ["V8CW7K3BXX00"]


def test_without_sub_variant_config_behaviour_unchanged(csv_path, genesis_rules):
    """OEMs with no model_sub_variant_tokens keep the old result (Coupe not filtered)."""
    rules = {k: v for k, v in genesis_rules.items() if k != "model_sub_variant_tokens"}
    assert _search(["gv80", "3.5t", "prestige"], csv_path, rules) == ["V8CC7K3BGPBL", "V8CW7K3BGP00", "V8CW7K3BGPBL"]


def test_nothing_matches_returns_empty(csv_path, genesis_rules):
    assert _search(["gv80", "3.5t", "sport"], csv_path, genesis_rules) == []
