# 🔍 PhishGuardAI Explainability Guide

## Overview

PhishGuardAI uses **SHAP (SHapley Additive exPlanations)** to provide feature-level explanations for phishing predictions. This document explains how to use the SHAP dashboard, interpret results, and understand when explainability is needed.

---

## 🎯 Why Explainability Matters

### Regulatory Compliance
- **GDPR Right to Explanation**: EU regulations require explanation for automated decisions
- **PCI-DSS Audit Trails**: Payment processors need to justify fraud blocks
- **Fair Lending Laws**: Must demonstrate non-discriminatory decision-making

### Business Value
- **Trust Building**: Security teams trust models they can inspect
- **Debugging**: Identify model biases or data quality issues
- **Feature Engineering**: Discover which features actually drive predictions

### User Trust
- **Merchant Confidence**: "Why was my URL blocked?" needs an answer
- **False Positive Investigation**: Understand what triggered the alert
- **Appeal Process**: Provide evidence for overturning decisions

---

## 🚀 Accessing the SHAP Dashboard

### Start the Services
```bash
# Terminal 1: Model service (includes SHAP explainer)
python -m model_svc.main

# Terminal 2: Gateway service (serves dashboard UI)
python -m gateway.main
```

### Open the Dashboard
Navigate to: **`http://localhost:8000/explain`**

---

## 📊 Dashboard Features

### Input Section
- **URL Input Field**: Enter any URL to analyze
- **Analyze Button**: Triggers model prediction + SHAP computation

### Output Sections

#### 1. Malicious Probability
- Large colored box showing prediction
- **Red (Dangerous)**: p ≥ 0.5 (likely phishing)
- **Green (Safe)**: p < 0.5 (likely legitimate)
- **Percentage**: Model's confidence (0.0% to 100.0%)

#### 2. Feature Contributions (SHAP Values)
- **Horizontal bar chart**: Shows each feature's contribution
- **Red bars →**: Features that **increase** phishing probability
- **Green bars ←**: Features that **decrease** phishing probability
- **Bar length**: Magnitude of contribution
- **Numerical value**: Exact SHAP value on the right

#### 3. Extracted Feature Values
- **Grid layout**: Shows raw feature values extracted from the URL
- **Examples**:
  - `IsHTTPS: 1.0000` → URL uses HTTPS
  - `DomainLength: 15.0000` → Domain is 15 characters
  - `TLDLegitimateProb: 0.8792` → TLD (.org) has high legitimacy score

---

## 🧠 Interpreting SHAP Values

### What SHAP Values Mean

**SHAP value = contribution of this feature to the prediction**

- **Positive SHAP value (red)**: This feature pushes the prediction **toward phishing**
- **Negative SHAP value (green)**: This feature pushes the prediction **toward legitimate**
- **Magnitude**: How strong the contribution is

### Mathematical Interpretation

If the model predicts `p_malicious = 0.85` (85% phishing):
- Base rate (average phishing rate in training) ≈ 0.43
- SHAP values sum to explain the difference: 0.85 - 0.43 = +0.42

**Example breakdown:**
```
Feature                    | SHAP Value | Interpretation
---------------------------|------------|----------------------------------
NoOfOtherSpecialChars = 5 | +0.18      | Many special chars increase risk by 18%
DomainLength = 20         | -0.05      | Moderate length decreases risk by 5%
TLDLegitimateProb = 0.62  | +0.08      | Suspicious TLD increases risk by 8%
... (other features)      | ...        | ...
---------------------------|------------|----------------------------------
SUM                       | +0.42      | Total shift from base rate
```

---

## 📝 Example Interpretations

### Example 1: Clear Phishing (facebook1mob.com)

**URL:** `http://facebook1mob.com`  
**Prediction:** 100.0% malicious

**Top SHAP Contributions:**
| Feature | Value | SHAP Value | Interpretation |
|---------|-------|------------|----------------|
| NoOfOtherSpecialCharsInURL | 5.0000 | **+1.76 (red)** | ⚠️ The '1' in "facebook1mob" is typosquatting |
| DomainLength | 20.0000 | **-1.90 (green)** | ✓ Moderate length slightly reduces risk |

