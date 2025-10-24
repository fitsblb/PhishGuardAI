"""
Model service: inference endpoint for calibrated phishing classifier.
Supports both primary (7-feat) and shadow (8-feat) models for temporal drift monitoring.

The service extracts URL-only features, runs prediction, and returns calibrated
phishing probability along with the feature vector used.

Architecture:
- Primary model: 7 features (IsHTTPS removed due to distribution shift)
- Shadow model: 8 features (optional, for A/B testing)
- Feature extraction: Metadata-driven (auto-detects required features)
- Graceful fallback: Heuristic scoring if model service fails

Endpoints:
- POST /predict: Main inference endpoint
- GET /health: Service health check
- GET /config: Model configuration and metadata
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from common.feature_extraction import extract_features, validate_features

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG_PATH = os.getenv("MODEL_SVC_CONFIG", "configs/dev/config.yaml")

try:
    import yaml

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
    logger.info(f"✓ Loaded configuration from {CONFIG_PATH}")
except Exception as e:
    logger.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    CONFIG = {}

# Model paths
PRIMARY_MODEL_PATH = CONFIG.get("model", {}).get(
    "primary_path", "models/dev/model_7feat.pkl"
)
PRIMARY_META_PATH = PRIMARY_MODEL_PATH.replace(".pkl", "_meta.json")

SHADOW_ENABLED = CONFIG.get("model", {}).get("shadow", {}).get("enabled", False)
SHADOW_MODEL_PATH = (
    CONFIG.get("model", {}).get("shadow", {}).get("path", "models/dev/model_8feat.pkl")
)
SHADOW_META_PATH = (
    SHADOW_MODEL_PATH.replace(".pkl", "_meta.json") if SHADOW_ENABLED else None
)

logger.info(f"Primary model: {PRIMARY_MODEL_PATH}")
logger.info(f"Shadow enabled: {SHADOW_ENABLED}")

# ============================================================
# MODEL LOADING
# ============================================================
logger.info("=" * 60)

try:
    PRIMARY_MODEL = joblib.load(PRIMARY_MODEL_PATH)
    logger.info(f"✓ Loaded model from {PRIMARY_MODEL_PATH}")

    with open(PRIMARY_META_PATH, "r", encoding="utf-8") as f:
        PRIMARY_META = json.load(f)
    logger.info(f"✓ Loaded metadata from {PRIMARY_META_PATH}")

    logger.info(f"  Model type: {type(PRIMARY_MODEL).__name__}")
    logger.info(f"  Feature count: {PRIMARY_META.get('features', 'unknown')}")
    logger.info(f"  Phish proba column index: {PRIMARY_META.get('phish_proba_col', 0)}")
    logger.info(f"  Features: {PRIMARY_META.get('feature_order', [])}")

except Exception as e:
    logger.error(f"✗ Failed to load primary model: {e}")
    raise

SHADOW_MODEL = None
SHADOW_META = None

if SHADOW_ENABLED:
    try:
        SHADOW_MODEL = joblib.load(SHADOW_MODEL_PATH)
        logger.info(f"✓ Loaded shadow model from {SHADOW_MODEL_PATH}")

        with open(SHADOW_META_PATH, "r", encoding="utf-8") as f:
            SHADOW_META = json.load(f)
        logger.info(f"✓ Loaded shadow metadata from {SHADOW_META_PATH}")

    except Exception as e:
        logger.warning(f"○ Shadow model loading failed: {e}")
        SHADOW_ENABLED = False

logger.info("")
logger.info("PRIMARY MODEL CONFIGURATION:")
logger.info(f"  Feature order: {PRIMARY_META.get('feature_order', [])}")
logger.info(f"  Phish column index: {PRIMARY_META.get('phish_proba_col', 0)}")
logger.info("  Class mapping: {'phish': 0, 'legit': 1}")

if SHADOW_ENABLED:
    logger.info("")
    logger.info("SHADOW MODEL CONFIGURATION:")
    logger.info(f"  Feature order: {SHADOW_META.get('feature_order', [])}")
    logger.info(f"  Phish column index: {SHADOW_META.get('phish_proba_col', 0)}")
else:
    logger.info("○ Shadow mode DISABLED")

logger.info("=" * 60)
logger.info("✓ Model Service Ready")
logger.info("=" * 60)

# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title="PhishGuard Model Service",
    version="0.1.0",
    description="Phishing detection model inference service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MODELS
# ============================================================


class PredictIn(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class PredictOut(BaseModel):
    p_malicious: float
    source: str = "model"
    model_name: str
    shadow: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, float]] = None


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


def predict_with_model(
    url: str,
    model: Any,
    metadata: Dict[str, Any],
    model_label: str = "primary",
) -> float:
    """
    Run prediction with a given model.

    Args:
        url: URL to classify
        model: Trained model object
        metadata: Model metadata (feature_order, phish_proba_col, etc.)
        model_label: Label for logging (e.g., "primary", "shadow")

    Returns:
        p_malicious: Probability that URL is phishing [0.0, 1.0]
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PREDICTION WITH {model_label.upper()} MODEL")
    logger.info(f"{'=' * 60}")

    # Extract features
    feature_order = metadata.get("feature_order", [])
    if not feature_order:
        raise ValueError(f"No feature_order in {model_label} model metadata")

    features_df = engineer_features_for_model(url, feature_order)

    # Run prediction
    logger.info("\nCALLING model.predict_proba()...")
    proba = model.predict_proba(features_df)

    logger.info("\nMODEL OUTPUT (predict_proba):")
    logger.info(f"  Shape: {proba.shape}")
    logger.info(f"  Raw output: {proba}")

    # Log all columns
    for i in range(proba.shape[1]):
        logger.info(f"  Column {i} (index {i}): {proba[0, i]:.6f}")

    # Extract phishing probability
    phish_col_ix = metadata.get("phish_proba_col", 0)
    logger.info(f"  Using phish_col_ix: {phish_col_ix}")

    p_malicious = float(proba[0, phish_col_ix])

    logger.info(f"\nEXTRACTED p_malicious: {p_malicious:.6f}")
    logger.info(f"{'=' * 60}\n")

    return p_malicious


