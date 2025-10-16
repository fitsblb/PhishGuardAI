"""
Tests for the model service.
"""

from fastapi.testclient import TestClient

from model_svc.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test the health endpoint returns correct status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "model-svc"
    # Accept current version format
    assert data["version"] in ["0.1.0", "0.2.0-debug"]


def test_predict_endpoint_basic():
    """Test predict endpoint with basic URL."""
    response = client.post("/predict", json={"url": "http://example.com"})
    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "p_malicious" in data
    assert "source" in data

    # Check data types and ranges
    assert isinstance(data["p_malicious"], float)
    assert 0.0 <= data["p_malicious"] <= 1.0
    assert data["source"] in ["model", "heuristic"]


def test_predict_endpoint_suspicious_url():
    """Test predict endpoint with suspicious URL characteristics."""
    response = client.post(
        "/predict",
        json={"url": "http://ex.com/login?acct=12345"},
    )
    assert response.status_code == 200
    data = response.json()

    # Should return higher probability for suspicious URL
    assert data["p_malicious"] > 0.0
    assert data["source"] in ["model", "heuristic"]


def test_predict_endpoint_complex_url():
    """Test predict endpoint with complex suspicious URL."""
    suspicious_url = (
        "http://secure-banking-login.suspicious-domain.com"
        "/account/verify?acct=123456&token=abc123"
    )
    response = client.post("/predict", json={"url": suspicious_url})
    assert response.status_code == 200
    data = response.json()

    # Complex suspicious URL should have higher score
    assert data["p_malicious"] > 0.3
    assert data["source"] in ["model", "heuristic"]


def test_predict_endpoint_invalid_input():
    """Test predict endpoint with invalid input."""
    response = client.post("/predict", json={"invalid": "data"})
    assert response.status_code == 422  # Validation error


def test_predict_endpoint_empty_url():
    """Test predict endpoint with empty URL."""
    response = client.post("/predict", json={"url": ""})
    # Empty URLs should be rejected with validation error
    assert response.status_code == 422


def test_predict_endpoint_various_urls():
    """Test predict endpoint with various URL patterns."""
    test_urls = [
        "http://google.com",
        "https://github.com/user/repo",
        "http://login-paypal.fake-domain.com",
        "https://amazon.com/signin?redirect=account",
    ]

    for url in test_urls:
        response = client.post("/predict", json={"url": url})
        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["p_malicious"] <= 1.0
        # Accept whitelist as valid source (some domains are whitelisted)
        assert data["source"] in ["model", "heuristic", "whitelist"]


def test_heuristic_scoring_consistency():
    """Test that heuristic scoring is consistent for same URL."""
    url = "http://test.com/login?acct=123"

    # Make multiple requests
    responses = []
    for _ in range(3):
        response = client.post("/predict", json={"url": url})
        assert response.status_code == 200
        responses.append(response.json())

    # All responses should be identical (deterministic)
    for i in range(1, len(responses)):
        assert responses[i]["p_malicious"] == responses[0]["p_malicious"]
        assert responses[i]["source"] == responses[0]["source"]
