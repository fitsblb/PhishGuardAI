# Tests the threshold policy loader + decision function.

import json
from pathlib import Path

import pytest

from common.thresholds import decide, load_thresholds


@pytest.fixture()
def tmp_thresholds(tmp_path: Path):
    # symmetric band around t* for demo (~10% gray-zone in your notebook)
    payload = {
        "model": "xgb",
        "class_mapping": {"phish": 0, "legit": 1},
        "calibration": {"method": "isotonic", "cv": 5},
        "thresholds": {
            "t_star": 0.45,
            "low": 0.30,
            "high": 0.60,
            "gray_zone_rate": 0.10,
        },
        "data": {"file": "data/processed/phiusiil_clean_urlfeats.csv"},
        "seed": 42,
    }
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return f


def test_load_thresholds(tmp_thresholds: Path):
    th = load_thresholds(tmp_thresholds)
    # nosec
    assert set(th.keys()) == {"t_star", "low", "high", "gray_zone_rate"}
    assert 0.0 <= th["low"] < th["high"] <= 1.0  # nosec


@pytest.mark.parametrize(
    "p,expected",
    [
        (0.00, "ALLOW"),  # far below low
        (0.29, "ALLOW"),  # just below low
        (0.30, "REVIEW"),  # exactly low → REVIEW by our policy
        (0.45, "REVIEW"),  # center of band
        (0.59, "REVIEW"),  # just below high
        (0.60, "BLOCK"),  # exactly high → BLOCK
        (1.00, "BLOCK"),  # far above high
    ],
)
def test_decision_boundaries(tmp_thresholds: Path, p: float, expected: str):
    th = load_thresholds(tmp_thresholds)
    assert decide(p, th) == expected  # nosec
