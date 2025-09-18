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
    source: Literal["model", "heuristic"]


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
    if not model_url:
        return None

    try:
        response = requests.post(f"{model_url}/predict", json={"url": url}, timeout=3.0)
        response.raise_for_status()
        data = response.json()
        p_malicious = data.get("p_malicious")

        # Validate probability is in valid range [0.0, 1.0]
        if p_malicious is None or not isinstance(p_malicious, (int, float)):
            return None
        if not (0.0 <= p_malicious <= 1.0):
            return None

        return float(p_malicious)
    except Exception:
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
    # choose p_malicious (client-provided/model service/heuristic
    # handled upstream in our existing wiring)
    extras = payload.extras.model_dump() if payload.extras else {}
    # prefer client/model; fallback heuristic
    # (gateway-call-model branch already added model call)
    try:
        # if present from earlier branch
        from gateway.main import _call_model_service
    except Exception:
        _call_model_service = None

    if payload.p_malicious is not None:
        p_mal = float(payload.p_malicious)
        src: Literal["model", "heuristic"] = "model"
    elif _call_model_service:
        p_from_svc = _call_model_service(payload.url, extras)
        if p_from_svc is not None:
            p_mal = p_from_svc
            src = "model"
        else:
            p_mal = _heuristic_pmal(payload.url)
            src = "heuristic"
    else:
        p_mal = _heuristic_pmal(payload.url)
        src = "heuristic"

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
