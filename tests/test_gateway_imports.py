# Ensures we can import the gateway app and judge wiring
# without relying on the repo's thresholds.json.

import importlib
import json
from pathlib import Path


def test_gateway_imports_with_temp_thresholds(monkeypatch, tmp_path: Path):
    # Create a minimal thresholds file in a temp dir
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
    th_path = tmp_path / "thresholds.json"
    th_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("THRESHOLDS_JSON", str(th_path))

    # Import after setting env so gateway loads cleanly
    gw_main = importlib.import_module("gateway.main")
    assert gw_main.app.title == "PhishGuard Gateway"

    # Judge wiring is importable and callable
    jw = importlib.import_module("gateway.judge_wire")
    TH = gw_main.TH
    outcome = jw.decide_with_judge("https://example.com", p_malicious=0.05, th=TH)
    assert outcome.final_decision in {"ALLOW", "REVIEW", "BLOCK"}
