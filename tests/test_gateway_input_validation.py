import os

from fastapi.testclient import TestClient


def make_client(max_bytes: int = 8192):
    os.environ["MAX_REQ_BYTES"] = str(max_bytes)
    os.environ.setdefault("THRESHOLDS_JSON", "configs/dev/thresholds.json")
    from importlib import reload

    import gateway.main as gw

    reload(gw)  # re-import to apply env changes
    return TestClient(gw.app)


def test_url_too_long_422():
    client = make_client()
    long_url = "http://ex.com/" + ("a" * 3000)  # > 2048
    r = client.post("/predict", json={"url": long_url, "p_malicious": 0.5})
    assert r.status_code == 422


def test_request_too_large_413():
    client = make_client(max_bytes=50)  # tiny cap so normal payload trips it
    payload = {"url": "http://ex.com/login?acct=1", "p_malicious": 0.45}
    r = client.post("/predict", json=payload)
    assert r.status_code == 413
    assert r.json()["detail"].lower().startswith("request body too large")


def test_cors_preflight_allows_localhost():
    client = make_client()
    # Starlette's TestClient will handle OPTIONS; we validate the CORS header echo
    r = client.options(
        "/predict",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "http://localhost"
