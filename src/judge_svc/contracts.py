from typing import Annotated, Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

JudgeVerdict = Literal["LEAN_LEGIT", "LEAN_PHISH", "UNCERTAIN"]


class FeatureDigest(BaseModel):
    # 8-feature model (production features - required)
    IsHTTPS: int = Field(..., ge=0, le=1, description="Binary HTTPS indicator")
    TLDLegitimateProb: float = Field(
        ..., ge=0.0, le=1.0, description="Bayesian TLD legitimacy probability"
    )
    CharContinuationRate: float = Field(
        ..., ge=0.0, le=1.0, description="Character continuation pattern rate"
    )
    SpacialCharRatioInURL: float = Field(
        ..., ge=0.0, le=1.0, description="Special character ratio"
    )
    URLCharProb: float = Field(
        ..., ge=0.0, le=1.0, description="URL character probability"
    )
    LetterRatioInURL: float = Field(
        ..., ge=0.0, le=1.0, description="Letter ratio in URL"
    )
    NoOfOtherSpecialCharsInURL: int = Field(
        ..., ge=0, description="Count of other special characters"
    )
    DomainLength: int = Field(..., ge=0, description="RFC-compliant domain length")

    # Legacy features (optional for backward compatibility)
    url_len: Optional[int] = Field(None, ge=0, description="Legacy: total URL length")
    url_digit_ratio: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Legacy: digit ratio"
    )
    url_subdomains: Optional[int] = Field(
        None, ge=0, description="Legacy: subdomain count"
    )


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
