# 🎬 PhishGuardAI - 5-Minute Demo Script

**Purpose:** Demonstrate all system capabilities in a structured, repeatable walkthrough.  
**Duration:** 5 minutes  
**Audience:** Technical interviewers (data scientists, platform engineers, analytics leaders)

---

## 🚀 Setup (30 seconds)

### Terminal 1: Model Service
```bash
python -m model_svc.main
```

**Wait for:**
```
✓ Loaded model from models/dev/model_8feat.pkl
✓ Model Service Ready
INFO:     Uvicorn running on http://0.0.0.0:9000
```

### Terminal 2: Gateway Service
```bash
# Windows
set MODEL_SVC_URL=http://localhost:9000

# Linux/Mac
export MODEL_SVC_URL=http://localhost:9000

python -m gateway.main
```

**Wait for:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 📊 Demo Path

### Test 1: Whitelist Fast Path (30 seconds)

**Talking Point:**  
> "First, let's test the whitelist fast-path. This handles out-of-distribution domains—major tech companies not in our 2019-2020 training data. Notice the O(1) lookup bypasses the model entirely."

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com"}'
```

**Expected Output:**
```json
{
  "url": "https://github.com",
  "p_malicious": 0.01,
  "decision": "ALLOW",
  "reason": "domain-whitelist",
  "source": "whitelist",
  "judge": null
}
```

**Key Points:**
- ✅ `source: whitelist` - Model never called
- ✅ `reason: domain-whitelist` - Inherently explainable
- ✅ Sub-10ms latency (show in logs if available)

---

### Test 2: High Confidence Phishing → Auto-Block (30 seconds)

**Talking Point:**  
> "Now a clear phishing URL. Notice `phishing.top` has obvious patterns: suspicious TLD (.top has low legitimacy), 'phishing' keyword in domain. The model predicts p=1.0 and the policy band automatically blocks it without consulting the judge."

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"https://phishing.top"}'
```

**Expected Output:**
```json
{
  "url": "https://phishing.top",
  "p_malicious": 1.0,
  "decision": "BLOCK",
  "reason": "policy-band",
  "source": "model",
  "judge": null
}
```

**Key Points:**
- ✅ `p_malicious: 1.0` - Model is confident
- ✅ `reason: policy-band` - Automated decision (no human review)
- ✅ `source: model` - 8-feature XGBoost prediction
- ✅ This is part of our 89% automation rate

---

### Test 3: Legitimate Domain → Auto-Allow (30 seconds)

**Talking Point:**  
> "Let's test a legitimate domain not on the whitelist. example.com is short (11 chars), but the model correctly identifies it as safe based on URL morphology."

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

**Expected Output:**
```json
{
  "url": "https://example.com",
  "p_malicious": 0.01,
  "decision": "ALLOW",
  "reason": "domain-whitelist",
  "source": "whitelist",
  "judge": null
}
```

**Key Points:**
- ✅ Low p_malicious (if not whitelisted, should be <0.004)
- ✅ Auto-ALLOW via policy band or whitelist
- ✅ Part of our 0.09% false positive rate

---

### Test 4: Enhanced Short Domain Routing (1 minute)

