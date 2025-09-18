from typing import Annotated, Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

JudgeVerdict = Literal["LEAN_LEGIT", "LEAN_PHISH", "UNCERTAIN"]


class FeatureDigest(BaseModel):
    # compact, URL-only signals we pass to the judge
    url_len: int = Field(..., ge=0)
    url_digit_ratio: float = Field(..., ge=0.0, le=1.0)
    url_subdomains: int = Field(..., ge=0)
    TLDLegitimateProb: Optional[float] = Field(None, ge=0.0, le=1.0)
    # optional extras (keep small and explicit)
    NoOfOtherSpecialCharsInURL: Optional[int] = Field(None, ge=0)
    SpacialCharRatioInURL: Optional[float] = Field(None, ge=0.0, le=1.0)
    CharContinuationRate: Optional[float] = Field(None, ge=0.0, le=1.0)
    URLCharProb: Optional[float] = Field(None, ge=0.0, le=1.0)


class JudgeRequest(BaseModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    features: FeatureDigest


class JudgeResponse(BaseModel):
    verdict: JudgeVerdict
    rationale: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]
    # optional score in [0,1] reflecting judged risk (not the model score)
    judge_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    # echo minimal context for audit
    context: Dict[str, Any] = Field(default_factory=dict)
