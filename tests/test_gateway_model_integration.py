"""
Tests for gateway model service integration.
"""

import os
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from gateway.main import _call_model_service, app

client = TestClient(app)


class TestModelServiceIntegration:
    """Test gateway integration with model service."""

    @patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"})
    @patch("gateway.main.requests.post")
    def test_call_model_service_success(self, mock_post):
        """Test successful call to model service."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "p_malicious": 0.75,
            "source": "heuristic",
        }
        mock_post.return_value = mock_response

        result = _call_model_service("http://example.com", {})

        assert result == 0.75
        mock_post.assert_called_once_with(
            "http://localhost:9000/predict",
            json={"url": "http://example.com"},
            timeout=3.0,
        )

    def test_call_model_service_no_url_configured(self):
        """Test when MODEL_SVC_URL is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = _call_model_service("http://example.com", {})
            assert result is None

    def test_call_model_service_request_failure(self):
        """Test when model service request fails."""
        with patch("gateway.main.requests.post") as mock_post:
            # Mock request failure
            mock_post.side_effect = Exception("Connection error")

            with patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"}):
                result = _call_model_service("http://example.com", {})

            assert result is None

    def test_call_model_service_invalid_response(self):
        """Test when model service returns invalid probability."""
        with patch("gateway.main.requests.post") as mock_post:
            # Mock response with invalid probability
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"p_malicious": 1.5}  # Invalid: > 1.0
            mock_post.return_value = mock_response

            with patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"}):
                result = _call_model_service("http://example.com", {})

            assert result is None

    def test_predict_with_p_malicious_provided(self):
        """Test /predict when p_malicious is provided by caller."""
        response = client.post(
            "/predict",
            json={"url": "http://suspicious-domain.test", "p_malicious": 0.8},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["p_malicious"] == 0.8
        assert data["source"] == "model"  # Should be "model" when provided

    @patch("gateway.main._call_model_service")
    def test_predict_model_service_success(self, mock_call_model):
        """Test /predict when model service returns valid probability."""
        # Mock model service returning probability
        mock_call_model.return_value = 0.65

        with patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"}):
            response = client.post(
                "/predict", json={"url": "http://suspicious-phishing-site.com"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["p_malicious"] == 0.65
        assert data["source"] == "model"
        assert data["url"] == "http://suspicious-phishing-site.com"

        # Verify model service was called
        mock_call_model.assert_called_once_with(
            "http://suspicious-phishing-site.com", {}
        )

    @patch("gateway.main._call_model_service")
    def test_predict_fallback_to_heuristic(self, mock_call_model):
        """Test /predict falls back to heuristic when model service fails."""
        # Mock model service returning None (failure)
        mock_call_model.return_value = None

        with patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"}):
            response = client.post(
                "/predict", json={"url": "http://test-fallback.example"}
            )

        assert response.status_code == 200
        data = response.json()
        # Should fall back to heuristic when model service fails
        assert data["source"] == "heuristic"
        # Valid probability from heuristic
        assert 0.0 <= data["p_malicious"] <= 1.0

        # Verify model service was attempted
        mock_call_model.assert_called_once_with("http://test-fallback.example", {})

    def test_predict_no_model_service_url(self):
        """Test /predict when MODEL_SVC_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            response = client.post("/predict", json={"url": "http://example.com"})

        assert response.status_code == 200
        data = response.json()
        # Should fall back to heuristic or whitelist
        assert data["source"] in ["heuristic", "whitelist"]
        assert 0.0 <= data["p_malicious"] <= 1.0

    @patch("gateway.main._call_model_service")
    def test_predict_with_extras(self, mock_call_model):
        """Test /predict passes extras correctly."""
        mock_call_model.return_value = 0.45

        extras_data = {
            "TLDLegitimateProb": 0.8,
            "NoOfOtherSpecialCharsInURL": 3,
        }

        with patch.dict(os.environ, {"MODEL_SVC_URL": "http://localhost:9000"}):
            response = client.post(
                "/predict",
                json={"url": "http://test.com", "extras": extras_data},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "model"

        # Verify model service was called - expect all ExtrasIn fields (incl. None)
        expected_extras = {
            "TLDLegitimateProb": 0.8,
            "NoOfOtherSpecialCharsInURL": 3,
            "SpacialCharRatioInURL": None,
            "CharContinuationRate": None,
            "URLCharProb": None,
        }
        mock_call_model.assert_called_once_with("http://test.com", expected_extras)

    def test_predict_priority_order(self):
        """Test that p_malicious priority is: caller > model service > heuristic."""
        # Test 1: Caller provided p_malicious (highest priority)
        with patch("gateway.main._call_model_service") as mock_call_model:
            mock_call_model.return_value = 0.99  # This should be ignored

            response = client.post(
                "/predict",
                json={
                    "url": "http://test-priority.example",  # Use non-whitelisted domain
                    "p_malicious": 0.2,  # Caller's value should win
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["p_malicious"] == 0.2
        assert data["source"] == "model"
        # Model service should not be called when p_malicious is provided
        mock_call_model.assert_not_called()
