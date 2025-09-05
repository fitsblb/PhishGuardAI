# scripts/ge_build_phiusiil_suite.py
from pathlib import Path

import great_expectations as gx
import pandas as pd

CSV = Path("data/raw/PhiUSIIL_Phishing_URL_Dataset.csv")
OUT_CSV = Path("data/processed/phiusiil_clean.csv")
SUITE_NAME = "phiusiil_minimal"

# 1) Load & deduplicate by exact URL (prevents train/test contamination)
df = pd.read_csv(CSV, encoding_errors="ignore")
dup_total = df.duplicated(subset=["URL"]).sum() if "URL" in df.columns else 0
df = df.drop_duplicates(subset=["URL"]).reset_index(drop=True)
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT_CSV, index=False)

# 2) GE context - initialize project if needed
try:
    # Try to get existing context (if project already initialized)
    ctx = gx.get_context()
    if not hasattr(ctx, "root_directory") or ctx.root_directory is None:
        raise ValueError("No Great Expectations project found")
except (ValueError, gx.exceptions.DataContextError):
    # Initialize a new GE project in the current directory
    print("[GE] No Great Expectations project found. Initializing...")
    ctx = gx.get_context(mode="file")  # Creates file-based context
    print("[GE] Initialized Great Expectations project at: " f"{ctx.root_directory}")

# Create pandas datasource
try:
    datasource = ctx.data_sources.get("phiusiil_src")
except (ValueError, KeyError):
    datasource = ctx.data_sources.add_pandas("phiusiil_src")

# Add dataframe asset
try:
    asset = datasource.get_asset("phiusiil_df")
except (ValueError, KeyError, AttributeError, LookupError):
    asset = datasource.add_dataframe_asset("phiusiil_df")

# Create batch definition for the whole dataframe
try:
    batch_definition = asset.get_batch_definition("phiusiil_batch")
except (ValueError, KeyError, AttributeError, LookupError):
    batch_definition = asset.add_batch_definition_whole_dataframe("phiusiil_batch")

# Create batch parameters with the dataframe
batch_parameters = {"dataframe": df}

# Get the batch
batch = batch_definition.get_batch(batch_parameters=batch_parameters)

# Create or get expectation suite
try:
    suite = ctx.suites.get(SUITE_NAME)
    # Clear existing expectations to rebuild
    suite.expectations = []
except (ValueError, KeyError, gx.exceptions.DataContextError):
    suite = ctx.suites.add(gx.ExpectationSuite(name=SUITE_NAME))

# Get validator using the batch
validator = ctx.get_validator(batch=batch, expectation_suite=suite)


# 3) Expectations grounded in your EDA
def has(col: str) -> bool:
    return col in df.columns


# Label checks
label_col = next(
    (c for c in df.columns if c.lower() in {"label", "result", "y", "target"}),
    "label",
)
validator.expect_column_values_to_not_be_null(label_col)
validator.expect_column_values_to_be_in_set(label_col, [0, 1])

# URL presence & uniqueness (run after dedup)
if has("URL"):
    validator.expect_column_values_to_not_be_null("URL")
    validator.expect_column_values_to_be_unique("URL")

# Probability-like features expected in [0,1]
prob_like_candidates = [
    "CharContinuationRate",
    "URLTitleMatchScore",
    "URLCharProb",
    "TLDLegitimateProb",
]
for c in prob_like_candidates:
    if has(c):
        validator.expect_column_values_to_be_between(c, min_value=0.0, max_value=1.0)

# Binary-like features constrained to {0,1} (exclude the label itself)
for c in df.columns:
    if c == label_col:
        continue
    s = df[c]
    if pd.api.types.is_integer_dtype(s) or pd.api.types.is_bool_dtype(s):
        non_null = s.dropna()
        if not non_null.empty and non_null.isin([0, 1]).all():
            validator.expect_column_values_to_be_in_set(c, [0, 1])

# Non-negative numeric counts/rates (skip those already handled)
numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
skip = set([label_col] + [c for c in prob_like_candidates if has(c)])
for c in numeric_cols:
    if c in skip:
        continue
    if df[c].min() >= 0:
        validator.expect_column_values_to_be_between(c, min_value=0)

# 4) Save suite - just save, don't add since we already have it in context
ctx.suites.add_or_update(validator.expectation_suite)

print(
    f"[GE] Suite '{SUITE_NAME}' created with "
    f"{len(validator.expectation_suite.expectations)} expectations."
)
print(f"[GE] Context root: {getattr(ctx, 'root_directory', 'N/A')}")
print(f"Dropped exact duplicate URLs: {dup_total}")
print(f"Cleaned CSV written → {OUT_CSV}")