**Analysis:**

- Secondary risk: Typosquatting ("facebook1" mimics "facebook")
- Despite moderate domain length, the suspicious patterns dominate
- **Verdict: BLOCK** - Clear phishing attempt

---

### Example 2: Legitimate Domain (circlek.org)

**URL:** `https://www.circlek.org`  
**Prediction:** 0.1% malicious

**Top SHAP Contributions:**
| Feature | Value | SHAP Value | Interpretation |
|---------|-------|------------|----------------|
| CharContinuationRate | 0.1818 | **+3.29 (red)** | ⚠️ "circlek" has repeated 'k' pattern |
| DomainLength | 15.0000 | **-2.57 (green)** | ✓ Moderate length reduces risk |
| NoOfOtherSpecialCharsInURL | 5.0000 | **+2.21 (red)** | ⚠️ Some special chars present |

**Analysis:**
- Despite some red flags (char continuation, special chars), net prediction is safe
- Moderate domain length is strongly protective
- **Verdict: ALLOW** - Overall legitimate despite minor suspicious signals


---

### Example 3: Borderline (githubmemory.com)

**URL:** `https://www.githubmemory.com`  
**Prediction:** 0.3% malicious

**Top SHAP Contributions:**
| Feature | Value | SHAP Value | Interpretation |
|---------|-------|------------|----------------|
| NoOfOtherSpecialCharsInURL | 5.0000 | **+2.73 (red)** | ⚠️ Special characters present |
| CharContinuationRate | 0.1481 | **+1.89 (red)** | ⚠️ Repeated patterns in domain |
| DomainLength | 20.0000 | **-0.79 (green)** | ✓ Moderate length reduces risk |

**Analysis:**
- Competing signals: suspicious patterns vs. legitimate structure
- "githubmemory" might be a legitimate service or copycat site
- Low prediction (0.3%) suggests legitimate, but worth reviewing
- **Verdict: ALLOW** - But borderline case for manual review

---

### Example 4: Whitelisted Domain (github.com/microsoft/vscode)

**URL:** `https://github.com/microsoft/vscode`  
**Prediction:** 1.0% malicious (whitelisted)

**SHAP Output:**
```
No feature contributions available (whitelist match)
```

