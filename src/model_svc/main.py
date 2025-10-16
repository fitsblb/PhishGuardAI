"""
PhishGuard Model Service - DEBUG VERSION
Extensive logging to diagnose prediction issues.

TEMPORARY: This version has extra logging. Remove before production.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import pandas as pd
import shap
import yaml  # type: ignore
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import shared feature extraction
from common.feature_extraction import (
    extract_features,
    validate_features,
)

# === Known Legitimate Domain Whitelist ===
# Handles out-of-distribution major tech companies not in PhiUSIIL training data
KNOWN_LEGITIMATE_DOMAINS = {
    "google.com",
    "www.google.com",
    "github.com",
    "www.github.com",
    "microsoft.com",
    "www.microsoft.com",
    "amazon.com",
    "www.amazon.com",
    "apple.com",
    "www.apple.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "www.twitter.com",
    "linkedin.com",
    "www.linkedin.com",
    "youtube.com",
    "www.youtube.com",
    "wikipedia.org",
    "www.wikipedia.org",
    "stackoverflow.com",
    "www.stackoverflow.com",
    "netflix.com",
    "www.netflix.com",
    "paypal.com",
    "www.paypal.com",
}


def _check_whitelist(url: str) -> bool:
    """Check if URL is on known legitimate domain whitelist."""
    try:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()
        # Strip www. for comparison
        domain_no_www = domain.replace("www.", "")
        return (
            domain in KNOWN_LEGITIMATE_DOMAINS
            or domain_no_www in KNOWN_LEGITIMATE_DOMAINS
        )
    except Exception:
        return False


# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION LOADING
# ============================================================

CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "configs/dev/config.yaml"))

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
    logger.info(f"✓ Loaded configuration from {CONFIG_PATH}")
except Exception as e:
    logger.error(f"✗ Failed to load config from {CONFIG_PATH}: {e}")
    CONFIG = {}

# Extract model service config
MODEL_CONFIG = CONFIG.get("model_service", {})
PRIMARY_CONFIG = MODEL_CONFIG.get("primary", {})
SHADOW_CONFIG = MODEL_CONFIG.get("shadow", {})

# Environment variable overrides - PRIMARY NOW USES 8-FEATURE MODEL
PRIMARY_MODEL_PATH = Path(
    os.getenv("MODEL_PATH", PRIMARY_CONFIG.get("path", "models/dev/model_8feat.pkl"))
)
PRIMARY_META_PATH = Path(
    os.getenv(
        "MODEL_META_PATH",
        PRIMARY_CONFIG.get("meta_path", "models/dev/model_8feat_meta.json"),
    )
)

# Shadow mode disabled for production (Option A: 8-feature primary only)
SHADOW_ENABLED = os.getenv("SHADOW_ENABLED", "false").lower() == "true"

SHADOW_MODEL_PATH: Optional[Path]
SHADOW_META_PATH: Optional[Path]

if SHADOW_ENABLED:
    SHADOW_MODEL_PATH = Path(
        os.getenv(
            "SHADOW_MODEL_PATH", SHADOW_CONFIG.get("path", "models/dev/model_7feat.pkl")
        )
    )
    SHADOW_META_PATH = Path(
        os.getenv(
            "SHADOW_META_PATH",
            SHADOW_CONFIG.get("meta_path", "models/dev/model_7feat_meta.json"),
        )
    )
    print(f"Shadow mode ENABLED: {SHADOW_MODEL_PATH}")
else:
    SHADOW_MODEL_PATH = None
    SHADOW_META_PATH = None
    print("Shadow mode DISABLED (production mode)")

# ============================================================
# GLOBAL MODEL STORAGE
# ============================================================

_primary_model: Optional[Any] = None
_primary_meta: Dict = {}
_primary_feature_order: list = []
_primary_phish_col_ix: int = 0

_shadow_model: Optional[Any] = None
_shadow_meta: Dict = {}
_shadow_feature_order: list = []
_shadow_phish_col_ix: int = 0


# ============================================================
# MODEL LOADING
# ============================================================


def load_model_artifact(model_path: Path, meta_path: Path) -> tuple[Any, Dict]:
    """Load a model and its metadata."""
    model = None
    meta = {}

    try:
        if model_path.exists():
            model = joblib.load(model_path)
            logger.info(f"✓ Loaded model from {model_path}")
        else:
            logger.warning(f"✗ Model not found: {model_path}")

        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            logger.info(f"✓ Loaded metadata from {meta_path}")

            # DEBUG: Log metadata details
            logger.info(f"  Model type: {meta.get('model_type', 'unknown')}")
            logger.info(f"  Feature count: {len(meta.get('feature_order', []))}")
            logger.info(
                f"  Phish proba column index: {meta.get('phish_proba_col_index', 0)}"
            )
            logger.info(f"  Features: {meta.get('feature_order', [])}")
        else:
            logger.warning(f"✗ Metadata not found: {meta_path}")

    except Exception as e:
        logger.error(f"✗ Failed to load model/metadata: {e}", exc_info=True)

    return model, meta


# ============================================================
# FASTAPI LIFESPAN
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # ========== STARTUP ==========
    global _primary_model, _primary_meta, _primary_feature_order, _primary_phish_col_ix
    global _shadow_model, _shadow_meta, _shadow_feature_order, _shadow_phish_col_ix

    logger.info("=" * 60)
    logger.info("PhishGuard Model Service Starting (DEBUG MODE)")
    logger.info("=" * 60)
    logger.info(f"Config file: {CONFIG_PATH}")
    logger.info(f"Primary model: {PRIMARY_MODEL_PATH}")
    logger.info(f"Shadow enabled: {SHADOW_ENABLED}")
    if SHADOW_ENABLED:
        logger.info(f"Shadow model: {SHADOW_MODEL_PATH}")
    logger.info("=" * 60)

    # Load primary model
    _primary_model, _primary_meta = load_model_artifact(
        PRIMARY_MODEL_PATH, PRIMARY_META_PATH
    )
    _primary_feature_order = _primary_meta.get("feature_order", [])
    _primary_phish_col_ix = int(_primary_meta.get("phish_proba_col_index", 0))

    logger.info("\nPRIMARY MODEL CONFIGURATION:")
    logger.info(f"  Feature order: {_primary_feature_order}")
    logger.info(f"  Phish column index: {_primary_phish_col_ix}")
    logger.info(f"  Class mapping: {_primary_meta.get('class_mapping', {})}")

    # Load shadow model if enabled
    if SHADOW_ENABLED:
        assert SHADOW_MODEL_PATH is not None
        assert SHADOW_META_PATH is not None
        _shadow_model, _shadow_meta = load_model_artifact(
            SHADOW_MODEL_PATH, SHADOW_META_PATH
        )
        _shadow_feature_order = _shadow_meta.get("feature_order", [])
        _shadow_phish_col_ix = int(_shadow_meta.get("phish_proba_col_index", 0))
        logger.info("✓ Shadow mode ENABLED")

        logger.info("\nSHADOW MODEL CONFIGURATION:")
        logger.info(f"  Feature order: {_shadow_feature_order}")
        logger.info(f"  Phish column index: {_shadow_phish_col_ix}")
    else:
        logger.info("○ Shadow mode DISABLED")

    logger.info("=" * 60)
    logger.info("✓ Model Service Ready")
    logger.info("=" * 60)

    yield

    # ========== SHUTDOWN ==========
    logger.info("PhishGuard Model Service Shutting Down")


# ============================================================
# CREATE FASTAPI APP
# ============================================================

app = FastAPI(
    title="PhishGuard Model Service", version="0.2.0-debug", lifespan=lifespan
)


# ============================================================
# PYDANTIC MODELS
# ============================================================


class PredictRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="URL to analyze")


class ShadowPrediction(BaseModel):
    p_malicious: float = Field(..., description="Shadow model prediction")
    model_name: str = Field(..., description="Shadow model identifier")
    agreement: bool = Field(
        ..., description="Whether shadow agrees with primary (within 0.1)"
    )


class PredictResponse(BaseModel):
    p_malicious: float = Field(
        ..., description="Probability that URL is malicious (0.0-1.0)"
    )
    source: str = Field(..., description="Prediction source: 'model' or 'heuristic'")
    model_name: Optional[str] = Field(None, description="Primary model identifier")
    shadow: Optional[ShadowPrediction] = Field(
        None, description="Shadow model prediction (if enabled)"
    )


class ExplainRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="URL to explain")


class ExplainResponse(BaseModel):
    p_malicious: float = Field(
        ..., description="Probability that URL is malicious (0.0-1.0)"
    )
    feature_contributions: dict = Field(..., description="SHAP values for each feature")
    feature_values: dict = Field(..., description="Feature values for the input URL")
    source: str = Field(..., description="Prediction source: 'model' or 'heuristic'")
    model_name: Optional[str] = Field(None, description="Primary model identifier")


# ============================================================
# FEATURE ENGINEERING
# ============================================================


def engineer_features_for_model(url: str, feature_order: list[str]) -> pd.DataFrame:
    """
    Extract features for model inference with debug logging.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"FEATURE ENGINEERING FOR: {url}")
    logger.info(f"{'=' * 60}")

    # Determine if this model needs IsHTTPS
    include_https = "IsHTTPS" in feature_order
    logger.info(f"Include IsHTTPS: {include_https}")

    # Extract features using shared library
    features_dict = extract_features(url, include_https=include_https)

    logger.info("\nEXTRACTED FEATURES:")
    for k, v in features_dict.items():
        logger.info(f"  {k:35s} = {v}")

    # Validate features
    is_valid = validate_features(features_dict, include_https=include_https)
    logger.info(f"\nFeature validation: {'✓ PASSED' if is_valid else '✗ FAILED'}")

    if not is_valid:
        logger.error(f"Feature validation failed for URL: {url}")
        raise ValueError("Feature validation failed")

    # Convert to DataFrame
    df = pd.DataFrame([features_dict])
    logger.info(f"\nDataFrame shape (before reorder): {df.shape}")
    logger.info(f"DataFrame columns (before reorder): {list(df.columns)}")

    # Reorder columns to match model's expected order
    if feature_order:
        missing_cols = set(feature_order) - set(df.columns)
        if missing_cols:
            logger.error(f"Missing features for model: {missing_cols}")
            raise ValueError(f"Missing required features: {missing_cols}")

        logger.info("\nREORDERING to match model:")
        for i, feat in enumerate(feature_order):
            logger.info(f"  Position {i}: {feat}")

        df = df[feature_order]

        logger.info(f"\nDataFrame shape (after reorder): {df.shape}")
        logger.info(f"DataFrame columns (after reorder): {list(df.columns)}")
        logger.info("\nFINAL FEATURE VALUES:")
        for i, (col, val) in enumerate(zip(df.columns, df.iloc[0].values)):
            logger.info(f"  [{i}] {col:35s} = {val}")

    logger.info(f"{'=' * 60}\n")

    return df


