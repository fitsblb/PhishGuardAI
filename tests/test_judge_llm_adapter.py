import json
import types
from pathlib import Path

from judge_svc.adapter import judge_url_llm
from judge_svc.contracts import FeatureDigest, JudgeRequest


class FakeResp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"response": self._text}


def test_judge_llm_parsing(monkeypatch):
    # Mock requests.post so no Ollama is required
    import judge_svc.adapter as adap

    monkeypatch.setattr(
        adap,
        "requests",
        types.SimpleNamespace(
            post=lambda *a, **k: FakeResp(
                "VERDICT: LEAN_PHISH\nSCORE: 0.82\nRATIONALE: suspicious tokens"
            )
        ),
    )
    req = JudgeRequest(
        url="http://ex.com/login",
        features=FeatureDigest(
            url_len=120,
            url_digit_ratio=0.22,
            url_subdomains=3,
        ),
    )
    out = judge_url_llm(req)
    assert out.verdict == "LEAN_PHISH"
    assert out.judge_score and 0.8 <= out.judge_score <= 0.82
    assert "suspicious" in out.rationale


def test_gateway_uses_backend_selector(monkeypatch, tmp_path: Path):
    # Temporary thresholds so gateway imports cleanly
    th = {
        "model": "x",
        "class_mapping": {"phish": 0, "legit": 1},
        "calibration": {"method": "i", "cv": 5},
        "thresholds": {
            "t_star": 0.45,
            "low": 0.30,
            "high": 0.60,
            "gray_zone_rate": 0.10,
        },
        "data": {"file": "x"},
        "seed": 42,
    }
    p = tmp_path / "thresholds.json"
    p.write_text(json.dumps(th), encoding="utf-8")
    monkeypatch.setenv("THRESHOLDS_JSON", str(p))

    # Force backend=llm and mock its call
    monkeypatch.setenv("JUDGE_BACKEND", "llm")
    import gateway.judge_wire as jw

    monkeypatch.setattr(
        jw,
        "_JUDGE_FN",
        lambda req: types.SimpleNamespace(
            verdict="LEAN_LEGIT",
            rationale="mock",
            judge_score=0.2,
            context={},
        ),
    )

    # Use the thresholds from the temp file
    TH = {
        "t_star": 0.45,
        "low": 0.30,
        "high": 0.60,
        "gray_zone_rate": 0.10,
    }
    res = jw.decide_with_judge("http://foo/login", 0.45, TH)

    # Wiring didn't crash; decision is mapped
    assert res.final_decision in {"ALLOW", "REVIEW", "BLOCK"}
