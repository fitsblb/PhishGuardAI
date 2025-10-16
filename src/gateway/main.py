from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from common.stats import reset, snapshot
from common.thresholds import Thresholds, load_thresholds
from gateway.judge_wire import decide_with_judge

# ===================================================================
# WHITELIST: Known legitimate domains (handles OOD major tech sites)
# ===================================================================
KNOWN_LEGITIMATE_DOMAINS = {
    "google.com",
    "www.google.com",
    "github.com",
    "example.com",
    "www.example.com",
    "openai.com",
    "www.openai.com",
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
    "ebay.com",
    "www.ebay.com",
}


def _check_whitelist(url: str) -> bool:
    """Check if URL is on known legitimate domain whitelist."""
    try:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()
        # Strip www. prefix for comparison
        domain_no_www = domain.replace("www.", "")
        return (
            domain in KNOWN_LEGITIMATE_DOMAINS
            or domain_no_www in KNOWN_LEGITIMATE_DOMAINS
        )
    except Exception:
        return False


# List of expected extras keys for normalization
_EXPECTED_EXTRAS_KEYS = [
    "TLDLegitimateProb",
    "NoOfOtherSpecialCharsInURL",
    "SpacialCharRatioInURL",
    "CharContinuationRate",
    "URLCharProb",
    "url_len",
    "url_digit_ratio",
    "url_subdomains",
]


# Normalize extras dict to ensure all expected keys are present
def _normalize_extras(extras: dict | None) -> dict:
    base = {k: None for k in _EXPECTED_EXTRAS_KEYS}
    if extras:
        for k in _EXPECTED_EXTRAS_KEYS:
            if k in extras:
                base[k] = extras[k]
    return base


# --------- Config ---------
THRESH_PATH = os.getenv("THRESHOLDS_JSON", "configs/dev/thresholds.json")
MAX_REQ_BYTES = int(os.getenv("MAX_REQ_BYTES", "8192"))  # 8KB default
CORS_ORIGINS = [
    s.strip()
    for s in os.getenv(
        "GATEWAY_CORS_ORIGINS", "http://localhost,http://127.0.0.1"
    ).split(",")
    if s.strip()
]

# --------- App & middleware ---------
app = FastAPI(title="PhishGuard Gateway", version="0.1.0")


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_REQ_BYTES:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