# ============================================================
# HEURISTIC FALLBACK
# ============================================================


def url_heuristic_score(url: str) -> float:
    """
    Simple heuristic for phishing probability (fallback when model unavailable).

    WARNING: Penalty weights are EXPERT-ESTIMATED, not data-derived.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        score = 0.0

        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()

        # Domain indicators
        if any(
            word in domain for word in ["login", "secure", "bank", "paypal", "verify"]
        ):
            score += 0.2

        if len(domain.split(".")) > 3:
            score += 0.15

        if any(char in domain for char in ["-", "_"]) and len(domain) > 15:
            score += 0.1

        # Path indicators
        if any(
            word in path for word in ["login", "signin", "account", "verify", "update"]
        ):
            score += 0.2

        if len(path) > 50:
            score += 0.1

        # Query parameter indicators
        if any(word in query for word in ["acct", "account", "id", "token", "session"]):
            score += 0.15

        if len(query) > 100:
            score += 0.1

        # URL length
        if len(url) > 100:
            score += 0.1

        return min(max(score, 0.0), 0.99)

    except Exception as e:
        logger.warning(f"Heuristic scoring failed for {url}: {e}")
        return 0.5


# ============================================================
# PREDICTION
# ============================================================


def predict_with_model(
    model: Any,
    url: str,
    feature_order: list[str],
    phish_col_ix: int,
    model_name: str = "unknown",
) -> float:
    """Make prediction with extensive debug logging."""

    logger.info(f"\n{'=' * 60}")
    logger.info(f"PREDICTION WITH {model_name.upper()}")
    logger.info(f"{'=' * 60}")

    # Extract and prepare features
    features_df = engineer_features_for_model(url, feature_order)

    logger.info("\nCALLING model.predict_proba()...")
    probas = model.predict_proba(features_df)

    logger.info("\nMODEL OUTPUT (predict_proba):")
    logger.info(f"  Shape: {probas.shape}")
    logger.info(f"  Raw output: {probas}")
    logger.info(f"  Column 0 (index {0}): {probas[0][0]:.6f}")
    logger.info(f"  Column 1 (index {1}): {probas[0][1]:.6f}")
    logger.info(f"  Using phish_col_ix: {phish_col_ix}")

    p_malicious = float(probas[0][phish_col_ix])
    logger.info(f"\nEXTRACTED p_malicious: {p_malicious:.6f}")

    # Validate output
    if not (0.0 <= p_malicious <= 1.0):
        logger.error(f"Invalid probability: {p_malicious}")
        raise ValueError(f"Invalid probability: {p_malicious}")

    logger.info(f"{'=' * 60}\n")

    return p_malicious


# ============================================================
# API ENDPOINTS
# ============================================================
@app.post("/predict/explain", response_model=ExplainResponse)
def explain(request: ExplainRequest):
    """
    Return SHAP feature contributions for a given URL using the primary model.
    """
    url = request.url
    if _primary_model is None:
        return JSONResponse(
            status_code=503, content={"error": "Primary model not loaded"}
        )

    # Fast path: Check whitelist BEFORE calling model
    if _check_whitelist(url):
        return ExplainResponse(
            p_malicious=0.01,
            feature_contributions={},
            feature_values={},
            source="whitelist",
            model_name="domain-whitelist",
        )

    # Extract features
    try:
        features_df = engineer_features_for_model(url, _primary_feature_order)
        # Convert numpy values to Python floats for JSON serialization
        feature_values = {k: float(v) for k, v in dict(features_df.iloc[0]).items()}
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": f"Feature extraction failed: {e}"}
        )

    # Compute prediction
    try:
        p_malicious = float(
            _primary_model.predict_proba(features_df)[0][_primary_phish_col_ix]
        )
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"Model prediction failed: {e}"}
        )

    # SHAP explainability
    try:
        # For CalibratedClassifierCV, we need to access the base estimator
        # Try TreeExplainer first (for XGBoost), fallback to KernelExplainer
        try:
            # Access the base estimator from CalibratedClassifierCV
            base_estimator = _primary_model.calibrated_classifiers_[0].estimator
            explainer = shap.TreeExplainer(base_estimator)
            shap_values = explainer.shap_values(features_df)
            # For binary classification, shap_values might be a list [neg, pos]
            if isinstance(shap_values, list):
                shap_values = shap_values[_primary_phish_col_ix]
            # Convert numpy values to Python floats for JSON serialization
            contributions = {
                k: float(v) for k, v in zip(features_df.columns, shap_values[0])
            }
        except Exception as tree_err:
            logger.warning(f"TreeExplainer failed: {tree_err}, trying KernelExplainer")

            # Fallback to KernelExplainer (slower but more general)
            def model_predict(X):
                return _primary_model.predict_proba(X)[:, _primary_phish_col_ix]

            explainer = shap.KernelExplainer(model_predict, features_df)
            shap_values = explainer.shap_values(features_df)
            # Convert numpy values to Python floats for JSON serialization
            contributions = {
                k: float(v) for k, v in zip(features_df.columns, shap_values[0])
            }
    except Exception as e:
        logger.error(f"SHAP explainability failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"SHAP explainability failed: {str(e)}"}
        )

    return ExplainResponse(
        p_malicious=p_malicious,
        feature_contributions=contributions,
        feature_values=feature_values,
        source="model",
        model_name=PRIMARY_CONFIG.get("name", "primary"),
    )


@app.get("/health")
def health():
    """Health check endpoint with model status."""
    return {
        "status": "ok",
        "service": "model-svc",
        "version": "0.2.0-debug",
        "models": {
            "primary": {
                "loaded": _primary_model is not None,
                "name": PRIMARY_CONFIG.get("name", "unknown"),
                "features": len(_primary_feature_order),
                "feature_order": _primary_feature_order,
                "phish_col_ix": _primary_phish_col_ix,
            },
            "shadow": {
                "enabled": SHADOW_ENABLED,
                "loaded": _shadow_model is not None if SHADOW_ENABLED else None,
                "name": (
                    SHADOW_CONFIG.get("name", "unknown") if SHADOW_ENABLED else None
                ),
                "features": len(_shadow_feature_order) if SHADOW_ENABLED else None,
            },
        },
    }


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """
    Predict phishing probability with extensive debug logging.
    """
    # Fast path: Check whitelist BEFORE calling model
    if _check_whitelist(request.url):
        logger.info(f"✓ WHITELIST HIT: {request.url} - bypassing model prediction")
        return PredictResponse(
            p_malicious=0.01,
            source="whitelist",
            model_name="domain-whitelist",
            shadow=None,
        )

    url = request.url

    logger.info(f"\n\n{'#' * 60}")
    logger.info("# NEW PREDICTION REQUEST")
    logger.info(f"# URL: {url}")
    logger.info(f"{'#' * 60}\n")

    # ========================================
    # PRIMARY MODEL PREDICTION
    # ========================================

    p_malicious_primary = None
    source = "heuristic"
    model_name_primary = None

    if _primary_model is not None:
        try:
            p_malicious_primary = predict_with_model(
                _primary_model,
                url,
                _primary_feature_order,
                _primary_phish_col_ix,
                model_name="PRIMARY (8-feature)",
            )
            source = "model"
            model_name_primary = PRIMARY_CONFIG.get("name", "primary")

            logger.info(
                f"\n✓ PRIMARY MODEL SUCCESS: p_malicious = {p_malicious_primary:.6f}\n"
            )

        except Exception as e:
            logger.error(f"\n✗ PRIMARY MODEL FAILED: {e}", exc_info=True)
            logger.error("Falling back to heuristic\n")

    # Fallback to heuristic if model failed
    if p_malicious_primary is None:
        p_malicious_primary = url_heuristic_score(url)
        source = "heuristic"
        logger.warning(
            f"Using heuristic fallback: p_malicious = {p_malicious_primary:.4f}"
        )

    # ========================================
    # SHADOW MODEL PREDICTION (Optional)
    # ========================================

    shadow_result = None

    # Shadow model (only if enabled)
    if SHADOW_ENABLED and _shadow_model is not None and source == "model":
        try:
            p_malicious_shadow = predict_with_model(
                _shadow_model,
                url,
                _shadow_feature_order,
                _shadow_phish_col_ix,
                model_name="SHADOW (7-feature)",
            )

            # Log shadow prediction details
            logger.info(f"Shadow prediction: {p_malicious_shadow:.6f}")

            agreement = abs(p_malicious_primary - p_malicious_shadow) < 0.1

            shadow_result = ShadowPrediction(
                p_malicious=p_malicious_shadow,
                model_name=SHADOW_CONFIG.get("name", "shadow"),
                agreement=agreement,
            )

            logger.info(
                f"\n✓ SHADOW MODEL SUCCESS: p_malicious = {p_malicious_shadow:.6f}"
            )
            logger.info(
                f"Agreement: {agreement} "
                f"(diff = {abs(p_malicious_primary - p_malicious_shadow):.6f})\n"
            )

        except Exception as e:
            logger.warning(f"Shadow prediction failed: {e}")
            logger.error(f"\n✗ SHADOW MODEL FAILED: {e}", exc_info=True)

    # ========================================
    # RETURN RESPONSE
    # ========================================

    logger.info("#" * 60)
    logger.info("# FINAL RESULT")
    logger.info(f"# p_malicious: {p_malicious_primary:.6f}")
    logger.info(f"# source: {source}")
    logger.info("#" * 60 + "\n\n")

    return PredictResponse(
        p_malicious=p_malicious_primary,
        source=source,
        model_name=model_name_primary,
        shadow=shadow_result,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)  # nosec B104
