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
    th = data["thresholds"]
    return {
        "t_star": float(th["t_star"]),
        "low": float(th["low"]),
        "high": float(th["high"]),
        "gray_zone_rate": float(th["gray_zone_rate"]),
    }


Decision = Literal["ALLOW", "REVIEW", "BLOCK"]


def decide(p_malicious: float, th: Thresholds) -> Decision:
    if p_malicious < th["low"]:
        return "ALLOW"
    if p_malicious >= th["high"]:
        return "BLOCK"
    return "REVIEW"
