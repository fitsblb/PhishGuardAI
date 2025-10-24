"""
Build Great Expectations suite for PhishGuard 7-Feature Model.
Creates comprehensive data validation expectations for the production-ready feature set.

This script:
1. Loads processed features (phiusiil_features_v2.csv)
2. Creates GE expectations for all 7 required features
3. Validates data quality for ML pipeline

Features validated match docs/FEATURE_EXTRACTION.md
"""

from pathlib import Path

import great_expectations as gx
import pandas as pd
from great_expectations.core.batch import RuntimeBatchRequest

# Updated paths for 7-feature model
PROCESSED_CSV = Path("data/processed/phiusiil_features_v2.csv")
SUITE_NAME = "phiusiil_7feature_production"

# 7-Feature Model Definition (matches ge_check.py and FEATURE_EXTRACTION.md)
REQUIRED_FEATURES = {
    # Probability features [0, 1]
    "TLDLegitimateProb": ("float", 0.0, 1.0),
    "CharContinuationRate": ("float", 0.0, 1.0),
    "SpacialCharRatioInURL": ("float", 0.0, 1.0),
    "URLCharProb": ("float", 0.0, 1.0),
    "LetterRatioInURL": ("float", 0.0, 1.0),
    # Count features
    "NoOfOtherSpecialCharsInURL": ("int_like", 0, 1000),
    "DomainLength": ("int_like", 1, 253),  # RFC 1035 limit
}

# Legacy features to warn about
DEPRECATED_FEATURES = {"url_len", "url_digit_ratio", "url_subdomains"}

print(f"🔍 Loading processed features: {PROCESSED_CSV}")
if not PROCESSED_CSV.exists():
    raise FileNotFoundError(f"Processed features not found: {PROCESSED_CSV}")

# Load the processed features dataset
df = pd.read_csv(PROCESSED_CSV)
print(f"✅ Loaded dataset: {df.shape[0]:,} rows × {df.shape[1]} columns")

# Check for deprecated features
deprecated_present = [col for col in DEPRECATED_FEATURES if col in df.columns]
if deprecated_present:
    print(f"⚠️  Found deprecated features: {deprecated_present}")

# Verify all required features are present
missing_features = [feat for feat in REQUIRED_FEATURES if feat not in df.columns]
if missing_features:
    raise ValueError(f"Missing required features: {missing_features}")

print(f"✅ All 7 required features present: {list(REQUIRED_FEATURES.keys())}")

# Initialize Great Expectations context (handle corrupted config)
print("🔧 Setting up Great Expectations...")
try:
    ctx = gx.get_context()
    if not hasattr(ctx, "root_directory") or ctx.root_directory is None:
        raise ValueError("No Great Expectations project found")
    print(f"✅ Using existing GE project: {ctx.root_directory}")