**Talking Point:**  
> "This is one of my favorite features: enhanced short domain routing. npm.org is only 7 characters—short domains are edge cases because they're underrepresented in training data. Even though the model gives moderate confidence (p=0.35), our routing logic detects `len(domain) <= 10` and escalates to the judge. This prevents false positives on legitimate URL shorteners like bit.ly or npm.org."

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"https://npm.org","p_malicious":0.35}'
```

**Expected Output:**
```json
{
  "url": "https://npm.org",
  "p_malicious": 0.35,
  "decision": "ALLOW",
  "reason": "judge-short-domain-lean-legit",
  "judge": {
    "verdict": "LEAN_LEGIT",
    "rationale": "no obvious phishing heuristics triggered",
    "judge_score": 0.0,
    "context": {
      "url_len": 15,
      "url_digit_ratio": 0.0,
      "url_subdomains": 0,
      "TLDLegitimateProb": null
    }
  },
  "source": "model"
}
```

**Key Points:**
- ✅ `reason: judge-short-domain-lean-legit` - Enhanced routing triggered
- ✅ Judge provides **explainable rationale** (not just probability)
- ✅ Prevents FPs on legitimate shorteners (bit.ly, t.co, npm.org)
- ✅ This is **domain knowledge encoded into the decision flow**

**Follow-up Question to Anticipate:**
> "Why not just retrain the model on short domains?"

**Answer:**
> "We could, but that requires constant retraining as new shorteners emerge. The routing logic is more flexible—we can add npm.org, t.co, etc. to the short domain detection without retraining. It's a production ML Ops pattern: encode domain knowledge in the decision pipeline, not just in the model."

---

### Test 5: Stats Monitoring (30 seconds)

**Talking Point:**  
> "We track decision distributions for observability. In production, this feeds into Prometheus and Grafana. Notice the split between `policy_decisions` (what the policy bands recommended) and `final_decisions` (what was actually returned after judge intervention). This lets us measure judge override rates."

```bash
curl http://localhost:8000/stats
```

**Expected Output:**
```json
{
  "policy_decisions": {
    "ALLOW": 2,
    "REVIEW": 1,
    "BLOCK": 1
  },
  "final_decisions": {
    "ALLOW": 3,
    "BLOCK": 1
  },
  "judge_verdicts": {
    "LEAN_LEGIT": 1,
    "UNCERTAIN": 0,
    "LEAN_PHISH": 0
  }
}
```

**Key Points:**
- ✅ Tracks policy vs final decisions
- ✅ Judge verdict distribution
- ✅ In production: feeds Prometheus for alerting

---

### Test 6: SHAP Explainability Dashboard (2 minutes)

**Talking Point:**  
> "Finally, let me show you the SHAP explainability dashboard—one of our key differentiators for regulatory compliance and trust."

**Open browser:** `http://localhost:8000/explain`

#### Example 1: Clear Phishing (30 seconds)
**Enter:** `http://facebook1mob.com`

**Point out:**
- 🔴 **100% malicious** - High-risk prediction
- 🔴 **IsHTTPS (green bar, negative SHAP)**: Missing HTTPS strongly indicates phishing
- 🔴 **NoOfOtherSpecialChars (red bar, positive SHAP)**: The '1' in "facebook1mob" is typosquatting
- ✅ **Feature values table**: Shows raw extractions (IsHTTPS=0, DomainLength=20, etc.)

**Talking Point:**
> "SHAP shows which features drove the decision. IsHTTPS being 0 (missing HTTPS) has a large negative impact—it strongly pushes the prediction toward phishing. The '1' in facebook1mob is a typosquatting pattern the model learned. This is critical for compliance: regulators want to know WHY a URL was blocked, not just the probability."

#### Example 2: Legitimate Domain (30 seconds)
**Enter:** `https://www.circlek.org`

**Point out:**
- 🟢 **0.1% malicious** - Low-risk prediction
- 🟢 **DomainLength (green bar, negative SHAP)**: Moderate length (15 chars) is protective
- 🔴 **CharContinuationRate (red bar, positive SHAP)**: "circlek" has slight character repetition, but overall safe
- ✅ **Net result**: Legitimate despite minor suspicious signals

**Talking Point:**
> "SHAP explains why this is safe despite some red flags. DomainLength (15 chars) is protective—phishing URLs are often extremely short or extremely long. The slight CharContinuationRate increase from 'circlek' isn't enough to overcome the protective signals."

#### Example 3: Whitelisted Domain (30 seconds)
**Enter:** `https://github.com/microsoft/vscode`

**Point out:**
- 🟢 **1.0% malicious** (whitelisted)
- ℹ️ **"No feature contributions available (whitelist match)"**
- ✅ Model was never called → No SHAP values to compute

**Talking Point:**
> "For whitelisted domains, the model is never called, so there are no SHAP values. The explanation is inherently simple: 'It's GitHub—we trust it.' This demonstrates our two-tier explainability: whitelist decisions are inherently explainable, and model decisions get SHAP feature attributions."

---

## 🎯 Key Metrics to Mention

**Memorize these numbers:**
- **99.92% PR-AUC** - Near-perfect precision-recall tradeoff
- **0.09% False Positive Rate** - 23 FPs out of 26,970 legitimate URLs
- **89% Automation** - Policy bands handle most decisions without manual review
- **11% Gray Zone** - Escalated to judge for explainable review
- **8 Features** - URL-only (no page fetching), <50ms inference
- **47,074 URLs** - PhiUSIIL training dataset

