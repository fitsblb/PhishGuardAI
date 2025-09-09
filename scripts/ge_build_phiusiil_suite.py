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
    print(f"[GE] Initialized Great Expectations project at: {ctx.root_directory}")

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
    ctx.suites.delete(SUITE_NAME)
except Exception:  # nosec B110
    # Suite doesn't exist, which is fine
    pass
suite = ctx.suites.add(gx.ExpectationSuite(name=SUITE_NAME))

# Get validator using the batch
validator = ctx.get_validator(batch=batch, expectation_suite=suite)

# 3) Expectations grounded in your EDA
# --- GE hardening derived from URL-only policy ---


def has(col: str) -> bool:
    return col in df.columns


# 1) Core invariants
label_col = next(
    (c for c in df.columns if c.lower() in {"label", "result", "y", "target"}), "label"
)
validator.expect_column_values_to_not_be_null(label_col)
validator.expect_column_values_to_be_in_set(label_col, [0, 1])

if has("URL"):
    validator.expect_column_values_to_not_be_null("URL")
    validator.expect_column_values_to_be_unique("URL")

# 2) URL-only engineered features (ranges/dtypes)
if has("url_len"):
    validator.expect_column_values_to_be_between("url_len", min_value=0)
    validator.expect_column_values_to_be_of_type("url_len", "int64")

if has("url_subdomains"):
    validator.expect_column_values_to_be_between("url_subdomains", min_value=0)
    validator.expect_column_values_to_be_of_type("url_subdomains", "int64")

if has("url_digit_ratio"):
    validator.expect_column_values_to_be_between(
        "url_digit_ratio", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("url_digit_ratio", "float64")

# 3) Probability-like URL priors (must be in [0,1])
for c in ["CharContinuationRate", "URLCharProb", "TLDLegitimateProb"]:
    if has(c):
        validator.expect_column_values_to_be_between(c, min_value=0.0, max_value=1.0)

# 4) Keep page-source strings as strings (so they never sneak in numerically)
for c in ["Domain", "TLD", "Title"]:
    if has(c):
        validator.expect_column_values_to_be_of_type(c, "object")

# 5) Optional: boolean flags constrained to {0,1} (skip label itself)
for c in df.select_dtypes(include=["int64", "bool"]).columns:
    if c != label_col and df[c].dropna().isin([0, 1]).all():
        validator.expect_column_values_to_be_in_set(c, [0, 1])

# Save suite
ctx.suites.add_or_update(validator.expectation_suite)
expectations_count = len(validator.expectation_suite.expectations)
print(f"[GE] Hardened suite saved with {expectations_count} expectations.")