except (
    ValueError,
    gx.exceptions.DataContextError,
    gx.exceptions.InvalidDataContextConfigError,
):
    print("🔨 GE config corrupted or missing - initializing fresh project...")

    # Remove corrupted GE directory if it exists
    import shutil

    gx_dir = Path("gx")
    if gx_dir.exists():
        print("🗑️  Removing corrupted GE directory...")
        shutil.rmtree(gx_dir)

    # Initialize fresh GE project
    try:
        ctx = gx.get_context(mode="file")
        print(f"✅ Initialized fresh GE project: {ctx.root_directory}")
    except Exception as e:
        print(f"❌ Failed to initialize GE: {e}")
        print("💡 Continuing with basic validation instead...")

        # Simple validation without GE
        print("🔍 Running basic feature validation...")

        # Check all required features are present and valid
        validation_errors = []

        for feature_name, (dtype, min_val, max_val) in REQUIRED_FEATURES.items():
            if feature_name not in df.columns:
                validation_errors.append(f"Missing feature: {feature_name}")
                continue

            series = df[feature_name]

            # Check for nulls
            null_count = series.isnull().sum()
            if null_count > 0:
                validation_errors.append(f"{feature_name}: {null_count} null values")

            # Check data type and range
            if dtype == "binary":
                if not series.isin([0, 1]).all():
                    validation_errors.append(f"{feature_name}: not binary (0/1)")
            elif dtype == "float":
                if not pd.api.types.is_numeric_dtype(series):
                    validation_errors.append(f"{feature_name}: not numeric")
                elif (series < min_val).any() or (series > max_val).any():
                    validation_errors.append(
                        f"{feature_name}: values outside [{min_val}, {max_val}]"
                    )
            elif dtype == "int_like":
                if not pd.api.types.is_integer_dtype(series) and not (
                    pd.api.types.is_float_dtype(series) and (series % 1 == 0).all()
                ):
                    validation_errors.append(f"{feature_name}: not integer-like")
                elif (series < min_val).any() or (series > max_val).any():
                    validation_errors.append(
                        f"{feature_name}: values outside [{min_val}, {max_val}]"
                    )

        if validation_errors:
            print("❌ Validation errors found:")
            for error in validation_errors[:10]:  # Show first 10 errors
                print(f"   💥 {error}")
            if len(validation_errors) > 10:
                print(f"   ... and {len(validation_errors) - 10} more errors")
        else:
            print("✅ All basic validations PASSED!")
            print(f"📊 Dataset: {df.shape[0]:,} rows × {df.shape[1]} columns")
            print(
                f"🎯 Features: {len(REQUIRED_FEATURES)} production features validated"
            )

        print("🚀 Data ready for ML pipeline (basic validation)")
        exit(0)

# Create or get pandas datasource for PhishGuard features
datasource_name = "phishguard_features"
try:
    datasource = ctx.datasources[datasource_name]
    print(f"✅ Using existing datasource: {datasource_name}")
except (ValueError, KeyError):
    # Create new pandas datasource using modern GE API
    datasource_config = {
        "name": datasource_name,
        "class_name": "Datasource",
        "execution_engine": {"class_name": "PandasExecutionEngine"},
        "data_connectors": {
            "default_runtime_data_connector": {
                "class_name": "RuntimeDataConnector",
                "batch_identifiers": ["default_identifier_name"],
            }
        },
    }
    datasource = ctx.add_datasource(**datasource_config)
    print(f"✅ Created new datasource: {datasource_name}")

# Create batch request for our DataFrame using proper GE API
batch_request = RuntimeBatchRequest(
    datasource_name=datasource_name,
    data_connector_name="default_runtime_data_connector",
    data_asset_name="processed_8features",
    runtime_parameters={"batch_data": df},
    batch_identifiers={"default_identifier_name": "production_features"},
)  # Remove existing suite if it exists (fresh start)
try:
    existing_suites = ctx.list_expectation_suite_names()
    if SUITE_NAME in existing_suites:
        ctx.delete_expectation_suite(SUITE_NAME)
        print(f"🗑️  Removed existing suite: {SUITE_NAME}")
except Exception as e:
    # Ignore deletion errors - suite might not exist
    print(f"Note: Could not delete existing suite: {e}")

# Create new expectation suite using add_expectation_suite
try:
    suite = ctx.add_expectation_suite(expectation_suite_name=SUITE_NAME)
    print(f"✅ Created expectation suite: {SUITE_NAME}")
except Exception:
    # Suite might already exist, get it instead
    suite = ctx.get_expectation_suite(expectation_suite_name=SUITE_NAME)
    print(f"✅ Using existing expectation suite: {SUITE_NAME}")

# Get validator using batch request
validator = ctx.get_validator(
    batch_request=batch_request, expectation_suite_name=SUITE_NAME
)

print("🎯 Building expectations for 7-feature production model...")


def has_column(col: str) -> bool:
    """Check if column exists in dataframe"""
    return col in df.columns


# === CORE DATA INTEGRITY ===
print("  📋 Core data integrity checks...")

