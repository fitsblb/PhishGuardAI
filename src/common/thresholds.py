import json
from pathlib import Path
from typing import Literal, TypedDict


class Thresholds(TypedDict):
    t_star: float
    low: float
    high: float
    gray_zone_rate: float


def load_thresholds(path: str | Path) -> Thresholds:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    # Handle both nested and flat threshold file formats
    if "thresholds" in data:
        # Nested format (thresholds_8feat.json, thresholds_7feat.json)
        th = data["thresholds"]
        return {
            "t_star": float(th.get("optimal_threshold", th.get("t_star", 0.35))),
            "low": float(th.get("gray_zone_low", th.get("low", 0.004))),
            "high": float(th.get("gray_zone_high", th.get("high", 0.999))),
            "gray_zone_rate": float(th["gray_zone_rate"]),
        }
    else:
        # Flat format (legacy thresholds.json)
        return {
            "t_star": float(data.get("optimal_threshold", 0.35)),
            "low": float(data.get("gray_zone_low", 0.004)),
            "high": float(data.get("gray_zone_high", 0.999)),
            "gray_zone_rate": float(data["gray_zone_rate"]),
        }


Decision = Literal["ALLOW", "REVIEW", "BLOCK"]


def decide(p_malicious: float, th: Thresholds) -> Decision:
    if p_malicious < th["low"]:
        return "ALLOW"
    if p_malicious >= th["high"]:
        return "BLOCK"
    return "REVIEW"