**Analysis:**
- URL matched whitelist before model was called
- Model never made a prediction → No SHAP values to compute
- **Verdict: ALLOW** - Inherently explainable (it's GitHub)

**Explanation Strategy:**
- **Model-based decisions**: Use SHAP to explain feature contributions
- **Whitelist decisions**: Explain as "known legitimate domain from allowlist"

---

## 🎯 When to Use SHAP Explanations

### Required for:
✅ **Regulatory audits** - Demonstrate non-discriminatory decision-making  
✅ **False positive investigations** - Why was this legitimate URL blocked?  
✅ **Model debugging** - Are features behaving as expected?  
✅ **Merchant appeals** - Provide evidence for overturning BLOCK decisions  
✅ **Security team training** - Teach what patterns indicate phishing

### Not needed for:
❌ **Real-time scanning** - Too slow (100-200ms for SHAP computation)  
❌ **Whitelist decisions** - Already explainable ("it's on the allowlist")  
❌ **High-volume batch processing** - Use judge rationale instead

---

## ⚙️ Technical Implementation

### How SHAP Works

**1. TreeExplainer (XGBoost)**
```python
# Access base estimator from calibrated model
base_estimator = model.calibrated_classifiers_[0].estimator

# Create SHAP explainer
explainer = shap.TreeExplainer(base_estimator)

# Compute SHAP values for input features
shap_values = explainer.shap_values(features_df)
```

**2. Fallback: KernelExplainer**
If TreeExplainer fails (e.g., for non-tree models):
```python
# Model-agnostic explainer (slower but more general)
explainer = shap.KernelExplainer(model_predict, background_data)
shap_values = explainer.shap_values(features_df)
```

### API Endpoint

**Request:**
```bash
POST /predict/explain
{
  "url": "http://example.com"
}
```

**Response:**
```json
{
  "p_malicious": 0.15,
  "source": "model",
  "model_name": "8-feature-production-v1",
  "feature_contributions": {
    "IsHTTPS": -0.05,
    "TLDLegitimateProb": -0.08,
    "CharContinuationRate": +0.02,
    ...
  },
  "feature_values": {
    "IsHTTPS": 1.0,
    "TLDLegitimateProb": 0.8792,
    "CharContinuationRate": 0.1818,
    ...
  }
}
```

### Performance Considerations

| Operation | Latency | Notes |
|-----------|---------|-------|
| Model prediction alone | ~20-30ms | XGBoost inference |
| SHAP computation (TreeExplainer) | ~50-100ms | Tree traversal + Shapley values |
| SHAP computation (KernelExplainer) | ~200-500ms | Model-agnostic (slower) |

**Recommendation**: Use SHAP for on-demand explanations, NOT real-time scanning.

---

## 🔧 Troubleshooting

### Issue: "SHAP explainability failed"

**Symptoms:**
- API returns 500 error
- Error message: "SHAP explainability failed"

**Possible Causes:**
1. Model not loaded correctly
2. Feature extraction failed
3. TreeExplainer incompatible with model architecture

**Solutions:**
```bash
# Check model service logs
# Look for: "✓ Loaded model from models/dev/model_8feat.pkl"

# Verify model metadata
curl http://localhost:9000/health
# Should show: "loaded": true

# Test without SHAP (regular prediction)
curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

### Issue: "No feature contributions available (whitelist match)"

**This is expected behavior!**
- Whitelisted URLs bypass the model
- No model prediction → No SHAP values
- Explainability: "URL is on known legitimate domain allowlist"

---

## 📊 SHAP Dashboard Integration

### File Locations
```
static/
  └─ explain.html          # SHAP dashboard UI (HTML/CSS/JS)
src/model_svc/main.py      # /predict/explain endpoint
src/gateway/main.py        # Serves static files at /explain
```

### Customization

**Change dashboard styling:**
Edit `static/explain.html` CSS section:
```css
.probability-display {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  /* Customize gradient colors */
}
```

**Add new features:**
Modify `/predict/explain` endpoint in `src/model_svc/main.py`:
```python
# Add confidence intervals, alternative explanations, etc.
```

---

## 🎓 Best Practices

### For Security Teams
1. **Review borderline cases** (0.3 < p < 0.7) using SHAP
2. **Validate model assumptions** - Check if SHAP values align with domain knowledge
3. **Document patterns** - Build a library of "typical phishing SHAP profiles"

### For Data Scientists
1. **Sanity check features** - IsHTTPS should usually be protective (green), not risky (red)
2. **Identify feature bugs** - If DomainLength always shows red for long domains, investigate
3. **Calibrate thresholds** - Use SHAP to understand which features drive gray-zone decisions

### For Compliance Officers
1. **Screenshot SHAP explanations** for audit trails
2. **Export SHAP values to CSV** for statistical analysis
3. **Document explanation methodology** in compliance reports

---

## 🚀 Future Enhancements

### Planned Improvements
- **Global feature importance**: Show which features are most influential across ALL predictions
- **Counterfactual explanations**: "If IsHTTPS was 1 instead of 0, decision would change to ALLOW"
- **LIME integration**: Alternative explanation method for comparison
- **Interactive plots**: Click on features to see detailed breakdowns
- **Export functionality**: Download SHAP plots as PNG/SVG for reports

---

## 📚 Additional Resources

- **SHAP Documentation**: https://shap.readthedocs.io/
- **Original Paper**: Lundberg, S. M., & Lee, S. I. (2017). "A unified approach to interpreting model predictions." NIPS.
- **TreeExplainer Paper**: Lundberg, S. M., et al. (2020). "From local explanations to global understanding with explainable AI for trees." Nature Machine Intelligence.

---

## 📧 Questions?

For questions about SHAP integration or explainability best practices, contact:
- **Fitsum Gebrezghiabihier** - [fitsumbahbi@gmail.com](mailto:fitsumbahbi@gmail.com)

---

**Remember**: Explainability is not just a technical feature—it's a business requirement for trust, compliance, and operational maturity in fraud detection systems.
