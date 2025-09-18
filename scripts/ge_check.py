"""
Lightweight data contract check for URL-only features.
Fails (exit 1) if required columns are missing or out-of-range.

Run:
  python scripts/ge_check.py
  python scripts/ge_check.py --csv data/processed/phiusiil_clean_urlfeats.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DEF_CSV = "data/processed/phiusiil_clean_urlfeats.csv"
META_PATH = Path("models/dev/model_meta.json")  # for feature_order consistency check

REQUIRED_NUMERIC = {
    "url_len": ("int_like", 0, 8192),  # Increased from 4096 to handle outliers
    "url_digit_ratio": ("float", 0.0, 1.0),
    "url_subdomains": ("int_like", 0, 10),
}
OPTIONAL_BOUNDED = {
    "TLDLegitimateProb": ("float", 0.0, 1.0),
    "SpacialCharRatioInURL": ("float", 0.0, 1.0),
    "CharContinuationRate": ("float", 0.0, 1.0),
    "URLCharProb": ("float", 0.0, 1.0),
}


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"⚠️  {msg}")


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def is_int_like(s: pd.Series) -> bool:
    if pd.api.types.is_integer_dtype(s):
        return True
    if pd.api.types.is_float_dtype(s):  # allow floats with .0
        return np.all(np.isfinite(s)) and np.all(np.equal(np.mod(s, 1), 0))
    return False


def check_range(name: str, s: pd.Series, lo, hi) -> list[str]:
    errs = []
    bad_lo = s < lo
    bad_hi = s > hi
    if bad_lo.any():
        errs.append(f"{name}: {bad_lo.sum()} values < {lo}")
    if bad_hi.any():
        errs.append(f"{name}: {bad_hi.sum()} values > {hi}")
    if (~np.isfinite(s)).any():
        errs.append(f"{name}: {np.sum(~np.isfinite(s))} non-finite values")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv", default=DEF_CSV, help=f"Processed CSV path (default: {DEF_CSV})"
    )
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        fail(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    ok(f"Loaded {csv_path} → shape={df.shape}")

    # 1) Required columns present
    missing = [c for c in REQUIRED_NUMERIC if c not in df.columns]
    if missing:
        fail(f"Missing required columns: {missing}")
    ok("Required columns present")

    # 2) Dtype & range checks
    errors: list[str] = []
    for col, (kind, lo, hi) in REQUIRED_NUMERIC.items():
        s = df[col]
        if kind == "int_like" and not is_int_like(s):
            errors.append(f"{col}: expected integer-like dtype")
        if kind == "float" and not pd.api.types.is_numeric_dtype(s):
            errors.append(f"{col}: expected numeric dtype")
        errors.extend(check_range(col, pd.to_numeric(s, errors="coerce"), lo, hi))
        if s.isna().any():
            errors.append(f"{col}: {s.isna().sum()} nulls")
    ok("Basic dtype/range checks computed")

    # 3) Optional bounded features (if present)
    for col, (_, lo, hi) in OPTIONAL_BOUNDED.items():
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            errors.extend(check_range(col, s, lo, hi))
    ok("Optional bounded columns validated (if present)")

    # 4) No duplicate rows by URL-like keys if URL column exists
    for key in ("URL", "url"):
        if key in df.columns:
            dups = df.duplicated(subset=[key]).sum()
            if dups:
                warn(f"Found {dups} duplicate URLs based on column '{key}'")

    # 5) Feature order compatibility with model metadata (if present)
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        feat_order = meta.get("feature_order") or []
        if feat_order:
            missing_for_model = [c for c in feat_order if c not in df.columns]
            if missing_for_model:
                errors.append(
                    f"Model feature_order missing in CSV: {missing_for_model}"
                )
            else:
                ok("CSV covers model feature_order")

    # 6) Summarize & exit
    if errors:
        print("\n---- Violations ----")
        for e in errors:
            print(f" - {e}")
        fail(f"{len(errors)} violation(s) found")
    ok("Data contract PASSED")


if __name__ == "__main__":
    main()