# ============================================================
# ENDPOINTS
# ============================================================


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "model_svc",
        "version": app.version,
        "models": {"primary": PRIMARY_MODEL_PATH, "shadow_enabled": SHADOW_ENABLED},
    }


@app.get("/config")
def config():
    return {
        "primary": {"path": PRIMARY_MODEL_PATH, "metadata": PRIMARY_META},
        "shadow": {
            "enabled": SHADOW_ENABLED,
            "path": SHADOW_MODEL_PATH if SHADOW_ENABLED else None,
            "metadata": SHADOW_META if SHADOW_ENABLED else None,
        },
    }


@app.post("/predict", response_model=PredictOut)
def predict(payload: PredictIn) -> PredictOut:
    """
    Predict phishing probability for a given URL.

    This endpoint:
    1. Extracts 7 URL-only features (IsHTTPS removed due to distribution shift)
    2. Runs primary model prediction
    3. Optionally runs shadow model for A/B testing
    4. Returns calibrated probability + features used

    Returns:
        PredictOut with:
        - p_malicious: Phishing probability [0.0, 1.0]
        - source: "model" (ML prediction) or "heuristic" (fallback)
        - model_name: Model identifier
        - shadow: Shadow model results (if enabled)
        - features: Feature vector used for prediction (7 features)
    """
    logger.info(f"\n{'#' * 60}")
    logger.info("# PREDICTION REQUEST")
    logger.info(f"# URL: {payload.url}")
    logger.info(f"{'#' * 60}\n")

    # Extract features for response (7-feature production model)
    features_dict = extract_features(payload.url, include_https=False)

    # Primary model prediction
    p_malicious_primary = 0.1  # Fallback
    source = "heuristic"

    try:
        p_malicious_primary = predict_with_model(
            payload.url, PRIMARY_MODEL, PRIMARY_META, model_label="primary"
        )
        source = "model"

    except Exception as e:
        logger.error(f"\n✗ PRIMARY MODEL FAILED: {e}")
        import traceback

        traceback.print_exc()
        logger.error("Falling back to heuristic")

    # Shadow model prediction (optional)
    shadow_result = None

    if SHADOW_ENABLED and SHADOW_MODEL is not None and source == "model":
        try:
            p_malicious_shadow = predict_with_model(
                payload.url, SHADOW_MODEL, SHADOW_META, model_label="shadow"
            )

            shadow_result = {
                "model_name": SHADOW_META.get("model_name", "8-feature-shadow-v1"),
                "p_malicious": p_malicious_shadow,
                "diff": p_malicious_primary - p_malicious_shadow,
            }

            logger.info("\nSHADOW MODEL COMPARISON:")
            logger.info(f"  Primary: {p_malicious_primary:.6f}")
            logger.info(f"  Shadow:  {p_malicious_shadow:.6f}")
            logger.info(f"  Diff:    {shadow_result['diff']:.6f}")

        except Exception as e:
            logger.warning(f"\n○ SHADOW MODEL FAILED: {e}")
            shadow_result = {"error": str(e)}

    # Heuristic fallback message
    if source == "heuristic":
        logger.warning(
            f"Using heuristic fallback: p_malicious = {p_malicious_primary:.4f}"
        )

    # Final result
    logger.info(f"\n{'#' * 60}")
    logger.info("# FINAL RESULT")
    logger.info(f"# p_malicious: {p_malicious_primary:.6f}")
    logger.info(f"# source: {source}")
    logger.info(f"{'#' * 60}\n")

    return PredictOut(
        p_malicious=p_malicious_primary,
        source=source,
        model_name=PRIMARY_META.get("model_name", "7-feature-production-v1"),
        shadow=shadow_result,
        features=features_dict,
    )


