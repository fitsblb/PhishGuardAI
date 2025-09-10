from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

# Imports match our editable-install (src-layout) packaging
from common.thresholds import Thresholds, load_thresholds
from gateway.judge_wire import decide_with_judge

app = FastAPI(title="PhishGuard Gateway")

# --------- thresholds (loaded once at startup) ---------
THRESH_PATH = os.getenv("THRESHOLDS_JSON", "configs/dev/thresholds.json")
try:
    TH: Thresholds = load_thresholds(THRESH_PATH)
except Exception as e:
    # Fail early and loudly; the service depends on thresholds to make decisions
    raise RuntimeError(f"Failed to load thresholds from {THRESH_PATH}: {e}")


# --------- request/response models ---------
class ExtrasIn(BaseModel):
    # Optional URL-only features to pass to the judge (all optional for convenience)
    TLDLegitimateProb: Optional[float] = Field(None, ge=0.0, le=1.0)
    NoOfOtherSpecialCharsInURL: Optional[int] = Field(None, ge=0)
    SpacialCharRatioInURL: Optional[float] = Field(None, ge=0.0, le=1.0)
    CharContinuationRate: Optional[float] = Field(None, ge=0.0, le=1.0)
    URLCharProb: Optional[float] = Field(None, ge=0.0, le=1.0)


class PredictIn(BaseModel):
    url: str = Field(..., min_length=3)
    # If provided, we’ll trust this probability from the model service (P(phish))
    p_malicious: Optional[float] = Field(None, ge=0.0, le=1.0)
    # Optional extras passed to judge (only used if policy says REVIEW)
    extras: Optional[ExtrasIn] = None


class PredictOut(BaseModel):
    url: str
    p_malicious: float
    decision: Literal["ALLOW", "REVIEW", "BLOCK"]
    reason: str
    thresholds: Dict[str, float]
    judge: Optional[Dict[str, Any]] = None
    source: Literal["model", "heuristic"]  # where p_malicious came from


# --------- tiny deterministic URL feature helpers (match training utils) ---------
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
    """
    Fallback ONLY for local demos when p_malicious is not provided.
    This is NOT your trained model — just a transparent, bounded heuristic.
    """
    risk = 0.0
    # length
    L = _url_len(url)
    if L >= 160:
        risk += 0.50
    elif L >= 100:
        risk += 0.35
    elif L >= 80:
        risk += 0.20
    # digits
    dr = _digit_ratio(url)
    if dr >= 0.30:
        risk += 0.35
    elif dr >= 0.20:
        risk += 0.20
    elif dr >= 0.10:
        risk += 0.10
    # subdomains
    sd = _subdomain_count(url)
    if sd >= 4:
        risk += 0.20
    elif sd >= 3:
        risk += 0.10
    # light token check
    url_l = url.lower()
    if any(tok in url_l for tok in ["login", "verify", "update", "secure", "account"]):
        risk += 0.10
    return max(0.0, min(1.0, risk))


# --------- routes ---------
@app.get("/health")
def health():
    # Later: add readiness checks (e.g., downstream pings)
    return {"status": "ok", "service": "gateway", "version": "0.0.1"}


@app.get("/config")
def config():
    return {"thresholds": TH, "thresholds_path": THRESH_PATH}


@app.post("/predict", response_model=PredictOut)
def predict(payload: PredictIn):
    # 1) choose p_malicious (prefer model-supplied; otherwise heuristic)
    if payload.p_malicious is not None:
        p_mal = float(payload.p_malicious)
        src = "model"
    else:
        p_mal = _heuristic_pmal(payload.url)
        src = "heuristic"

    # 2) extras for judge (optional)
    extras = payload.extras.model_dump() if payload.extras else {}

    # 3) policy band → maybe judge → final decision
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