---

## 🧠 Anticipated Questions & Answers

### Q: "What's the latency?"
**A:**  
> "Whitelist path is <10ms (O(1) lookup). Model path is ~20-50ms (feature extraction + XGBoost inference). Judge path is ~50-100ms. We have a known performance bottleneck (2s p95) that's documented as future optimization work—root cause analysis is pending, likely model loading issue."

### Q: "How do you handle distribution shift?"
**A:**  
> "Three mechanisms: (1) Whitelist handles out-of-distribution major tech companies. (2) Enhanced routing logic catches short domain edge cases. (3) Future work: PSI (Population Stability Index) monitoring to detect feature drift and trigger retraining."

### Q: "What if the judge is wrong?"
**A:**  
> "The judge is a rule-based system (deterministic stub) with optional LLM upgrade via Ollama. The stub never fails—it's pure Python logic. The LLM adapter has automatic fallback if Ollama is down. This fail-secure design ensures the system never returns 500 errors. In production, we'd implement a feedback loop where security teams can label judge decisions to improve the heuristics."

### Q: "How would you deploy this at Helcim scale?"
**A:**  
> "Multi-phase rollout: (1) Shadow mode for 2 weeks—log predictions but don't act, compare to existing system. (2) Canary deployment—5% traffic → 25% → 50% → 100%. (3) Full production with Kubernetes autoscaling (target: 500 req/sec per pod), Prometheus metrics, PagerDuty alerts for latency p99 > 200ms or FP rate > 0.2%. Security hardening: rate limiting (100 req/sec per API key), JWT authentication, secrets management via Vault."

### Q: "What's your biggest lesson from this project?"
**A:**  
> "Training/serving skew—I discovered that feature extraction in production didn't match training. The training notebook used PhiUSIIL's pre-computed features, but my production service had custom logic. Small differences (how to count special chars, calculate ratios) led to wildly wrong predictions. I fixed it by creating a shared feature library (`src/common/feature_extraction.py`) and using it in BOTH training and serving. This taught me: feature extraction is code, not notebooks. Always validate end-to-end consistency."

---

## ✅ Post-Demo Checklist

**After the demo, be ready to:**
- [ ] Walk through code if they want technical depth
- [ ] Explain any design decision (policy bands, thresholds, whitelist, etc.)
- [ ] Discuss how this applies to Helcim's fraud detection needs
- [ ] Show notebooks if they want to see training process
- [ ] Explain Great Expectations data contracts
- [ ] Discuss Docker deployment strategy

**Don't:**
- ❌ Apologize for known limitations (frame as "future work")
- ❌ Say "I would have done X differently" (own your decisions)
- ❌ Over-explain (let them ask questions)

**Do:**
- ✅ Be enthusiastic about the SHAP dashboard (it's your differentiator)
- ✅ Connect everything to Helcim's payment fraud use case
- ✅ Use concrete numbers (99.92% PR-AUC, not "the model is accurate")
- ✅ Tell the training/serving skew story if there's time

---

## 🎬 Demo Complete!

**Total time:** 5 minutes  
**Tests run:** 6 (whitelist, phishing, legitimate, short domain, stats, SHAP)  
**Key systems demonstrated:** Gateway, Model Service, Judge, SHAP Dashboard  
**Key concepts covered:** Whitelist, Policy Bands, Enhanced Routing, Explainability, Observability  

**You're ready!** 🚀

---

## 📞 Questions During Demo?

**If they ask to see code:**
```bash
# Show gateway logic
code src/gateway/main.py

# Show model service
code src/model_svc/main.py

# Show feature extraction
code src/common/feature_extraction.py
```

**If they ask about testing:**
```bash
pytest -v tests/
```

**If they ask about Docker:**
```bash
docker build -f docker/gateway.Dockerfile -t phishguard:demo .
docker run --rm -p 8000:8000 phishguard:demo
```

---

**Pro tip:** Run through this demo 2-3 times before the interview. Practice your talking points out loud. Know what to say while waiting for curl responses (don't let silence hang).

**Remember:** Confidence comes from preparation. You've built something impressive—now show it off! 💪
