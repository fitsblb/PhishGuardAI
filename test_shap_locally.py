"""
Quick test to verify SHAP works with our CalibratedClassifierCV model
"""

import joblib
import pandas as pd
import shap

# Load the model
model = joblib.load("models/dev/model_8feat.pkl")
print(f"Model type: {type(model)}")

# Create sample features (phishing URL features)
features_df = pd.DataFrame(
    [
        {
            "IsHTTPS": 0.0,
            "TLDLegitimateProb": 0.017663043478260868,
            "CharContinuationRate": 0.05714285714285714,
            "SpacialCharRatioInURL": 0.19444444444444445,
            "URLCharProb": 1.0,
            "LetterRatioInURL": 0.6666666666666666,
            "NoOfOtherSpecialCharsInURL": 7.0,
            "DomainLength": 23.0,
        }
    ]
)

print(f"\nFeatures shape: {features_df.shape}")
print(f"Features:\n{features_df}")

# Test prediction
pred = model.predict_proba(features_df)
print(f"\nPrediction: {pred}")
print(f"Phishing probability: {pred[0][0]}")

# Test SHAP TreeExplainer
print("\n" + "=" * 60)
print("Testing SHAP TreeExplainer...")
print("=" * 60)
try:
    # Access the base estimator from CalibratedClassifierCV
    base_estimator = model.calibrated_classifiers_[0].estimator
    print(f"Base estimator type: {type(base_estimator)}")

    explainer = shap.TreeExplainer(base_estimator)
    shap_values = explainer.shap_values(features_df)

    print(f"SHAP values type: {type(shap_values)}")
    print(f"SHAP values: {shap_values}")

    # For binary classification, shap_values might be a list [neg, pos]
    if isinstance(shap_values, list):
        print(f"SHAP values is a list with {len(shap_values)} elements")
        shap_values_phish = shap_values[0]  # Index 0 for phishing class
    else:
        shap_values_phish = shap_values

    print(f"SHAP values for phishing class: {shap_values_phish}")

    contributions = dict(zip(features_df.columns, shap_values_phish[0]))
    print("\nFeature contributions:")
    for feat, contrib in sorted(
        contributions.items(), key=lambda x: abs(x[1]), reverse=True
    ):
        print(f"  {feat:35s}: {contrib:+.6f}")

    print("\n✓ TreeExplainer SUCCESS!")

except Exception as e:
    print(f"\n✗ TreeExplainer FAILED: {e}")
    import traceback

    traceback.print_exc()

    # Try KernelExplainer fallback
    print("\n" + "=" * 60)
    print("Testing SHAP KernelExplainer (fallback)...")
    print("=" * 60)
    try:

        def model_predict(X):
            return model.predict_proba(X)[:, 0]  # Phishing class

        explainer = shap.KernelExplainer(model_predict, features_df)
        shap_values = explainer.shap_values(features_df, nsamples=100)

        contributions = dict(zip(features_df.columns, shap_values[0]))
        print("\nFeature contributions:")
        for feat, contrib in sorted(
            contributions.items(), key=lambda x: abs(x[1]), reverse=True
        ):
            print(f"  {feat:35s}: {contrib:+.6f}")

        print("\n✓ KernelExplainer SUCCESS!")

    except Exception as ke:
        print(f"\n✗ KernelExplainer FAILED: {ke}")
        import traceback

        traceback.print_exc()
