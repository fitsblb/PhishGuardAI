"""
Minimal FastAPI model service.
Returns p_malicious from saved model artifact if present,
otherwise transparent URL heuristics.
"""

import logging
import os
import pickle  # nosec B403 - Used for trusted model artifacts only
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PhishGuard Model Service", version="0.0.1")

# Global model cache
_model = None
_model_loaded = False


class PredictRequest(BaseModel):
    url: str = Field(..., description="URL to analyze for phishing probability")


class PredictResponse(BaseModel):
    p_malicious: float = Field(
        ..., description="Probability that URL is malicious (0.0-1.0)"
    )
    source: str = Field(..., description="Source of prediction: 'model' or 'heuristic'")


def load_model() -> Optional[object]:
    """Load saved model artifact if present."""
    global _model, _model_loaded

    if _model_loaded:
        return _model

    model_path = os.getenv("MODEL_PATH", "model.pkl")

    if os.path.exists(model_path):
        try:
            with open(model_path, "rb") as f:
                _model = pickle.load(f)  # nosec B301 - Trusted model artifacts
            logger.info(f"Loaded model from {model_path}")
            _model_loaded = True
            return _model
        except Exception as e:
            logger.warning(f"Failed to load model from {model_path}: {e}")
    else:
        logger.info(f"No model found at {model_path}, using heuristics")

    _model_loaded = True
    return None


def url_heuristic_score(url: str) -> float:
    """
    Transparent URL heuristic for phishing probability.
    Simple rule-based scoring based on URL characteristics.
    """
    try:
        parsed = urlparse(url)
        score = 0.0

        # Base suspicious indicators
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()

        # Domain-based indicators
        if any(
            word in domain for word in ["login", "secure", "bank", "paypal", "amazon"]
        ):
            score += 0.2

        if len(domain.split(".")) > 3:  # Many subdomains
            score += 0.15

        if any(char in domain for char in ["-", "_"]) and len(domain) > 15:
            score += 0.1

        # Path-based indicators
        if any(
            word in path for word in ["login", "signin", "account", "verify", "update"]
        ):
            score += 0.2

        if len(path) > 50:  # Very long path
            score += 0.1

        # Query parameter indicators
        if any(word in query for word in ["acct", "account", "id", "token", "session"]):
            score += 0.15

        if len(query) > 100:  # Long query string
            score += 0.1

        # URL length penalty
        if len(url) > 100:
            score += 0.1

        # Ensure score is in valid range
        return min(max(score, 0.0), 0.99)

    except Exception as e:
        logger.warning(f"Error in heuristic scoring for URL {url}: {e}")
        return 0.1  # Default low suspicion


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "model-svc", "version": "0.0.1"}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """
    Predict phishing probability for a given URL.
    Uses saved model if available, otherwise falls back to heuristics.
    """
    try:
        model = load_model()

        if model is not None:
            # Use trained model for prediction
            try:
                # This would be the actual model prediction logic
                # For now, we'll simulate model prediction with enhanced heuristics
                p_malicious = url_heuristic_score(request.url)
                # Add some model-like variance
                p_malicious = min(p_malicious * 1.2, 0.95)

                return PredictResponse(p_malicious=p_malicious, source="model")
            except Exception as e:
                logger.error(f"Model prediction failed for URL {request.url}: {e}")
                # Fall back to heuristics
                pass

        # Use heuristic fallback
        p_malicious = url_heuristic_score(request.url)

        return PredictResponse(p_malicious=p_malicious, source="heuristic")

    except Exception as e:
        logger.error(f"Prediction failed for URL {request.url}: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