@app.post("/predict/explain")
def predict_explain(payload: PredictIn):
    """
    Get SHAP explainability for a prediction.

    Returns feature importance values showing which features contributed
    most to the phishing/legitimate classification.

    Note: For calibrated models, SHAP is computed on the base estimator
    (before calibration), so values are approximate.
    """
    try:
        # Extract features
        features_df = engineer_features_for_model(
            payload.url, PRIMARY_META["feature_order"]
        )

        # Get prediction from FULL calibrated model
        proba = PRIMARY_MODEL.predict_proba(features_df)
        phish_col_ix = PRIMARY_META.get("phish_proba_col", 0)
        p_malicious = float(proba[0, phish_col_ix])

        # Unwrap base estimator for SHAP
        # CalibratedClassifierCV wraps the actual tree model
        base_model = PRIMARY_MODEL

        # Check if it's a CalibratedClassifierCV and unwrap
        if hasattr(PRIMARY_MODEL, "calibrated_classifiers_"):
            # Get the base estimator from the first calibrated classifier
            base_model = PRIMARY_MODEL.calibrated_classifiers_[0].estimator
            logger.info(f"Unwrapped calibrated model. Base type: {type(base_model)}")

        # Create SHAP explainer on base model
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(features_df)

        # Extract SHAP values for phishing class
        if isinstance(shap_values, list):
            shap_vals = shap_values[phish_col_ix]
        else:
            shap_vals = shap_values

        # Get base value
        base_value = explainer.expected_value
        if isinstance(base_value, (list, np.ndarray)):
            base_value = base_value[phish_col_ix]

        # Build feature contributions
        feature_names = PRIMARY_META["feature_order"]
        contributions = {}

        for i, feat in enumerate(feature_names):
            contributions[feat] = {
                "value": float(features_df.iloc[0, i]),
                "shap_value": float(shap_vals[0, i]),
                "importance": abs(float(shap_vals[0, i])),
            }

        # Sort by absolute importance (most important first)
        sorted_contribs = dict(
            sorted(
                contributions.items(), key=lambda x: x[1]["importance"], reverse=True
            )
        )

        # Get top 3 features for summary
        top_features = list(sorted_contribs.keys())[:3]

        return {
            "url": payload.url,
            "p_malicious": p_malicious,
            "base_value": float(base_value),
            "features": sorted_contribs,
            "top_features": top_features,
            "model_name": PRIMARY_META.get("model_name", "7-feature-production-v1"),
            "explanation": "Positive SHAP values push towards phishing; negative towards legitimate",
            "note": "SHAP computed on base estimator (before calibration) for approximate feature importance",
        }

    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"error": "SHAP not installed. Install with: pip install shap"},
        )
    except Exception as e:
        import traceback

        logger.error(f"SHAP explanation failed: {e}")
        traceback.print_exc()

        # Fallback: return basic feature information without SHAP
        try:
            features_df = engineer_features_for_model(
                payload.url, PRIMARY_META["feature_order"]
            )
            proba = PRIMARY_MODEL.predict_proba(features_df)
            phish_col_ix = PRIMARY_META.get("phish_proba_col", 0)
            p_malicious = float(proba[0, phish_col_ix])

            # Build basic feature contributions without SHAP
            feature_names = PRIMARY_META["feature_order"]
            contributions = {}
            for i, feat in enumerate(feature_names):
                contributions[feat] = {
                    "value": float(features_df.iloc[0, i]),
                    "shap_value": None,  # No SHAP available
                    "importance": None,  # No importance available
                }

            return {
                "url": payload.url,
                "p_malicious": p_malicious,
                "base_value": None,
                "features": contributions,
                "top_features": list(contributions.keys())[:3],
                "model_name": PRIMARY_META.get("model_name", "7-feature-production-v1"),
                "explanation": "SHAP explanation unavailable due to model "
                "compatibility issue",
                "note": "Showing feature values only - SHAP analysis failed",
                "shap_error": str(e),
            }
        except Exception as fallback_e:
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Both SHAP and fallback explanation failed: "
                    f"{str(e)}, {str(fallback_e)}",
                    "details": str(traceback.format_exc()),
                },
            )