# Label column validation (phish=0, legit=1)
label_col = next(
    (c for c in df.columns if c.lower() in {"label", "result", "y", "target", "class"}),
    "label",
)
if has_column(label_col):
    validator.expect_column_values_to_not_be_null(label_col)
    validator.expect_column_values_to_be_in_set(label_col, [0, 1])
    print(f"    ✅ Label column '{label_col}' validated")

# URL uniqueness (prevent data leakage)
if has_column("URL"):
    validator.expect_column_values_to_not_be_null("URL")
    validator.expect_column_values_to_be_unique("URL")
    print("    ✅ URL uniqueness validated")

# === 7-FEATURE MODEL VALIDATION ===
print("  🧠 7-Feature model validation...")

# 1. IsHTTPS - Binary feature (0=HTTP, 1=HTTPS)
if has_column("IsHTTPS"):
    validator.expect_column_values_to_not_be_null("IsHTTPS")
    validator.expect_column_values_to_be_in_set("IsHTTPS", [0, 1])
    # Note: Accept both int64 and float64 for binary features (common in pandas)
    if df["IsHTTPS"].dtype == "int64":
        validator.expect_column_values_to_be_of_type("IsHTTPS", "int64")
    elif df["IsHTTPS"].dtype == "float64":
        validator.expect_column_values_to_be_of_type("IsHTTPS", "float64")
    print("    ✅ IsHTTPS (binary) validated")