app.add_middleware(ContentSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# --------- thresholds (load once) ---------
TH: Thresholds = load_thresholds(THRESH_PATH)


# --------- Models ---------
class ExtrasIn(BaseModel):
    TLDLegitimateProb: Optional[float] = Field(None, ge=0.0, le=1.0)
    NoOfOtherSpecialCharsInURL: Optional[int] = Field(None, ge=0)
    SpacialCharRatioInURL: Optional[float] = Field(None, ge=0.0, le=1.0)
    CharContinuationRate: Optional[float] = Field(None, ge=0.0, le=1.0)
    URLCharProb: Optional[float] = Field(None, ge=0.0, le=1.0)


class PredictIn(BaseModel):
    # Guard extremes: realistic upper bound; empty/whitespace rejected
    # by min_length & stripping on client
    url: str = Field(min_length=3, max_length=2048)
    p_malicious: Optional[float] = Field(None, ge=0.0, le=1.0)
    extras: Optional[ExtrasIn] = None


class PredictOut(BaseModel):
    url: str
    p_malicious: float
    decision: Literal["ALLOW", "REVIEW", "BLOCK"]
    reason: str
    thresholds: Dict[str, float]
    judge: Optional[Dict[str, Any]] = None
    source: Literal["model", "heuristic", "whitelist"]


# --------- tiny deterministic URL helpers (fallback heuristic) ---------
def _url_len(s: str) -> int:
    return len(s) if isinstance(s, str) else 0


def _digit_ratio(s: str) -> float:
    if not isinstance(s, str) or not s:
        return 0.0
    d = sum(ch.isdigit() for ch in s)
    return d / len(s)


def _subdomain_count(s: str) -> int:
    if not isinstance(s, str) or not s:
        return 0
    host = s.split("://", 1)[-1].split("/", 1)[0]
    return max(0, host.count(".") - 1)


def _heuristic_pmal(url: str) -> float:
    risk = 0.0
    L = _url_len(url)
    if L >= 160:
        risk += 0.50
    elif L >= 100:
        risk += 0.35
    elif L >= 80:
        risk += 0.20
    dr = _digit_ratio(url)
    if dr >= 0.30:
        risk += 0.35
    elif dr >= 0.20:
        risk += 0.20
    elif dr >= 0.10:
        risk += 0.10
    sd = _subdomain_count(url)
    if sd >= 4:
        risk += 0.20
    elif sd >= 3:
        risk += 0.10
    url_l = url.lower()
    if any(tok in url_l for tok in ["login", "verify", "update", "secure", "account"]):
        risk += 0.10
    return max(0.0, min(1.0, risk))


def _call_model_service(url: str, extras: Dict[str, Any]) -> Optional[float]:
    """
    Call the model service to get p_malicious prediction.
    Returns None if service unavailable or on error.
    """
    model_url = os.environ.get("MODEL_SVC_URL")
    print(f"[DEBUG] MODEL_SVC_URL: {model_url}")  # Debug
    if not model_url:
        print("[DEBUG] No MODEL_SVC_URL set")  # Debug
        return None

    try:
        # Use model service API schema: {"url": "..."}
        payload = {"url": url}
        print(f"[DEBUG] Calling {model_url}/predict with payload: {payload}")  # Debug
        response = requests.post(f"{model_url}/predict", json=payload, timeout=3.0)
        print(f"[DEBUG] Response status: {response.status_code}")  # Debug
        response.raise_for_status()
        data = response.json()
        print(f"[DEBUG] Response data: {data}")  # Debug
        p_malicious = data.get("p_malicious")

        # Validate probability is in valid range [0.0, 1.0]
        if p_malicious is None or not isinstance(p_malicious, (int, float)):
            print(f"[DEBUG] Invalid p_malicious: {p_malicious}")  # Debug
            return None
        if not (0.0 <= p_malicious <= 1.0):
            print(f"[DEBUG] p_malicious out of range: {p_malicious}")  # Debug
            return None

        print(f"[DEBUG] Model service success: {p_malicious}")  # Debug
        return float(p_malicious)
    except Exception as e:
        print(f"[DEBUG] Model service error: {e}")  # Debug
        return None


# --------- Routes ---------
@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway", "version": app.version}


@app.get("/config")
def config():
    return {"thresholds": TH, "thresholds_path": THRESH_PATH}


@app.post("/predict", response_model=PredictOut)
def predict(payload: PredictIn):
    """
    Main prediction endpoint with whitelist, model service, and heuristic fallback.
    """
    # PHASE 1: Fast-path whitelist check
    if _check_whitelist(payload.url):
        return PredictOut(
            url=payload.url,
            p_malicious=0.01,  # Very low risk for whitelisted domains
            decision="ALLOW",
            reason="domain-whitelist",
            thresholds={
                "low": TH["low"],
                "high": TH["high"],
                "t_star": TH["t_star"],
                "gray_zone_rate": TH["gray_zone_rate"],
            },
            judge=None,
            source="whitelist",
        )

    # PHASE 2: Determine p_malicious source
    extras = payload.extras.model_dump() if payload.extras else {}

    if payload.p_malicious is not None:
        # Client provided probability
        p_mal = float(payload.p_malicious)
        src: Literal["model", "heuristic", "whitelist"] = "model"
    else:
        # Try model service first
        p_from_svc = _call_model_service(payload.url, extras)
        if p_from_svc is not None:
            p_mal = p_from_svc
            src = "model"
        else:
            # Fallback to heuristic
            p_mal = _heuristic_pmal(payload.url)
            src = "heuristic"

    # PHASE 3: Apply business logic and judge
    outcome = decide_with_judge(payload.url, p_mal, TH, extras=extras)

    return PredictOut(
        url=payload.url,
        p_malicious=p_mal,
        decision=outcome.final_decision,
        reason=outcome.policy_reason,
        thresholds={
            "low": TH["low"],
            "high": TH["high"],
            "t_star": TH["t_star"],
            "gray_zone_rate": TH["gray_zone_rate"],
        },
        judge=(None if outcome.judge is None else outcome.judge.model_dump()),
        source=src,
    )


@app.get("/stats")
def stats():
    return snapshot()


@app.post("/stats/reset")
def stats_reset():
    reset()
    return {"ok": True}


# --------- Explainability endpoints ---------
@app.post("/predict/explain")
def explain(payload: PredictIn):
    """
    Proxy to model service /predict/explain endpoint for SHAP explainability.
    """
    model_url = os.environ.get("MODEL_SVC_URL")
    if not model_url:
        return JSONResponse(
            status_code=503, content={"error": "Model service URL not configured"}
        )

    try:
        # Forward request to model service
        response = requests.post(
            f"{model_url}/predict/explain",
            json={"url": payload.url},
            timeout=10.0,  # SHAP computation can take longer
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            status_code=503, content={"error": f"Model service error: {str(e)}"}
        )


@app.get("/explain")
def explain_dashboard():
    """
    Serve the explainability dashboard HTML page.
    """
    import pathlib

    static_dir = pathlib.Path(__file__).parent / "static"
    html_file = static_dir / "explain.html"

    print(f"[DEBUG] Looking for dashboard at: {html_file.absolute()}")
    print(f"[DEBUG] File exists: {html_file.exists()}")
    print(f"[DEBUG] Static dir: {static_dir.absolute()}")
    print(f"[DEBUG] Static dir exists: {static_dir.exists()}")

    if html_file.exists():
        from fastapi.responses import FileResponse

        return FileResponse(html_file)
    else:
        return JSONResponse(
            status_code=404,
            content={"error": f"Dashboard not found at {html_file.absolute()}"},
        )
