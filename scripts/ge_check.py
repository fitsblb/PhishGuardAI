"""
Lightweight data contract check for PhishGuard 8-feature model.
Validates the 8 features documented in docs/FEATURE_EXTRACTION.md
Fails (exit 1) if required columns are missing or out-of-range.

Run:
  python scripts/ge_check.py
  python scripts/ge_check.py --csv data/processed/phiusiil_final_features.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DEF_CSV = "data/processed/phiusiil_features_v2.csv"
META_PATH = Path("models/dev/model_8feat_meta.json")  # Updated to 8-feature model

# 8-Feature Model: All features are required for production model
REQUIRED_FEATURES = {
    # Binary features
    "IsHTTPS": ("binary", 0, 1),
    # Probability features [0, 1]
    "TLDLegitimateProb": ("float", 0.0, 1.0),
    "CharContinuationRate": ("float", 0.0, 1.0),
    "SpacialCharRatioInURL": ("float", 0.0, 1.0),
    "URLCharProb": ("float", 0.0, 1.0),
    "LetterRatioInURL": ("float", 0.0, 1.0),
    # Count features
    "NoOfOtherSpecialCharsInURL": ("int_like", 0, 1000),  # Reasonable upper bound
    "DomainLength": ("int_like", 1, 253),  # RFC 1035 domain length limit
}

# Legacy features no longer used (for backward compatibility warnings)
DEPRECATED_FEATURES = {"url_len", "url_digit_ratio", "url_subdomains"}


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"⚠️  {msg}")


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def is_binary(s: pd.Series) -> bool:
    """Check if series contains only 0s and 1s"""
    if pd.api.types.is_integer_dtype(s):
        return s.isin([0, 1]).all()
    if pd.api.types.is_float_dtype(s):
        return s.isin([0.0, 1.0]).all()
    return False


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

    # 1) Required columns present (all 8 features must be present)
    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
    if missing:
        fail(f"Missing required features: {missing}")
    ok("All 8 required features present")

    # 2) Check for deprecated features (warn only)
    deprecated_present = [c for c in DEPRECATED_FEATURES if c in df.columns]
    if deprecated_present:
        warn(f"Found deprecated features (no longer used): {deprecated_present}")

    # 3) Dtype & range checks for each feature
    errors: list[str] = []
    for col, (kind, lo, hi) in REQUIRED_FEATURES.items():
        s = df[col]

        # Type validation
        if kind == "binary" and not is_binary(s):
            errors.append(
                f"{col}: expected binary (0/1) values, got: {s.unique()[:10]}"
            )
        elif kind == "int_like" and not is_int_like(s):
            errors.append(f"{col}: expected integer-like dtype")
        elif kind == "float" and not pd.api.types.is_numeric_dtype(s):
            errors.append(f"{col}: expected numeric dtype")

        # Range validation
        errors.extend(check_range(col, pd.to_numeric(s, errors="coerce"), lo, hi))

        # Null check
        if s.isna().any():
            errors.append(f"{col}: {s.isna().sum()} null values (not allowed)")

    ok("Feature type and range checks completed")

    # 4) No duplicate rows by URL-like keys if URL column exists
    for key in ("URL", "url"):
        if key in df.columns:
            dups = df.duplicated(subset=[key]).sum()
            if dups:
                warn(f"Found {dups} duplicate URLs based on column '{key}'")

    # 5) Feature order compatibility with 8-feature model metadata
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        feat_order = meta.get("feature_order") or []
        if feat_order:
            missing_for_model = [c for c in feat_order if c not in df.columns]
            if missing_for_model:
                errors.append(
                    f"8-feature model requires missing columns: {missing_for_model}"
                )
            else:
                ok("CSV matches 8-feature model requirements")

            # Check feature order matches exactly
            required_feat = list(REQUIRED_FEATURES.keys())
            if feat_order != required_feat:
                warn(
                    f"Feature order mismatch - Model: {feat_order}, "
                    f"Script: {required_feat}"
                )
    else:
        warn(f"Model metadata not found: {META_PATH}")

    # 6) Data quality checks
    total_rows = len(df)
    if total_rows == 0:
        errors.append("Dataset is empty")
    else:
        ok(f"Dataset contains {total_rows:,} rows")

        # Check for reasonable feature distributions
        if "IsHTTPS" in df.columns:
            https_rate = df["IsHTTPS"].mean()
            if https_rate < 0.3 or https_rate > 0.98:
                warn(f"Unusual HTTPS rate: {https_rate:.3f} (expected ~0.6-0.95)")

        if "TLDLegitimateProb" in df.columns:
            tld_mean = df["TLDLegitimateProb"].mean()
            if tld_mean < 0.2 or tld_mean > 0.9:
                warn(f"Unusual TLD legitimacy mean: {tld_mean:.3f} (expected ~0.4-0.8)")

    # 7) Summarize & exit
    if errors:
        print("\n---- VIOLATIONS ----")
        for e in errors:
            print(f" ❌ {e}")
        fail(f"{len(errors)} violation(s) found")

    print("\n✅ PhishGuard 8-Feature Data Contract PASSED")
    print(f"✅ All {len(REQUIRED_FEATURES)} features validated")
    print(f"✅ {total_rows:,} rows ready for model training/inference")


if __name__ == "__main__":
    main()