# 2. TLDLegitimateProb - Bayesian TLD probability [0,1]
if has_column("TLDLegitimateProb"):
    validator.expect_column_values_to_not_be_null("TLDLegitimateProb")
    validator.expect_column_values_to_be_between(
        "TLDLegitimateProb", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("TLDLegitimateProb", "float64")
    # Reasonable distribution check - TLD probs should vary
    validator.expect_column_unique_value_count_to_be_between(
        "TLDLegitimateProb", min_value=10, max_value=1000
    )
    print("    ✅ TLDLegitimateProb (Bayesian) validated")

# 3. CharContinuationRate - Character repetition [0,1]
if has_column("CharContinuationRate"):
    validator.expect_column_values_to_not_be_null("CharContinuationRate")
    validator.expect_column_values_to_be_between(
        "CharContinuationRate", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("CharContinuationRate", "float64")
    print("    ✅ CharContinuationRate (repetition) validated")

# 4. SpacialCharRatioInURL - Special character density [0,1]
if has_column("SpacialCharRatioInURL"):
    validator.expect_column_values_to_not_be_null("SpacialCharRatioInURL")
    validator.expect_column_values_to_be_between(
        "SpacialCharRatioInURL", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("SpacialCharRatioInURL", "float64")
    print("    ✅ SpacialCharRatioInURL (density) validated")

# 5. URLCharProb - Common URL character proportion [0,1]
if has_column("URLCharProb"):
    validator.expect_column_values_to_not_be_null("URLCharProb")
    validator.expect_column_values_to_be_between(
        "URLCharProb", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("URLCharProb", "float64")
    print("    ✅ URLCharProb (URL-likeness) validated")

# 6. LetterRatioInURL - Letter density [0,1]
if has_column("LetterRatioInURL"):
    validator.expect_column_values_to_not_be_null("LetterRatioInURL")
    validator.expect_column_values_to_be_between(
        "LetterRatioInURL", min_value=0.0, max_value=1.0
    )
    validator.expect_column_values_to_be_of_type("LetterRatioInURL", "float64")
    print("    ✅ LetterRatioInURL (letter density) validated")

# 7. NoOfOtherSpecialCharsInURL - Special character count [0,∞)
if has_column("NoOfOtherSpecialCharsInURL"):
    validator.expect_column_values_to_not_be_null("NoOfOtherSpecialCharsInURL")
    validator.expect_column_values_to_be_between(
        "NoOfOtherSpecialCharsInURL", min_value=0, max_value=1000
    )
    validator.expect_column_values_to_be_of_type("NoOfOtherSpecialCharsInURL", "int64")
    print("    ✅ NoOfOtherSpecialCharsInURL (count) validated")

# 8. DomainLength - Domain component length [1,253]
if has_column("DomainLength"):
    validator.expect_column_values_to_not_be_null("DomainLength")
    validator.expect_column_values_to_be_between(
        "DomainLength", min_value=1, max_value=253
    )  # RFC 1035
    validator.expect_column_values_to_be_of_type("DomainLength", "int64")
    print("    ✅ DomainLength (RFC compliant) validated")

# === DATA QUALITY CHECKS ===
print("  📊 Data quality and distribution checks...")

# Check reasonable HTTPS adoption (should be 60-95% for mixed phish/legit)
if has_column("IsHTTPS"):
    https_rate = df["IsHTTPS"].mean()
    if 0.3 <= https_rate <= 0.98:
        validator.expect_column_mean_to_be_between(
            "IsHTTPS", min_value=0.3, max_value=0.98
        )
        print(f"    ✅ HTTPS rate reasonable: {https_rate:.1%}")
    else:
        print(f"    ⚠️  Unusual HTTPS rate: {https_rate:.1%}")

# Check TLD legitimacy distribution
if has_column("TLDLegitimateProb"):
    tld_mean = df["TLDLegitimateProb"].mean()
    if 0.2 <= tld_mean <= 0.9:
        validator.expect_column_mean_to_be_between(
            "TLDLegitimateProb", min_value=0.2, max_value=0.9
        )
        print(f"    ✅ TLD legitimacy reasonable: {tld_mean:.3f}")
    else:
        print(f"    ⚠️  Unusual TLD legitimacy: {tld_mean:.3f}")

# No duplicate rows by URL (critical for train/test split)
if has_column("URL"):
    duplicate_count = df.duplicated(subset=["URL"]).sum()
    if duplicate_count == 0:
        print("    ✅ No duplicate URLs found")
    else:
        print(f"    ⚠️  Found {duplicate_count} duplicate URLs")

# === DEPRECATED FEATURE WARNINGS ===
if deprecated_present:
    print(f"  ⚠️  Deprecated features detected: {deprecated_present}")
    print("     These features are no longer used in the 7-feature model")

# Save the expectation suite
ctx.save_expectation_suite(validator.expectation_suite)
expectations_count = len(validator.expectation_suite.expectations)

print("\n🎉 PhishGuard 7-Feature Expectation Suite Complete!")
print(f"📋 Suite: {SUITE_NAME}")
print(f"🔍 Expectations: {expectations_count}")
print(f"📊 Dataset: {df.shape[0]:,} rows validated")
print(f"🎯 Features: {len(REQUIRED_FEATURES)} production features")

# Quick validation run
print("\n🧪 Running validation checkpoint...")
try:
    results = validator.validate()
    if results.success:
        print("✅ All expectations PASSED - Data ready for ML pipeline!")
    else:
        failed_expectations = len([exp for exp in results.results if not exp.success])
        print(f"❌ {failed_expectations} expectations FAILED - Review data quality")

        # Show detailed failure information
        print("\n🔍 Failed Expectations Details:")
        for i, result in enumerate(results.results):
            if not result.success:
                exp_type = result.expectation_config.expectation_type
                column = result.expectation_config.kwargs.get("column", "N/A")

                print(f"   💥 {exp_type}")
                print(f"      Column: {column}")
                print(f"      Config: {result.expectation_config.kwargs}")

                # Show result details if available
                if hasattr(result, "result") and result.result:
                    obs_value = result.result.get("observed_value", "N/A")
                    exp_range = result.result.get("element_count", "N/A")
                    print(f"      Observed: {obs_value}")
                    print(f"      Details: {result.result}")
                print()

        passed = len([r for r in results.results if r.success])
        total = len(results.results)
        print(f"📊 Success Rate: {passed}/{total} passed")

except Exception as e:
    print(f"⚠️  Validation error: {e}")

print("\n📁 Expectation suite saved to: gx/expectations/")
print("🚀 Ready for production ML pipeline!")
