# tests/test_gateway_e2e.py  (BRANCH: feature/e2e-gateway-tests)
import os

from fastapi.testclient import TestClient

# Bind known config BEFORE importing the app
os.environ.setdefault("THRESHOLDS_JSON", "configs/dev/thresholds.json")
# Use stub judge for deterministic, fast tests
os.environ.setdefault("JUDGE_BACKEND", "stub")

from gateway.main import app  # noqa: E402

client = TestClient(app)


def test_health_and_config():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("service") == "gateway"

    r = client.get("/config")
    assert r.status_code == 200
    th = r.json()["thresholds"]
    for k in ("low", "high", "t_star", "gray_zone_rate"):
        assert k in th
    assert 0.0 <= th["low"] < th["high"] <= 1.0


def _predict(url: str, p: float):
    r = client.post("/predict", json={"url": url, "p_malicious": p})
    assert r.status_code == 200
    return r.json()


def test_allow_review_block_paths():
    # Below low => ALLOW (no judge)
    j1 = _predict("http://example.com/", 0.05)
    assert j1["decision"] == "ALLOW"
    assert j1["reason"] == "policy-band"
    assert j1["judge"] is None

    # Inside band => REVIEW path (judge runs; reason starts with 'judge-')
    j2 = _predict("http://ex.com/login?acct=12345", 0.45)
    assert j2["reason"].startswith("judge-")
    assert j2["decision"] in {"ALLOW", "REVIEW", "BLOCK"}
    # mapping depends on stub rules
    assert j2["judge"] is not None  # judge invoked

    # At/above high => BLOCK (no judge)
    j3 = _predict("http://example.com/?id=999", 0.95)
    assert j3["decision"] == "BLOCK"
    assert j3["reason"] == "policy-band"
    assert j3["judge"] is None
