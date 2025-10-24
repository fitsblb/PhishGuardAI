# 🏗️ PhishGuardAI Architecture

**Deep dive into system design decisions, trade-off analysis, and architectural patterns.**

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [The IsHTTPS Decision: Distribution Shift Analysis](#the-ishttps-decision-distribution-shift-analysis)
3. [Feature Engineering Philosophy](#feature-engineering-philosophy)
4. [Policy Bands & Gray Zone Design](#policy-bands--gray-zone-design)
5. [LLM Judge Integration](#llm-judge-integration)
6. [SHAP Explainability](#shap-explainability)
7. [Graceful Degradation Strategy](#graceful-degradation-strategy)
8. [Trade-off Analysis](#trade-off-analysis)
9. [Future Architecture Evolution](#future-architecture-evolution)

---

## 🌐 System Overview

### Design Principles

1. **Multi-tier decisions:** Fast-path optimizations before expensive operations
2. **Fail-safe:** Graceful degradation when components unavailable
3. **Explainable:** Every decision has a traceable rationale
4. **Observable:** Rich instrumentation for monitoring and debugging
5. **Flexible:** Easy to swap components (stub judge ↔ LLM judge)

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    GATEWAY (:8000)                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ TIER 1: Whitelist (O(1) set lookup)                 │   │
│  │  • 15 known-good domains                            │   │
│  │  • Latency: <1ms                                    │   │
│  │  • Fast-path ALLOW (bypasses model)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ TIER 2: Model Inference (HTTP call)                 │   │
│  │  • Feature extraction (7 features)                  │   │
│  │  • XGBoost + isotonic calibration                   │   │
│  │  • Latency: ~50ms                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ TIER 3: Policy Bands (threshold comparison)         │   │
│  │  • p < 0.011 → ALLOW                                │   │
│  │  • p > 0.998 → BLOCK                                │   │
│  │  • 0.011 ≤ p ≤ 0.998 → REVIEW (gray zone)          │   │
│  │  • Latency: <1ms                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ TIER 4: Judge Escalation (gray zone only)           │   │
│  │  • Enhanced routing: short domain detection         │   │
│  │  • LLM judge (primary) or stub (fallback)           │   │
│  │  • Latency: 2-5s (LLM), <1ms (stub)                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ MODEL (:8002)│  │OLLAMA (:11434│  │  MONGO       │
│ • XGBoost    │  │ • llama3.2   │  │  (optional)  │
│ • SHAP       │  │ • Judge LLM  │  │  • Audit     │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Request Flow

**High-confidence legitimate (52% of traffic):**
```
Client → Gateway → Whitelist? → YES → ALLOW (10ms)
Client → Gateway → Whitelist? → NO → Model → p=0.001 → ALLOW (60ms)
```

**High-confidence phishing (36% of traffic):**
```
Client → Gateway → Model → p=0.999 → BLOCK (60ms)
```

**Gray zone (12% of traffic):**
```
Client → Gateway → Model → p=0.35 → Judge → ALLOW/BLOCK/REVIEW (2-5s)
```

---

## 🚨 The IsHTTPS Decision: Distribution Shift Analysis

### Background

**Initial Feature Selection:**
- IsHTTPS had **highest separation score (2.829)** among all features
- Training data: 94% phishing = HTTP, 97% legitimate = HTTPS
- Seemed like the perfect feature!

### The Problem

**Validation revealed systematic bias:**

```
8-Feature Model @ Optimal Threshold (0.36):
┌──────────────┬─────────────┬─────────────┐
│              │ Pred Legit  │ Pred Phish  │
├──────────────┼─────────────┼─────────────┤
│ True Legit   │   26,942    │     28      │
│ True Phish   │     101     │  19,882     │
└──────────────┴─────────────┴─────────────┘

HTTPS Breakdown of False Negatives:
• Total FNs: 101
• HTTPS FNs: 101 (100%)  ← SYSTEMATIC VULNERABILITY!
• HTTP FNs: 0
```

**Key Finding:** Even at optimal threshold, the model had **100% HTTPS false negatives**.

### Root Cause Analysis

**Training data distribution shift:**

| URL Type | Dataset (2019-2020) | Reality (2025) |
|----------|---------------------|----------------|
| Phishing HTTPS | 6% | **~75%** (Let's Encrypt era) |
| Legitimate HTTPS | 97% | 99% |

**Model behavior:**
```python
# What the model learned:
if IsHTTPS == 1:
    p_malicious *= 0.01  # Strong legitimacy signal
    
# Result:
# HTTPS phishing → Incorrectly classified as legitimate
```

**Why threshold tuning didn't help:**
- Lowering threshold (0.36) only partially compensates
- The bias is **structural** in the feature representation
- All HTTPS phishing still concentrated in false negatives

### The 7-Feature Alternative

**Removing IsHTTPS:**

```
7-Feature Model @ Optimal Threshold (0.50):
┌──────────────┬─────────────┬─────────────┐
│              │ Pred Legit  │ Pred Phish  │
├──────────────┼─────────────┼─────────────┤
│ True Legit   │   26,904    │     66      │
│ True Phish   │     210     │  19,773     │
└──────────────┴─────────────┴─────────────┘

HTTPS Breakdown of False Negatives:
• Total FNs: 210
• HTTPS FNs: 93 (44.3%)  ← RANDOM DISTRIBUTION ✅
• HTTP FNs: 117 (55.7%)
```

**Key Finding:** Errors are now **randomly distributed** across HTTP and HTTPS.

### Decision Matrix

| Factor | 8-Feature (IsHTTPS) | 7-Feature (no IsHTTPS) | Winner |
|--------|---------------------|------------------------|--------|
| **Total FNs** | 101 | 210 | 8-feature |
| **HTTPS FN Rate** | 100% | 44% | **7-feature** ✅ |
| **Error Pattern** | Systematic | Random | **7-feature** ✅ |
| **Threshold** | 0.36 (non-standard) | 0.50 (standard) | **7-feature** ✅ |
| **Production Risk** | High (HTTPS blind spot) | Low (robust) | **7-feature** ✅ |
| **PR-AUC** | 0.9992 | 0.9987 | 8-feature |
| **Operational Complexity** | Higher (unusual threshold) | Lower (standard) | **7-feature** ✅ |

### The Trade-off

**What we gave up:**
- 109 additional false negatives (+0.54% miss rate)
- 0.0005 PR-AUC decrease

**What we gained:**
- **Eliminated 100% HTTPS failure mode**
- Random error distribution (no systematic blind spot)
- Standard threshold (0.5) for easier operations
- Robust to modern phishing landscape (75% HTTPS)

### Why This Matters

**Attack Scenario:**

```
Attacker discovers 8-feature model vulnerability:
1. Launch HTTPS phishing campaign
2. 100% of campaign evades detection
3. Massive security incident

vs.

7-feature model:
1. Launch HTTPS phishing campaign  
2. 56% caught by model
3. 44% false negatives distributed randomly (acceptable baseline)
```

### Key Lesson

**Error Pattern > Error Count**

In fraud detection, a **predictable blind spot** (100% HTTPS miss rate) is more dangerous than a **higher error count with random distribution**.

**Analogy:** 
- 8-feature: A fortress with 99 walls and 1 known gap → Attackers exploit the gap
- 7-feature: A fortress with 95 walls randomly distributed → Attackers can't target specific weakness

---

## 🧬 Feature Engineering Philosophy

### Design Principles

1. **URL-Only Features:** No page fetching (latency, reliability)
2. **Stateless:** No external dependencies (DNS, WHOIS, etc.)
3. **Interpretable:** Features have clear business meaning
4. **Robust:** Resistant to adversarial manipulation

### Feature Selection Criteria

**Why These 7 Features?**

| Feature | Separation Score | Interpretability | Adversarial Robustness |
|---------|------------------|------------------|------------------------|
| **TLDLegitimateProb** | 2.012 | ✅ High | ⚠️ Medium (TLD can be faked) |
| **CharContinuationRate** | 1.372 | ✅ High | ✅ High (hard to hide repetition) |
| **SpacialCharRatioInURL** | 1.330 | ✅ High | ⚠️ Medium |
| **URLCharProb** | 0.889 | ⚠️ Medium | ✅ High (statistical property) |
| **LetterRatioInURL** | 0.825 | ✅ High | ⚠️ Medium |
| **NoOfOtherSpecialCharsInURL** | 0.540 | ✅ High | ⚠️ Low (easy to manipulate) |
| **DomainLength** | 0.301 | ✅ High | ✅ High (structural property) |

### TLD Legitimacy Probability

**Bayesian Prior Implementation:**

```python
def calculate_tld_prob(tld: str, train_data: DataFrame) -> float:
    """
    Calculate P(legitimate | TLD) using Bayesian estimation.
    
    Args:
        tld: Top-level domain (e.g., "com", "org", "tk")
        train_data: Training dataset with labels
        
    Returns:
        Probability in [0, 1]
    """
    # Count TLD occurrences
    tld_legit = train_data[(train_data['TLD'] == tld) & (train_data['label'] == 1)].shape[0]
    tld_total = train_data[train_data['TLD'] == tld].shape[0]
    
    # Hyperparameters (justified by confidence interval analysis)
    alpha = 5  # Pseudo-legitimate count
    beta = 5   # Pseudo-phishing count
    
    # Handle rare TLDs (< MIN_SAMPLES)
    if tld_total < 10:
        return 0.5  # Neutral (maximum uncertainty)
    
    # Bayesian estimation
    p_legit = (tld_legit + alpha) / (tld_total + alpha + beta)
    
    return p_legit
```

**Why Bayesian Estimation?**
- **Smoothing:** Prevents overfitting to rare TLDs
- **Uncertainty:** Returns 0.5 for unseen TLDs (neutral)
- **Interpretable:** Direct probability interpretation

**Example TLD Probabilities:**
```
.com   → 0.67 (moderately legitimate)
.org   → 0.81 (highly legitimate)
.gov   → 0.99 (almost always legitimate)
.tk    → 0.12 (often phishing)
.xyz   → 0.23 (suspicious)
```

### Feature Extraction Consistency

**Critical Design: Shared Library**

```
Training:
notebooks/01_baseline.ipynb
  ↓
common/feature_extraction.py  ← Shared implementation
  ↓
Training features → Model

Serving:
src/model_svc/main.py
  ↓
common/feature_extraction.py  ← Same shared implementation
  ↓
Serving features → Model
```

**Why This Matters:**
- **Training/serving skew prevention:** Same code for both
- **Single source of truth:** One feature definition
- **Easy updates:** Change once, affects both train & serve

---

## 🎯 Policy Bands & Gray Zone Design

### Policy Band Architecture

**Three-tier decision framework:**

```
                    ┌─────────────────────────────┐
                    │   Model Prediction          │
                    │   p_malicious ∈ [0, 1]      │
                    └──────────┬──────────────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
        p < 0.011      0.011 ≤ p ≤ 0.998     p > 0.998
               │               │               │
               ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │  ALLOW   │    │  REVIEW  │    │  BLOCK   │
        │  (52%)   │    │  (12%)   │    │  (36%)   │
        └──────────┘    └──────────┘    └──────────┘
               │               │               │
               └───────────────┴───────────────┘
                               │
                        Final Decision
```

### Threshold Selection Methodology

**Step 1: Optimal Threshold (t*)**

```python
# Maximize F1-macro
thresholds = np.linspace(0, 1, 1000)
f1_scores = []

for t in thresholds:
    y_pred = (y_proba >= t).astype(int)
    f1 = f1_score(y_true, y_pred, average='macro')
    f1_scores.append(f1)

t_star = thresholds[np.argmax(f1_scores)]
# Result: t_star = 0.500
```

**Step 2: Gray Zone Bounds**

```python
# Target: 10-15% of validation set in gray zone

# Low threshold: 5th percentile of phishing predictions
low_threshold = np.percentile(y_proba[y_true == 0], 5)
# Result: 0.011

# High threshold: 95th percentile of legitimate predictions  
high_threshold = np.percentile(y_proba[y_true == 1], 95)
# Result: 0.998

# Gray zone rate
gray_zone_rate = np.mean((y_proba >= low_threshold) & (y_proba <= high_threshold))
# Result: 12.0%
```

**Step 3: Validation**

```python
# Decision distribution on validation set
allow_rate = np.mean(y_proba < low_threshold)    # 52.0%
review_rate = gray_zone_rate                      # 12.0%
block_rate = np.mean(y_proba > high_threshold)   # 36.0%

# Automation rate (no human needed)
automation_rate = allow_rate + block_rate         # 88.0%
```

### Why These Thresholds?

**Low Threshold (0.011):**
- **Purpose:** Fast-path ALLOW for clearly legitimate URLs
- **Rationale:** 5th percentile of phishing → 95% of phishing caught
- **Trade-off:** Accept 5% FNs for 52% automation

**High Threshold (0.998):**
- **Purpose:** Fast-path BLOCK for clearly malicious URLs
- **Rationale:** 95th percentile of legitimate → 95% of legit passed
- **Trade-off:** Accept 5% FPs for 36% automation

**Gray Zone (0.011 to 0.998):**
- **Purpose:** Human review or judge escalation
- **Size:** 12% of traffic (5,632 samples in validation)
- **Rationale:** Uncertain cases benefit from additional review

### Operational Implications

**Throughput:**
```
1,000 requests/sec:
• ALLOW: 520/sec (policy band, <1ms latency)
• BLOCK: 360/sec (policy band, <1ms latency)
• REVIEW: 120/sec (judge escalation, 2-5s latency)

Judge Capacity Needed:
• 120 req/sec * 3s avg = 360 concurrent judge requests
• Recommend: 400+ judge workers or async queue
```

**Latency Profile:**
```
P50 (median): 60ms   (ALLOW/BLOCK via model)
P95: 100ms           (ALLOW/BLOCK via model)
P99: 5000ms          (REVIEW via LLM judge)
```

---

## 🧠 LLM Judge Integration

### Design Rationale

**Why LLM Judge?**

1. **Edge case handling:** Short domains (npm.org, bit.ly) defy simple rules
2. **Explainability:** Human-readable rationale for gray zone decisions
3. **Flexibility:** Easy to update prompts vs. retraining model
4. **User trust:** Natural language explanations build confidence

**Why Not Just Retrain Model?**

- Gray zone is **12% of traffic** → Not worth full retraining cycle
- Edge cases are **rare but important** → LLM excels at few-shot reasoning
- **Operational agility:** Can update judge behavior without model deployment

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│ JUDGE WIRE (src/gateway/judge_wire.py)                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1. Check if URL in gray zone (0.011 ≤ p ≤ 0.998)    │ │
│  └────────────────────┬─────────────────────────────────┘ │
│                       │                                    │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 2. Enhanced Routing:                                 │ │
│  │    • Domain ≤ 10 chars AND p < 0.5?                 │ │
│  │    • If yes: Flag as short domain edge case         │ │
│  └────────────────────┬─────────────────────────────────┘ │
│                       │                                    │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 3. Call Judge:                                       │ │
│  │    • Primary: LLM Adapter (Ollama)                  │ │
│  │    • Fallback: Stub Judge (deterministic)           │ │
│  └────────────────────┬─────────────────────────────────┘ │
└────────────────────────┼──────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│  LLM ADAPTER    │              │  STUB JUDGE     │
│  (Primary)      │              │  (Fallback)     │
│  ┌───────────┐  │              │  ┌───────────┐  │
│  │ Ollama    │  │              │  │ Rules     │  │
│  │ llama3.2  │  │              │  │ < 1ms     │  │
│  │ 2-5s      │  │              │  └───────────┘  │
│  └───────────┘  │              └─────────────────┘
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ VERDICT MAPPING                         │
│  • LEAN_PHISH → BLOCK                  │
│  • LEAN_LEGIT → ALLOW                  │
│  • UNCERTAIN → REVIEW (human escalate) │
└─────────────────────────────────────────┘
```

### Short Domain Detection

**Rationale:**

Legitimate short domains often look suspicious to statistical models:
- `npm.org` (7 chars) - Package manager, obviously legitimate
- `bit.ly` (6 chars) - URL shortener, legitimate but commonly abused
- `t.co` (4 chars) - Twitter shortener, legitimate

**Detection Logic:**

```python
def _should_route_to_judge_for_short_domain(url: str, p_malicious: float) -> bool:
    """
    Route to judge if:
    1. Domain ≤ 10 characters
    2. Confidence moderate (p < 0.5)
    
    Catches edge cases like npm.org that whitelist doesn't cover.
    """
    domain = extract_domain(url)
    
    is_short = len(domain) <= SHORT_DOMAIN_LENGTH  # Default: 10
    is_moderate_confidence = p_malicious < SHORT_DOMAIN_CONFIDENCE  # Default: 0.5
    
    return is_short and is_moderate_confidence
```

**Example:**
```
URL: http://npm.org/package/express
Model: p_malicious = 0.35 (gray zone)
Domain: "npm.org" (7 chars)
Condition: 7 ≤ 10 AND 0.35 < 0.5 → TRUE
Action: Route to LLM judge

LLM Judge Response:
"Domain 'npm.org' is a well-known package manager. Short domain length 
(7 chars) is expected for legitimate tech infrastructure. TLD .org is 
commonly used by open-source projects. VERDICT: LEAN_LEGIT"

Final Decision: ALLOW
```

### Prompt Engineering

**Current Prompt Structure:**

```
1. Role Definition:
   "You are a cybersecurity analyst specializing in phishing detection."
   
2. Feature Context:
   "KEY FEATURES TO ANALYZE:
    - TLDLegitimateProb: Bayesian TLD legitimacy probability [0,1]
    - CharContinuationRate: Character repetition patterns [0,1]
    ..."
    
3. Output Format:
   "RESPOND WITH EXACTLY THREE FIELDS:
    VERDICT: LEAN_PHISH | LEAN_LEGIT | UNCERTAIN
    SCORE: risk score in [0,1]
    RATIONALE: brief explanation"
    
4. URL + Features:
   "URL: {url}
    FEATURES: {json_features}"
    
5. Focus Areas:
   "Focus on: HTTPS usage, TLD legitimacy, character patterns,
    and any URL obfuscation techniques."
```

**Why This Works:**
- **Structured output:** Easy to parse (regex on VERDICT/SCORE/RATIONALE)
- **Feature grounding:** LLM bases reasoning on extracted features
- **Concise:** Reduces token count, speeds inference
- **Testable:** Clear success criteria (valid verdict + rationale)

### Failover Strategy

**LLM Failure Modes:**
1. **Timeout (60s):** Model loading or slow generation
2. **Connection refused:** Ollama not running
3. **Parsing failure:** LLM doesn't follow format
4. **Model not found:** Wrong model name

**Graceful Degradation:**
```python
try:
    # Try LLM judge
    response = ollama_api.generate(prompt)
    verdict, score, rationale = parse_response(response)
    return JudgeResponse(
        verdict=verdict,
        rationale=rationale,
        context={"backend": "llm"}
    )
except Exception as e:
    # Fall back to stub judge (deterministic rules)
    logger.error(f"LLM judge failed: {e}")
    stub_response = stub_judge(url, features)
    stub_response.context["backend"] = "stub_fallback"
    stub_response.context["error"] = str(e)
    return stub_response
```

**Failure Impact:**
- **Service continues:** Gray zone URLs get deterministic verdict
- **Logged:** Error recorded for debugging
- **Transparent:** Response includes `backend="stub_fallback"`

---

## 📊 SHAP Explainability

### Why SHAP?

**Requirements:**
1. **Regulatory compliance:** Explain why URL classified as phishing
2. **User trust:** Show which features contributed to decision
3. **Model debugging:** Identify feature importance issues

**Why SHAP over other methods:**
- **Model-agnostic:** Works with XGBoost, logistic regression, etc.
- **Theoretically sound:** Based on Shapley values (game theory)
- **Additive:** Feature contributions sum to prediction

### Implementation Challenge

**Problem:**
```python
# Our model is CalibratedClassifierCV (wrapper around XGBoost)
PRIMARY_MODEL = CalibratedClassifierCV(
    base_estimator=XGBClassifier(...),
    method='isotonic',
    cv=5
)

# SHAP doesn't support calibrated models directly
explainer = shap.TreeExplainer(PRIMARY_MODEL)
# Error: Model type not supported by TreeExplainer
```

**Solution: Unwrap Base Estimator**

```python
def get_shap_explainer(model):
    """
    Create SHAP explainer, unwrapping calibrated models.
    
    Note: SHAP computed on base estimator (before calibration),
    so values are approximate.
    """
    base_model = model
    
    # Check if model is CalibratedClassifierCV
    if hasattr(model, 'calibrated_classifiers_'):
        # Unwrap to get XGBoost base estimator
        base_model = model.calibrated_classifiers_[0].estimator
        logger.info(f"Unwrapped calibrated model. Base type: {type(base_model)}")
    
    # Create SHAP explainer on base model
    explainer = shap.TreeExplainer(base_model)
    return explainer
```

**Trade-off:**
- **Pro:** SHAP works, provides feature importance
- **Con:** Values computed before calibration (approximate)
- **Acceptable:** Relative importance still correct, absolute values slightly off

### SHAP Value Interpretation

**Example:**

```json
{
  "url": "http://verify-account-now.info",
  "p_malicious": 0.85,
  "base_value": 0.318,
  "features": {
    "CharContinuationRate": {
      "value": 0.1,
      "shap_value": -0.523,  // Pushes TOWARDS legitimate
      "importance": 0.523    // Most important feature
    },
    "NoOfOtherSpecialCharsInURL": {
      "value": 6,
      "shap_value": 0.342,   // Pushes TOWARDS phishing
      "importance": 0.342
    },
    "TLDLegitimateProb": {
      "value": 0.43,
      "shap_value": -0.026,  // Slightly legitimate
      "importance": 0.026
    }
  }
}
```

**Interpretation:**
```
base_value:       0.318 (neutral baseline)
+ CharContinuationRate: -0.523 (low repetition → legit signal)
+ NoOfOtherSpecialCharsInURL: +0.342 (6 special chars → phish signal)
+ TLDLegitimateProb: -0.026 (.info TLD → slightly legit)
+ ... (other features)
= final prediction: 0.85 (phishing)

Conclusion: Despite low character repetition (legitimate signal), 
the high special character count and suspicious TLD overcome it.
```

### Dashboard Integration

**Flow:**
```
User → /explain endpoint → SHAP computation → Dashboard rendering
                    ↓
              (200-500ms latency)
```

**Dashboard Features:**
1. **Sorted by importance:** Most influential features first
2. **Color-coded:** Red = phishing signal, Green = legitimate signal
3. **Feature values shown:** Transparency into model input
4. **Intuitive bars:** Visual length proportional to importance

**Code:**
```javascript
// src/gateway/static/explain.html
features.forEach(([name, info]) => {
    const bar = document.createElement('div');
    bar.className = info.shap_value >= 0 ? 'positive' : 'negative';
    bar.style.width = `${(Math.abs(info.shap_value) / maxAbs) * 100}%`;
    bar.textContent = info.shap_value >= 0 ? 
        '→ Increases risk' : '→ Decreases risk';
});
```

---

## 🛡️ Graceful Degradation Strategy

### Design Philosophy

**Never block the entire service due to a single component failure.**

### Failure Modes & Responses

| Component | Failure Mode | Response | Impact |
|-----------|--------------|----------|--------|
| **Model Service** | Down | Gateway returns 503 | ❌ Full outage (acceptable - core component) |
| **LLM Judge** | Timeout (>60s) | Fall back to stub judge | ✅ Service continues, stub verdict |
| **Ollama** | Not running | Fall back to stub judge | ✅ Service continues, stub verdict |
| **SHAP** | Computation fails | Return prediction without explanation | ✅ Prediction succeeds, no explanation |
| **MongoDB** | Connection lost | Skip audit logging | ✅ Service continues, audit incomplete |
| **Whitelist** | Load error | Skip whitelist check | ✅ All URLs go to model (slower) |

### Implementation Patterns

**Pattern 1: Try-Except with Fallback**

```python
def decide_with_judge(url, p_malicious, thresholds):
    try:
        # Try LLM judge
        judge_response = judge_url_llm(url, features)
    except Exception as e:
        # Fall back to stub
        logger.error(f"LLM judge failed: {e}")
        judge_response = judge_url_stub(url, features)
        judge_response.context["backend"] = "stub_fallback"
    
    return judge_response
```

**Pattern 2: Optional Feature with Try-Except**

```python
@app.post("/predict/explain")
def predict_explain(payload):
    # Always return prediction
    prediction = model.predict(features)
    
    # Try SHAP (optional)
    try:
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(features)
    except Exception as e:
        logger.error(f"SHAP failed: {e}")
        shap_values = None
    
    return {
        "prediction": prediction,
        "shap_values": shap_values  # May be null
    }
```

**Pattern 3: Fail-Open for Audit**

```python
def log_decision(url, decision):
    if MONGO_CLIENT is None:
        # No MongoDB configured → Skip silently
        return
    
    try:
        MONGO_CLIENT.decisions.insert_one({
            "url": url,
            "decision": decision,
            "timestamp": datetime.utcnow()
        })
    except Exception as e:
        # Log error but don't fail request
        logger.error(f"Audit log failed: {e}")
        pass
```

### Health Check Strategy

**Tiered Health Checks:**

```python
@app.get("/health")
def health_check():
    health = {
        "status": "healthy",
        "components": {}
    }
    
    # Critical: Model loaded?
    health["components"]["model"] = {
        "status": "healthy" if MODEL_LOADED else "unhealthy",
        "critical": True
    }
    
    # Non-critical: LLM judge available?
    try:
        requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        health["components"]["llm_judge"] = {
            "status": "healthy",
            "critical": False
        }
    except:
        health["components"]["llm_judge"] = {
            "status": "unhealthy",
            "critical": False
        }
    
    # Overall status
    critical_unhealthy = any(
        c["status"] == "unhealthy" and c["critical"]
        for c in health["components"].values()
    )
    
    if critical_unhealthy:
        health["status"] = "unhealthy"
        return JSONResponse(health, status_code=503)
    
    return health
```

---

## ⚖️ Trade-off Analysis

### Summary of Key Trade-offs

| Decision | Cost | Benefit | Rationale |
|----------|------|---------|-----------|
| **Remove IsHTTPS** | +109 FNs | Eliminate 100% HTTPS vulnerability | Error pattern > error count |
| **12% Gray Zone** | 12% need judge review | 88% automated | Balance automation vs quality |
| **LLM Judge** | 2-5s latency | Human-readable explanations | Only for gray zone (12%) |
| **SHAP on Base Estimator** | Approximate values | Explainability | Relative importance still correct |
| **Stub Judge Fallback** | Less sophisticated | Zero downtime | Service reliability > sophistication |
| **URL-Only Features** | No page content analysis | <50ms latency | Speed > marginal accuracy gain |

### Latency Budget

```
Target: P95 < 100ms for high-confidence decisions

Actual:
• Whitelist: <1ms (set lookup)
• ALLOW/BLOCK: 50-100ms (model inference)
• REVIEW: 2000-5000ms (LLM judge)

P95: 100ms ✅ (88% of traffic)
P99: 5000ms (12% gray zone)
```

**Trade-off:** Accept high P99 for explainability in gray zone.

### Accuracy vs Speed

```
Options Considered:

1. Ensemble (XGBoost + LogReg + RandomForest):
   • Accuracy: +0.5% PR-AUC
   • Latency: 3x slower
   • Decision: ❌ Not worth it

2. Deep Learning (BERT on URL text):
   • Accuracy: +1% PR-AUC (estimated)
   • Latency: 500ms+ (GPU required)
   • Decision: ❌ Over-engineered for URL-only

3. Single XGBoost + Isotonic Calibration:
   • Accuracy: 99.87% PR-AUC
   • Latency: 50ms
   • Decision: ✅ Sweet spot
```

---

## 🔮 Future Architecture Evolution

### Short-term (1-3 months)

**1. Prometheus Metrics + Grafana**
```
Metrics:
• phishguard_predictions_total{decision}
• phishguard_prediction_latency_seconds
• phishguard_judge_invocations_total{verdict, backend}

Dashboards:
• Decision distribution over time
• Latency percentiles (P50/P95/P99)
• Judge success rate
```

**2. Structured Logging with Request IDs**
```python
logger.info({
    "request_id": uuid4(),
    "event": "prediction",
    "url": url,
    "decision": decision,
    "p_malicious": p_malicious,
    "latency_ms": latency,
    "judge_invoked": bool(judge)
})
```

### Medium-term (3-6 months)

**1. Feature Drift Detection (PSI)**
```python
from scipy.stats import chisquare

def calculate_psi(baseline_dist, current_dist):
    """Population Stability Index"""
    psi = np.sum((current_dist - baseline_dist) * 
                 np.log(current_dist / baseline_dist))
    return psi

# Alert if PSI > 0.25 (significant shift)
```

**2. A/B Testing Framework**
```python
# Shadow mode: Run new model alongside production
if is_shadow_traffic(request):
    prod_result = prod_model.predict(features)
    shadow_result = shadow_model.predict(features)
    
    log_comparison(prod_result, shadow_result)
    
    return prod_result  # Only return prod
```

**3. Dynamic Threshold Tuning**
```python
# Adjust thresholds based on operational capacity
if judge_queue_length > 100:
    # Widen gray zone to reduce load
    thresholds.low *= 0.9
    thresholds.high *= 1.1
```

### Long-term (6-12 months)

**1. Page Content Features**
```python
# Optional: Fetch page content for high-risk cases
if p_malicious > 0.7 and p_malicious < 0.9:
    html_features = extract_html_features(url)
    combined_score = ensemble(url_features, html_features)
```

**2. Active Learning Pipeline**
```python
# Identify uncertain predictions for labeling
if 0.4 < p_malicious < 0.6:
    send_to_labeling_queue(url)
    
# Retrain weekly with new labels
```

**3. Multi-Model Ensemble**
```
URL-only model → p1
Page content model → p2  
User behavior model → p3

Final score = weighted_average([p1, p2, p3])
```

---

## 📚 Additional Resources

- **[README.md](../README.md)** - Project overview
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide
- **[API.md](API.md)** - API reference
- **[JUDGE.md](JUDGE.md)** - LLM judge deep dive

---

**Last Updated:** October 23, 2025  
**Version:** 1.0.0
