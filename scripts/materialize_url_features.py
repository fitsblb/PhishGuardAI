from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def url_len(s: str) -> int:
    return len(s) if isinstance(s, str) else 0


def digit_ratio(s: str) -> float:
    if not isinstance(s, str) or not s:
        return 0.0
    d = sum(ch.isdigit() for ch in s)
    return d / len(s)


def subdomain_count(s: str) -> int:
    if not isinstance(s, str) or not s:
        return 0
    host = s.split("://", 1)[-1].split("/", 1)[0]
    return max(0, host.count(".") - 1)


def md5_file(p: Path) -> str:
    h = hashlib.md5(
        usedforsecurity=False
    )  # nosec B324 - Used for data fingerprinting, not security
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--infile", type=Path, default=Path("data/processed/phiusiil_clean.csv")
    )
    ap.add_argument(
        "--outfile",
        type=Path,
        default=Path("data/processed/phiusiil_clean_urlfeats.csv"),
    )
    args = ap.parse_args()

    if not args.infile.exists():
        raise FileNotFoundError(f"Input not found: {args.infile}")
    df = pd.read_csv(args.infile, encoding_errors="ignore")
    if "URL" not in df.columns:
        raise ValueError("Expected 'URL' column in processed data")

    # Add/overwrite deterministic URL-only features
    df["url_len"] = df["URL"].map(url_len).astype("int64")
    df["url_digit_ratio"] = df["URL"].map(digit_ratio).astype("float64")
    df["url_subdomains"] = df["URL"].map(subdomain_count).astype("int64")

    # Quick invariants
    if df["url_len"].isna().sum() != 0:
        raise ValueError("url_len contains NaN values")
    if df["url_subdomains"].isna().sum() != 0:
        raise ValueError("url_subdomains contains NaN values")
    if not df["url_digit_ratio"].between(0.0, 1.0, inclusive="both").all():
        raise ValueError("digit_ratio outside [0,1]")
    if not ((df["url_len"] >= 0).all() and (df["url_subdomains"] >= 0).all()):
        raise ValueError("negative length/subdomains?")

    # Write artifact
    args.outfile.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.outfile, index=False)

    # Fingerprint + summary (useful to tag MLflow runs)
    fp = {
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "file": str(args.outfile),
        "md5": md5_file(args.outfile),
        "added_features": ["url_len", "url_digit_ratio", "url_subdomains"],
        "ranges": {
            "url_len": [int(df["url_len"].min()), int(df["url_len"].max())],
            "url_digit_ratio": [
                float(df["url_digit_ratio"].min()),
                float(df["url_digit_ratio"].max()),
            ],
            "url_subdomains": [
                int(df["url_subdomains"].min()),
                int(df["url_subdomains"].max()),
            ],
        },
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/url_features_fingerprint.json").write_text(json.dumps(fp, indent=2))
    print(json.dumps(fp, indent=2))


if __name__ == "__main__":
    main()
