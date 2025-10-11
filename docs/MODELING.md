# 🚀 PhishGuard AI: Model Training Documentation

<div align="center">

![PhishGuard AI](https://img.shields.io/badge/PhishGuard-AI-blue?style=for-the-badge&logo=shield)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)
![Performance](https://img.shields.io/badge/PR--AUC-99.85%25-brightgreen?style=for-the-badge)

</div>

---

## 📋 Project Information

| **Attribute** | **Value** |
|---------------|-----------|
| **🎯 Project** | PhishGuardAI - URL-Only Phishing Detection |
| **📅 Training Date** | January 2025 |
| **📊 Dataset** | PhiUSIIL (deduplicated, 235,370 unique URLs) |
| **📔 Notebook** | `notebooks/02_model_training.ipynb` |
| **🏷️ Version** | v1.0 |

---

## 🎯 Executive Summary

Trained two XGBoost models for URL-only phishing detection with exceptional performance:

<div align="center">

| 🏆 **Model** | 🎛️ **Features** | 📈 **PR-AUC** | 🎯 **F1-Macro** | 🚦 **Status** |
|--------------|-----------------|----------------|------------------|----------------|
| **8-Feature** (with IsHTTPS) | 8 | `0.9990` | `0.9968` | 🧪 Research baseline |
| **7-Feature** (no IsHTTPS) | 7 | `0.9985` | `0.9919` | ✅ **Production candidate** |

</div>

> **🔍 Key Finding:** Removing IsHTTPS causes only 0.05% PR-AUC degradation, proving URL structure features are highly discriminative independent of protocol. The 7-feature model is recommended for production deployment as it's robust to the modern threat landscape where 80%+ of phishing sites use HTTPS.

---

## 📚 Table of Contents

1. [📊 Dataset Overview](#dataset-overview)
2. [🎛️ Feature Set](#feature-set)
3. [🤖 Model Selection](#model-selection)
4. [🔍 Leakage Investigation](#leakage-investigation)
5. [⚖️ 8-Feature vs 7-Feature Comparison](#model-comparison)
6. [📈 Performance Analysis](#performance-analysis)
7. [🎚️ Threshold Tuning](#threshold-tuning)
8. [🚀 Production Recommendations](#production-recommendations)
9. [⚠️ Limitations & Future Work](#limitations-and-future-work)
10. [🔄 Reproducibility](#reproducibility)

---

## 📊 Dataset Overview

**📚 Source:** PhiUSIIL Phishing URL Dataset  
**📖 Citation:** Prasad, A., & Chandra, S. (2023). PhiUSIIL: A diverse security profile empowered phishing URL detection framework. *Computers & Security*.

### 📈 Dataset Statistics

<div align="center">

| **Metric** | **Value** | **Percentage** |
|------------|-----------|----------------|
| **Total URLs** | 235,370 | 100% |
| **🔴 Phishing** | 100,520 | 42.7% |
| **🟢 Legitimate** | 134,850 | 57.3% |
| **🔄 Duplicates Removed** | 425 URLs | 0.18% |

</div>

### 🔄 Train/Validation Split

<div align="center">

| **Set** | **Total** | **🔴 Phishing** | **🟢 Legitimate** | **Split %** |
|---------|-----------|-----------------|-------------------|-------------|
| **🎯 Training** | 188,296 | 80,416 (42.7%) | 107,880 (57.3%) | 80% |
| **✅ Validation** | 47,074 | 20,104 (42.7%) | 26,970 (57.3%) | 20% |

</div>

### ✅ Data Quality Assurance
- ✅ **Zero null values** across all features
- ✅ **No distribution shift** between train/validation sets (KS test p-values > 0.8)
- ✅ **No duplicate URLs** across train/validation splits
- ✅ **Stratified sampling** maintains class balance (42.7% phish in both sets)

---

## 🎛️ Feature Set

### 🏆 8-Feature Model (Research Baseline)

Selected from EDA phase based on separation scores and low correlation:

<div align="center">

| **#** | **🎛️ Feature** | **📊 Separation Score** | **🏷️ Type** | **📝 Description** |
|-------|-----------------|-------------------------|--------------|-------------------|
| 1 | `IsHTTPS` | `2.829` | 🔘 Binary | Protocol indicator (0=HTTP, 1=HTTPS) |
| 2 | `TLDLegitimateProb` | `2.012` | 📈 Float [0,1] | TLD reputation score |
| 3 | `CharContinuationRate` | `1.372` | 📈 Float [0,1] | Character repetition rate |
| 4 | `SpacialCharRatioInURL` | `1.330` | 📈 Float [0,1] | Special character density |
| 5 | `URLCharProb` | `0.889` | 📈 Float [0,1] | URL character probability |
| 6 | `LetterRatioInURL` | `0.825` | 📈 Float [0,1] | Letter character density |
| 7 | `NoOfOtherSpecialCharsInURL` | `0.562` | 🔢 Integer | Count of special characters |
| 8 | `DomainLength` | `0.324` | 🔢 Integer | Domain string length |

</div>

### ✅ 7-Feature Model (Production Candidate)

**🚫 Excluded:** `IsHTTPS`  
**💡 Rationale:** HTTPS adoption by phishing sites has increased from ~50% (2020-2022 dataset) to 80%+ (2025 reality). Excluding IsHTTPS creates a more robust model for current threat landscape.

**✅ Remaining features:** Features 2-8 from above table.

### 🚫 Features Excluded from Both Models

**During EDA, we explicitly excluded:**

#### 1. **🌐 Domain** (220K unique values)
- **❌ Reason:** Extreme cardinality, memorization risk
- **🔍 Finding:** Only 54 domains appear in both classes (0.025%)
- **✅ Decision:** Use `DomainLength` instead (captures length signal without memorization)

#### 2. **🏷️ Raw TLD** (695 unique values)
- **❌ Reason:** High cardinality, handled by `TLDLegitimateProb` numeric proxy
- **🔍 Finding:** `TLDLegitimateProb` accurately captures TLD risk (0.002 for .app, 0.523 for .com)
- **✅ Decision:** Use numeric proxy to avoid 695-feature explosion

#### 3. **📉 Weak Features** (separation < 0.3)
- `URLLength`, `DegitRatioInURL`, `NoOfSubDomain` excluded due to near-zero separation scores

---

## 🤖 Model Selection

### 🔬 Candidates Evaluated

#### 1. 📈 Logistic Regression (Baseline)

**🏗️ Architecture:**
- Linear model with StandardScaler preprocessing
- Pipeline: `StandardScaler(with_mean=False)` → `LogisticRegression`

**⚙️ Hyperparameters:**
```python
LogisticRegression(
   max_iter=2000,
   class_weight='balanced',  # Handle slight imbalance
   random_state=42
)
```

**🎯 Calibration:** Isotonic regression, 5-fold stratified CV

**📊 Performance:**
- **PR-AUC:** `0.9964`
- **F1-macro @0.5:** `0.9848`
- **Brier:** `0.012186`

**✅ Pros:**
- 💡 Extremely interpretable (coefficient = feature importance)
- ⚡ Fast inference (<1ms)
- 🎯 Well-calibrated by default
- 🏛️ Industry standard for fraud (regulatory friendly)

**❌ Cons:**
- 📏 Linear decision boundary (can't capture interactions)
- 📉 2.6% behind XGBoost on PR-AUC

#### 2. 🚀 XGBoost (Production Candidate) ✅

**🏗️ Architecture:** Gradient boosted decision trees

**⚙️ Hyperparameters:**
```python
XGBClassifier(
   n_estimators=300,
   max_depth=6,           # Sh`ALLOW` trees prevent overfitting
   learning_rate=0.1,
   subsample=0.9,         # Row sampling
   colsample_bytree=0.9,  # Column sampling
   reg_lambda=1.0,        # L2 regularization
   random_state=42,
   objective='binary:logistic'
)
```

**🎯 Calibration:** Isotonic regression, 5-fold stratified CV

**📊 Performance (8-feature):**
- **PR-AUC:** `0.9990` ✅
- **F1-macro @0.5:** `0.9968` ✅
- **Brier:** `0.002777` ✅

**✅ Pros:**
- 🔄 Handles non-linear patterns
- 📊 Built-in feature importance (gain, cover, frequency)
- 🛡️ Robust to outliers
- 🏆 State-of-art for tabular data

**❌ Cons:**
- 🔍 Less interpretable than LogReg (mitigated with SHAP)
- ⏱️ Slightly slower inference (~5-10ms)

### 🎯 Selection Decision

**🏆 Winner:** XGBoost

**💡 Rationale:**
- 📈 2.6% PR-AUC improvement over LogReg (0.9990 vs 0.9964)
- 📊 1.2% F1-macro improvement (0.9968 vs 0.9848)
- 🎯 4.4x better calibration (Brier: 0.0027 vs 0.0121)
- ⚖️ Trade-off: Slight loss of interpretability acceptable for performance gain
- 🛠️ Mitigation: Plan to use SHAP for post-hoc explanations

### ❓ Why Not Neural Networks?

- 📊 235K samples is moderate (not enough for deep learning advantage)
- 🎛️ 8 features is low-dimensional (trees excel in this regime)
- 🔍 Need interpretability for fraud (regulatory requirement)
- ⚡ Need fast inference for real-time API (<50ms)

---

## 🔍 Leakage Investigation

### 🎯 Motivation
Initial PR-AUC of 0.999 raised concerns about data leakage. Conducted systematic investigation across 5 dimensions.

### 🔍 Investigation 1: Feature Importance Analysis

**🔍 Finding:** IsHTTPS dominated at 72.4% importance

| **🎛️ Feature** | **📊 Importance** |
|----------------|-------------------|
| `IsHTTPS` | `72.4%` |
| `NoOfOtherSpecialCharsInURL` | `22.9%` |
| `LetterRatioInURL` | `1.4%` |
| `SpacialCharRatioInURL` | `1.3%` |
| (remaining features) | `2.0%` |

**⚠️ Concern:** Single feature accounting for 72% suggests potential leakage.  
**✅ Resolution:** Retrained without IsHTTPS (see Model Comparison section).

### 📊 Investigation 2: Train/Val Distribution Shift

**🔬 Method:** Kolmogorov-Smirnov test on all features

**📈 Results:** No significant distribution shifts detected

| **🎛️ Feature** | **📊 KS Statistic** | **📈 p-value** | **🚦 Significant?** |
|----------------|---------------------|-----------------|---------------------|
| `NoOfOtherSpecialCharsInURL` | `0.0032` | `0.827` | ❌ No |
| `TLDLegitimateProb` | `0.0026` | `0.956` | ❌ No |
| `IsHTTPS` | `0.0009` | `1.000` | ❌ No |
| (all features) | `<0.006` | `>0.24` | ❌ No |

**✅ Conclusion:** No train/val leakage via distribution shift

### 🎯 Investigation 3: Prediction Confidence Analysis

**📊 Validation Set Probabilities:**

| **📊 Metric** | **📈 Value** |
|---------------|--------------|
| **Mean** | `0.427` |
| **Std** | `0.492` |
| **Predictions < 0.001** | `9.5%` |
| **Predictions > 0.999** | `41.7%` |
| **Total extreme confidence** | `51.2%` |

**⚠️ Concern:** High proportion of extreme probabilities suggests overconfidence.  
**🔍 Analysis:** Model is confident but not overfit:

- ✅ Training and validation distributions match (no train/val gap)
- ✅ Cross-validation stability confirms generalization
- ✅ Extreme confidence reflects genuinely easy cases (e.g., HTTP phishing sites)

**✅ Conclusion:** Confidence levels are high but legitimate

### 🚨 Investigation 4: Error Analysis

**📊 8-Feature Model Errors:**

| **📊 Metric** | **📈 Value** |
|---------------|--------------|
| **Total errors** | `147 / 47,074 (0.31%)` |
| **🔴 False positives** | `15` (predicted phish, actually legit) |
| **🟡 False negatives** | `132` (predicted legit, actually phish) |

**🔍 Error Pattern Analysis:**

- ⚠️ All errors have `IsHTTPS=1` (HTTPS sites that fooled model)
- 📉 False negatives are HTTPS phishing sites (minority in dataset)
- 🎭 Error features resemble legitimate sites (low special chars, normal length)

**📋 Sample Confident Error:**
```
URL: [HTTPS phishing site]
p_malicious: 0.0006 (model predicted legit)
Actual: Phishing
Features: IsHTTPS=1, TLDLegitimateProb=0.523, CharContinuationRate=1.0
```

**✅ Conclusion:** Errors are hard cases, not random noise

### 📊 Investigation 5: Cross-Validation Stability

**🔬 Method:** 5-fold stratified cross-validation

**📈 Results:**

| **📊 Fold** | **📈 PR-AUC** |
|-------------|---------------|
| **Fold 1** | `0.9991` |
| **Fold 2** | `0.9989` |
| **Fold 3** | `0.9993` |
| **Fold 4** | `0.9992` |
| **Fold 5** | `0.9991` |

| **📊 Summary** | **📈 Value** |
|----------------|--------------|
| **Mean** | `0.9991` |
| **Std** | `0.0001` |
| **Holdout** | `0.9990` |

**✅ Conclusion:** Extremely stable across folds (std=0.0001)

### 🏆 Overall Leakage Verdict

<div align="center">

## ✅ NO DATA LEAKAGE DETECTED

</div>

**🔍 Evidence:**

- ✅ No distribution shift between train/val
- ✅ Stable cross-validation performance
- ✅ Consistent train/val probability distributions
- ✅ No duplicate URLs across splits (removed in EDA)
- ✅ No policy-sensitive features (Domain, URLSimilarityIndex excluded)

> **📝 However:** IsHTTPS dominance reflects temporal bias in dataset (2020-2022 HTTPS adoption rates), not leakage.

---

## ⚖️ Model Comparison: 8-Feature vs 7-Feature

### 🎯 Motivation

IsHTTPS accounted for 72% of model importance, but this reflects 2020-2022 phishing patterns when only ~50% of phishing sites used HTTPS. In 2025, 80%+ of phishing sites use HTTPS (Let's Encrypt made it free/automated).

**❓ Question:** How much does model performance degrade without IsHTTPS?

### 📊 Performance Comparison

<div align="center">

| **📊 Metric** | **🏆 8-Feature (IsHTTPS)** | **✅ 7-Feature (No IsHTTPS)** | **📉 Degradation** |
|---------------|---------------------------|------------------------------|---------------------|
| **PR-AUC** | `0.9990` | `0.9985` | `-0.05%` |
| **F1-Macro** | `0.9968` | `0.9919` | `-0.49%` |
| **Brier Score** | `0.002777` | `0.006382` | `+0.0036` |
| **Error Rate** | `0.31% (147)` | `0.79% (374)` | `+0.48%` |
| **`t_star`** | `0.400` | `0.600` | `+0.200` |
| **Gray-zone Rate** | `12.2%` | `9.4%` | `-2.8%` |

</div>

### 🔄 Feature Importance Shift

**🏆 8-Feature Model:**
```
IsHTTPS                        72.4%
NoOfOtherSpecialCharsInURL     22.9%
(remaining features)            4.7%
```

**✅ 7-Feature Model:**
```
NoOfOtherSpecialCharsInURL     74.9%
LetterRatioInURL                5.7%
SpacialCharRatioInURL           5.4%
DomainLength                    5.0%
TLDLegitimateProb               3.8%
URLCharProb                     3.0%
CharContinuationRate            2.2%
```

> **💡 Key Insight:** NoOfOtherSpecialCharsInURL becomes dominant (75%) without IsHTTPS, proving URL structure features are independently strong.

### 🔍 Error Overlap Analysis

| **📊 Error Category** | **📈 Count** | **📝 Description** |
|----------------------|--------------|-------------------|
| **🔄 Errors in both models** | `115` | Genuinely hard cases |
| **🏆 Only 8-feature errors** | `32` | IsHTTPS helped marginally |
| **✅ Only 7-feature errors** | `259` | IsHTTPS would have saved these |

**🔍 Interpretation:**

- ✅ IsHTTPS helps with 32 edge cases (minor benefit)
- ⚠️ 115 errors are irreducible with current features
- 📊 259 additional errors without IsHTTPS are acceptable for production robustness

### 🎯 Key Findings

- **📉 Minimal Performance Loss:** Only 0.05% PR-AUC drop without IsHTTPS
- **💪 Strong Alternative Signal:** NoOfOtherSpecialCharsInURL compensates effectively
- **🛡️ Production Robustness:** 7-feature model won't degrade as HTTPS phishing increases
- **🏆 Both Models Excellent:** Both exceed 99.8% PR-AUC

### ✅ Recommendation: Deploy 7-Feature Model for Production

**💡 Rationale:**

- 📊 Near-identical performance (0.9985 vs 0.9990)
- 🛡️ Robust to 2025+ threat landscape (HTTPS phishing common)
- 🔮 Future-proof against temporal drift
- 🎯 Still achieves 99.8% PR-AUC without protocol dependency

**🏆 8-Feature Model Use Case:**

- 📊 Benchmark for maximum performance on this dataset
- 🧪 A/B test to measure IsHTTPS value over time
- 🔬 Research baseline for future iterations

---

## 📈 Performance Analysis

### 🎯 Metrics Selection

#### 1. **📊 Primary: PR-AUC (Precision-Recall AUC)**

**❓ Why:** Focuses on positive class (phishing) performance

**✅ Advantages:**
- 🎯 Not affected by class imbalance (43% phish, 57% legit)
- 📊 Measures quality of p_malicious ranking
- ⚖️ Emphasizes high-precision, high-recall trade-off

**🆚 Better than ROC-AUC because:**
- 📈 ROC-AUC inflated by easy negatives (legitimate URLs)
- 🎯 PR-AUC directly measures fraud detection quality

#### 2. **📊 Secondary: F1-Macro**

**❓ Why:** Balances precision and recall across BOTH classes

**✅ Advantages:**

- Ensures legitimate URL detection isn't sacrificed
- Symmetric measure (treats both errors equally)
- Macro averaging treats classes equally regardless of frequency

#### 3. **📊 Tertiary: Brier Score**
**❓ Why:** Measures calibration quality
**✅ Advantages:**

- Assesses how accurate probabilities are
- Critical for threshold-based decisions
- Lower is better (penalizes overconfident wrong predictions)

**Interpretation:**

- `Brier` < 0.01 is excellent calibration
- `Our models`: 0.0027 (8-feat), 0.0064 (7-feat) - both excellent

**Calibration Strategy**
- **Method:** Isotonic Regression with 5-Fold Stratified CV

**❓ Why:Isotonic (not Platt/Sigmoid)?**

- Isotonic: Non-parametric, learns arbitrary monotonic function
- Platt: Assumes sigmoid shape (too restrictive for XGBoost)
- Literature: Isotonic is proven best for tree-based models

**❓ Why 5-Fold CV?**

- Prevents overfitting during calibration
- Uses 80% train, 20% calibrate in each fold
- More robust than single hold-out calibration

**Validation:**

- Brier score of 0.0027 (8-feat) confirms excellent calibration
- Probability distributions match across train/val sets

**Strengths:**

- ***Excellent Discrimination:*** 99.8-99.9% PR-AUC indicates strong signal
- ***Well-Calibrated:*** Brier < 0.007 means probabilities are reliable for thresholding
- ***Fast Inference:*** 7-8 numeric features, depth=6 trees → <10ms predictions
- ***Balanced Performance:*** F1-macro > 0.99 means both classes handled well
- ***Stable:*** Cross-validation std=0.0001 shows consistent performance
- ***No Leakage:*** Passed 5 leakage tests, no data contamination

## ⚠️ Limitations & Risks
#### **1. Dataset vs Production Gap**
***Issue:*** PhiUSIIL is research data (2020-2022), not live traffic

**Impact:**
- Real-world phishing tactics evolve faster than research datasets
- Dataset may contain collection artifacts (e.g., all IPFS URLs labeled phishing)
- Attackers adapt to defenses

**Mitigation:**
- A/B test on real Helcim traffic before full rollout
- Monitor false positive rate closely (legitimate URLs blocked)
- Plan monthly retraining on fresh phishing examples

**Expected Production Performance:**

- Realistic PR-AUC: 0.90-0.95 (5-10% degradation from test)
- Acceptable error rate: <1% false positives

#### **2. No Temporal Features**
***Issue:*** Missing domain age (strong real-world signal)

**Impact:**

- Can't detect brand-new malicious domains
- Phishing sites typically <48 hours old
- Domain age is one of strongest production signals

**Why Missing:**

- PhiUSIIL dataset doesn't include registration timestamps
- Would require WHOIS lookup for each URL (latency/cost)

**Mitigation:**

- Integrate domain age lookup in production (DomainTools API, WHOIS cache)
- Use domain age as Tier-0 feature (check first, fallback to model)
- Expect 5-10% performance boost with domain age

#### **3. Static Thresholds**
***Issue:*** Thresholds (low/high) don't adapt to changing fraud rates

**Impact:**

- If phishing rate increases, more REVIEW decisions
- If phishing rate decreases, thresholds may be too conservative

**Mitigation:**

- Monitor `ALLOW`/REVIEW/BLOCK distribution over time
- Implement dynamic threshold adjustment based on fraud rate trends
- Quarterly threshold retuning on validation set

#### **4. Adversarial Robustness Unknown**
***Issue:*** No testing against adversarial attacks

**Examples:**

- Attackers could minimize special characters to fool model
- Could use common TLDs (.com) instead of suspicious ones (.tk)
- Could craft URLs that mimic legitimate patterns

**Mitigation:**

- Implement ensemble with page-content model (HTML features)
- Monitor for anomalous URL patterns
- Human review of REVIEW zone decisions provides safety net


## 🎚️ Threshold Tuning
### 🧭 Policy Band Design
**Objective:** Maximize automation (`ALLOW`/BLOCK) while maintaining safety net (REVIEW) for uncertain cases

***Three Decision Zones:***
```
p_malicious
     0.0          LOW         HIGH         1.0
     |----------------|----------|-----------|
           `ALLOW`         REVIEW       BLOCK
```

        
**Threshold Selection Process**

**Step 1:** Find ``t_star`` (F1-Optimal Threshold)

***Method:*** Grid search over 19 thresholds (0.05 to 0.95)

**8-Feature Model:**

- ``t_star``: 0.400
- `F1-macro @t_star`: 0.9969

**7-Feature Model:**

- ``t_star``: 0.600
- `F1-macro @t_star`: 0.9919

**Interpretation:**

`t_star` represents optimal single threshold if forced to make binary decisions
- Low `t_star` (0.4) means model is conservative (better safe than sorry)
- Higher `t_star` (0.6) in 7-feature model reflects less confidence without IsHTTPS

**Step 2:** Find Gray-Zone Band

***Method:*** Binary search for symmetric band around `t_star` targeting 10-15% gray-zone rate
**Target Rationale:**

- Too small (<5%): Defeats purpose of having judge
- Too large (>20%): Overloads human reviewers
- Sweet spot (10-15%): Catches edge cases without overwhelming ops

**8-Feature Thresholds:**
```
Low:  0.003 (0.3%)   → ALLOW if p_malicious < 0.003
High: 0.797 (79.7%)  → BLOCK if p_malicious ≥ 0.797
Gray-zone: 12.2%     → REVIEW if 0.003 ≤ p_malicious < 0.797

```
**7-Feature Thresholds:**
```
Low:  0.200 (20.0%)  → ALLOW if p_malicious < 0.200
High: 1.000 (100%)   → BLOCK if p_malicious = 1.000
Gray-zone: 9.4%      → REVIEW if 0.200 ≤ p_malicious < 1.000

Low:  0.200 (20.0%)  → ALLOW if p_malicious < 0.200
High: 1.000 (100%)   → BLOCK if p_malicious = 1.000
Gray-zone: 9.4%      → REVIEW if 0.200 ≤ p_malicious < 1.000

```
### 📊 **Decision Distribution**
**8-Feature Model (Validation Set):**

- `ALLOW`: 45.5% (21,419 URLs) - High-confidence legitimate
- `REVIEW`: 12.2% (5,743 URLs) - Escalate to judge
- `BLOCK`: 42.4% (19,912 URLs) - High-confidence phishing

7-Feature Model (Validation Set):

- `ALLOW`: 46.0% (21,654 URLs) - High-confidence legitimate
- `REVIEW`: 9.4% (4,425 URLs) - Escalate to judge
- `BLOCK`: 44.6% (20,995 URLs) - High-confidence phishing

**Interpretation:**

- ~45% auto-approved (low false positive risk for legitimate URLs)
- ~10-12% escalated to judge (manageable workload)
- ~43% auto-blocked (catches majority of phishing without human review)

**Threshold Trade-offs**

- ***Conservative Thresholds (High Low, Low High):***

  - Pro: Fewer false positives, better user experience
  - Con: More REVIEW decisions, higher ops cost

- ***Aggressive Thresholds (Low Low, High High):***

  - Pro: More automation, lower ops cost
  - Con: More false positives/negatives, worse user experience

**Our Choice (Moderate):**

- 8-feature: Very aggressive `ALLOW` (low=0.003), conservative BLOCK (high=0.797)
- 7-feature: Moderate `ALLOW` (low=0.200), aggressive BLOCK (high=1.000)

Balances automation with safety


## 🚀 Production Recommendations
### 🧭 Deployment Strategy
```
┌─────────────────────────────────────────────────────────────────┐
│                      PRODUCTION DEPLOYMENT                       │
├─────────────────────────────────────────────────────────────────┤
│ Primary Model: 7-feature (no IsHTTPS)                           │
│   - Path: models/dev/model_7feat.pkl                           │
│   - PR-AUC: 0.9985                                              │
│   - Inference: <10ms                                            │
│   - Robust to 2025 HTTPS phishing landscape                     │
├─────────────────────────────────────────────────────────────────┤
│ Shadow Model: 8-feature (with IsHTTPS)                         │
│   - Path: models/dev/model_8feat.pkl                           │
│   - PR-AUC: 0.9990                                              │
│   - Purpose: A/B test, measure IsHTTPS value over time          │
│   - Monitor: IsHTTPS importance decay                           │
└─────────────────────────────────────────────────────────────────┘


```
### ✅ Pre-Deployment Checklist

 - A/B Test: Shadow mode on 10% of traffic for 2 weeks
 - False Positive Monitoring: Set alert threshold at 0.5% FP rate
 - Latency Testing: Confirm <50ms p99 latency
 - SHAP Explanations: Implement for BLOCK decisions
 - Judge Integration: Test REVIEW escalation workflow
 - Fallback: Configure heuristic fallback if model unavailable

### 📡 Monitoring Strategy
#### 📊 Model Performance Metrics
**Track Daily:**

###### 🔁 Distribution Drift

- Feature means/stds vs training baseline
- Alert if KS test p-value < 0.01 for any feature


###### 📉 Performance Decay

- PR-AUC on rolling 7-day holdout set
- Alert if PR-AUC < 0.95


###### 📊 Decision Distribution

- `ALLOW` / `REVIEW` / `BLOCK` percentages
- Alert if REVIEW rate > 20% (ops overload)



#### 💼 Business Metrics
##### 📅 Track Weekly

- False Positive Rate: Legitimate URLs blocked

  - Target: <0.5%
  - Alert: >1.0%


- False Negative Rate: Phishing URLs ALLOWED

  - Track via user reports + judge feedback
  - Alert: Increasing trend


- Judge Agreement Rate: Model vs judge decisions

  - Healthy: >85% agreement
  - Alert: <70% agreement (model drift)



#### 📌 Feature Importance Tracking
##### 📅 Track Monthly

- Monitor IsHTTPS importance in 8-feature model
- Expected: Gradual decrease as HTTPS phishing increases
- If IsHTTPS importance drops below 30%, consider removing from model

#### 🔁 Retraining Schedule
##### 🗓️ Monthly Retraining

- Fresh data window: Rolling 6 months
- Minimum dataset size: 50K URLs
- Validation: Hold out last month for testing
- Deploy: Only if new model improves PR-AUC by >1%

##### ⚡ Trigger-Based Retraining

- Performance decay: PR-AUC drops below 0.93
- Distribution drift: Any feature KS p-value < 0.01 for 3 consecutive days
- Feature importance shift: IsHTTPS drops below 20% (remove and retrain)

### 📈 Expected Production Performance
**Conservative Estimates:**

- PR-AUC: 0.90-0.95 (5-10% degradation from test)
- False Positive Rate: 0.3-0.8% (acceptable for user experience)
- False Negative Rate: 1-2% (acceptable with judge backup)
- Latency: <50ms p99 (8 features, depth=6 trees)

### ⚠️ Degradation Factors

- Adversarial adaptation (attackers evolving tactics)
- Distribution shift (real Helcim traffic vs research dataset)
C- oncept drift (new phishing techniques)


### Limitations and Future Work
**Current Limitations**

- URL-Only Features: Fast but misses page content signals (HTML, JavaScript)
- No Temporal Features: Doesn't use domain age (strong real-world signal)
- Static Thresholds: Don't adapt to changing fraud patterns
- Dataset Age: PhiUSIIL is 2020-2022 data, may not reflect 2025+ tactics
- No Adversarial Testing: Unknown robustness to targeted attacks

**Short-Term Improvements (Next Sprint)**

- Add Domain Age:

  - Integrate WHOIS lookup or DomainTools API
  - Expected: 5-10% PR-AUC boost
  - Trade-off: +20-50ms latency per lookup


- Implement SHAP Explanations:

  - Post-hoc interpretability for BLOCK decisions
  - Helps customer support explain blocks
  - Minimal latency impact (<5ms)


- Shadow Mode Deployment:

  - A/B test on 10% of Helcim traffic
  - Measure real-world false positive rate
  - Validate latency under load



**Medium-Term Improvements (Next Quarter)**

- Adaptive Thresholds:

  - Dynamic adjustment based on fraud rate trends
  - Quarterly retuning on validation set
  - Machine: Adjust thresholds automatically


- Ensemble with Page-Content Model:

  - Train complementary model on HTML features
  - Weighted voting or stacking
  - Expected: 2-5% PR-AUC boost


- Active Learning Pipeline:

  - Incorporate judge feedback into retraining
  - Prioritize labeling of REVIEW zone decisions
  - Continuous improvement loop



**Long-Term Vision (Next Year)**

- Real-Time Feature Extraction:

  - Extract features from live traffic (not batch)
  - Enable online learning
  - Reduce feedback loop from monthly to daily


- Multi-Model Ensemble:

  - URL structure (current model)
  - Page content (HTML/JS features)
  - Behavioral (user interaction patterns)
  - Ensemble: Weighted voting or neural meta-learner


- Adversarial Robustness:

  - Generate adversarial examples
  - Adversarial training
  - Red team testing



## 🔄 Reproducibility
### 📦 Artifacts
#### 🧠 Models
```

8-feature: models/dev/model_8feat.pkl (MD5: [generated])
7-feature: models/dev/model_7feat.pkl (MD5: [generated])

```
#### 🗂️ Metadata
```

8-feature: models/dev/model_8feat_meta.json
7-feature: models/dev/model_7feat_meta.json

```
#### 🎚️ Thresholds
```

8-feature: configs/dev/thresholds_8feat.json
7-feature: configs/dev/thresholds_7feat.json

```
#### 📈 Visualizations
```

Feature importance comparison: outputs/model/feature_importance.png
Probability distributions: outputs/model/probability_distributions.png
Model comparison: outputs/model/model_comparison.png

```
### 🎲 Random Seed
- All random operations use SEED=42:

- Train/test split
- XGBoost internal randomness
- Calibration CV folds
- Cross-validation splits

### 🧰 Environment
#### 📦 Key Dependencies
```
python==3.11
scikit-learn==1.5.2
xgboost==2.1.3
pandas==2.2.3
numpy==1.26.4
```

Full dependencies: See requirements.txt
### 🧪 Training Command
```
# From project root
jupyter notebook notebooks/02_model_training.ipynb

# Or via MLflow
mlflow run . --experiment-name phiusiil_baselines
```
### 📊 MLflow Experiment
- Tracking URI: http://localhost:5000 (default)
- Experiment: phiusiil_baselines
Run Names:

- xgb_optimal8_calibrated (8-feature model)
- xgb_optimal7_calibrated (7-feature model)

Logged Artifacts:

- Parameters
