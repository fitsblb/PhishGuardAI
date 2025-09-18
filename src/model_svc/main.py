"""
Minimal FastAPI model service.
Returns p_malicious from saved model artifact if present,
otherwise transparent URL heuristics.
"""

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PhishGuard Model Service", version="0.1.0")

# BRANCH: feature/model-artifact-freeze
# --- Model artifact paths ---
MODEL_ARTIFACT_PATH = Path(os.getenv("MODEL_PATH", "models/dev/model.pkl"))
MODEL_META_PATH = Path(os.getenv("MODEL_META_PATH", "models/dev/model_meta.json"))
_model, _meta = None, {}

try:
    if MODEL_ARTIFACT_PATH.exists():
        import joblib

        _model = joblib.load(MODEL_ARTIFACT_PATH)
        logger.info(f"Loaded model from {MODEL_ARTIFACT_PATH}")
    if MODEL_META_PATH.exists():
        import json

        _meta = json.loads(MODEL_META_PATH.read_text(encoding="utf-8"))
        logger.info(f"Loaded metadata from {MODEL_META_PATH}")
except Exception as e:
    logger.warning(f"Failed to load model or metadata: {e}")
    _model, _meta = None, {}

_feature_order = _meta.get("feature_order") or []  # list[str]
_phish_col_ix = int(_meta.get("phish_proba_col_index", 0))


class PredictRequest(BaseModel):
    url: str = Field(..., description="URL to analyze for phishing probability")


class PredictResponse(BaseModel):
    p_malicious: float = Field(
        ..., description="Probability that URL is malicious (0.0-1.0)"
    )
    source: str = Field(..., description="Source of prediction: 'model' or 'heuristic'")


def load_model() -> Any:
    """Load the model from file if available."""
    # Model is already loaded globally at startup
    return _model


def engineer_features(url: str) -> pd.DataFrame:
    """
    Extract URL features for model prediction.
    Returns DataFrame with features in metadata order.
    """
    import tldextract

    parsed = urlparse(url)
    extracted = tldextract.extract(url)

    # Base features (matching training)
    features = {
        "UrlLength": len(url),
        "DomainLength": len(parsed.netloc),
        "IpAddress": int(
            all(
                part.isdigit() and 0 <= int(part) <= 255
                for part in parsed.netloc.split(".")
            )
            if "." in parsed.netloc and not extracted.domain
            else False
        ),
        "TinyUrl": int(any(t in parsed.netloc for t in ["bit.ly", "tinyurl", "t.co"])),
        "Prefix/Suffix": int("-" in extracted.domain) if extracted.domain else 0,
        "DNS_Record": 1,  # Assume valid for live URLs
        "Web_Traffic": 1,  # Assume has traffic for live URLs
        "Domain_Age": 1,  # Assume established for live URLs
        "Domain_End": 1,  # Assume not expiring soon for live URLs
        "iFrame": 0,  # Can't detect from URL alone
        "Mouse_Over": 0,  # Can't detect from URL alone
        "Right_Click": 0,  # Can't detect from URL alone
        "Web_Forwards": 0,  # Can't detect from URL alone
    }

    # Create DataFrame with single row
    df = pd.DataFrame([features])

    # Reorder columns to match training metadata
    if _feature_order:
        missing_cols = set(_feature_order) - set(df.columns)
        if missing_cols:
            logger.warning(f"Missing features: {missing_cols}")
            for col in missing_cols:
                df[col] = 0  # Default missing features to 0
        df = df.reindex(columns=_feature_order, fill_value=0)

    return df


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
    has_model = _model is not None
    return {
        "status": "ok",
        "service": "model-svc",
        "version": "0.1.0",
        "has_model": has_model,
    }


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
                # Extract features and predict
                features_df = engineer_features(request.url)
                probas = model.predict_proba(features_df)

                # Get phishing probability from correct column
                p_malicious = float(probas[0][_phish_col_ix])

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
