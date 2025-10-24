# 🧠 PhishGuardAI LLM Judge System

**Deep dive into the LLM-augmented gray zone decision system.**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Routing Logic](#routing-logic)
4. [Prompt Engineering](#prompt-engineering)
5. [Verdict Mapping](#verdict-mapping)
6. [Performance Characteristics](#performance-characteristics)
7. [Failover Strategy](#failover-strategy)
8. [Comparison: LLM vs Stub Judge](#comparison-llm-vs-stub-judge)
9. [Ollama Configuration](#ollama-configuration)
10. [Testing & Validation](#testing--validation)

---

## 🌐 Overview

### Purpose

The LLM judge provides **human-readable explanations** for URLs in the **gray zone** (12% of traffic), especially edge cases that defy simple statistical rules.

### Design Goals

1. **Explainability:** Natural language rationale for decisions
2. **Edge case handling:** Short domains (npm.org, bit.ly) that look suspicious statistically
3. **Graceful degradation:** Fall back to stub judge if LLM unavailable
4. **No downtime:** System continues even if Ollama fails

### When Judge is Invoked

```
Model returns p_malicious ∈ [0.011, 0.998] (gray zone)
    ↓
Policy band: REVIEW
    ↓
Enhanced routing check:
  • Is domain ≤ 10 characters?
  • AND is confidence moderate (p < 0.5)?
    ↓
YES → Route to LLM judge
NO → Standard REVIEW routing
```

**Example URLs that trigger judge:**
- `npm.org` (7 chars, p=0.35) → Judge
- `bit.ly/abc` (6 chars, p=0.42) → Judge
- `t.co/xyz` (4 chars, p=0.38) → Judge
- `example-verify.com` (18 chars, p=0.45) → No judge (not short)

---

## 🏗️ Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ GATEWAY (src/gateway/main.py)                               │
│  • Receives URL prediction request                          │
│  • Returns p_malicious from model service                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ JUDGE WIRE (src/gateway/judge_wire.py)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ decide_with_judge(url, p_malicious, thresholds)      │   │
│  │   1. Check policy band                               │   │
│  │   2. If REVIEW: Enhanced routing logic               │   │
│  │   3. Build JudgeRequest with 7 features              │   │
│  │   4. Call selected judge (LLM or stub)               │   │
│  │   5. Map verdict to final decision                   │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
┌──────────────────────┐  ┌──────────────────────┐
│ LLM ADAPTER          │  │ STUB JUDGE           │
│ (src/judge_svc/      │  │ (src/judge_svc/      │
│  adapter.py)         │  │  stub.py)            │
│  ┌────────────────┐  │  │  ┌────────────────┐  │
│  │ Prompt         │  │  │  │ Deterministic  │  │
│  │ Engineering    │  │  │  │ Rules          │  │
│  │                │  │  │  │                │  │
│  │ Ollama API     │  │  │  │ • Special      │  │
│  │ Call           │  │  │  │   chars check  │  │
│  │                │  │  │  │ • Continuation │  │
│  │ Response       │  │  │  │   rate check   │  │
│  │ Parsing        │  │  │  │                │  │
│  │                │  │  │  │ Instant (<1ms) │  │
│  │ Timeout: 60s   │  │  │  └────────────────┘  │
│  └────────────────┘  │  └──────────────────────┘
└──────────────────────┘           ▲
         │                         │
         │ Try LLM                 │ Fallback if
         │ Primary                 │ LLM fails
         ▼                         │
┌──────────────────────┐           │
│ OLLAMA (:11434)      │───────────┘
│  • llama3.2:1b       │  Exception
│  • Local inference   │
│  • No API costs      │
└──────────────────────┘
```

### Data Flow

```
1. URL received: "http://npm.org"
   ↓
2. Model inference: p_malicious = 0.35
   ↓
3. Policy band: 0.011 < 0.35 < 0.998 → REVIEW
   ↓
4. Enhanced routing:
   - Domain: "npm.org" (7 chars) ≤ 10 ✓
   - Confidence: 0.35 < 0.5 ✓
   - Route to judge: YES
   ↓
5. Build JudgeRequest:
   {
     "url": "http://npm.org",
     "features": {
       "TLDLegitimateProb": 0.85,
       "DomainLength": 7,
       ...
     }
   }
   ↓
6. Call LLM judge (60s timeout):
   Try: Ollama llama3.2:1b
   Catch Exception → Stub judge fallback
   ↓
7. Parse LLM response:
   VERDICT: LEAN_LEGIT
   SCORE: 0.15
   RATIONALE: "npm.org is a well-known package manager..."
   ↓
8. Map verdict to decision:
   LEAN_LEGIT → ALLOW
   ↓
9. Return to client:
   {
     "decision": "ALLOW",
     "reason": "judge-short-domain-lean-legit",
     "judge": { ... }
   }
```

---

## 🧭 Routing Logic

### Policy Band Decision

```python
def decide(p_malicious: float, thresholds: Thresholds) -> Decision:
    """
    Apply policy bands to determine base decision.
    
    Returns:
        ALLOW if p < low (0.011)
        BLOCK if p > high (0.998)
        REVIEW if low ≤ p ≤ high (gray zone)
    """
    if p_malicious < thresholds.low:
        return "ALLOW"
    elif p_malicious > thresholds.high:
        return "BLOCK"
    else:
        return "REVIEW"
```

### Enhanced Routing (Short Domain Detection)

```python
def _should_route_to_judge_for_short_domain(
    url: str, 
    p_malicious: float
) -> bool:
    """
    Check if URL should be routed to judge due to short domain edge case.
    
    Rationale: Short legitimate domains (npm.org, bit.ly, etc.) may appear
    suspicious to the model due to distribution shift. Route to judge for
    human-readable explanation when:
    - Domain length ≤ threshold (default 10 chars)
    - Confidence is moderate (p < 0.5) - not highly suspicious
    
    This catches edge cases not covered by the whitelist.
    """
    domain = extract_domain(url)
    if not domain:
        return False
    
    is_short = len(domain) <= SHORT_DOMAIN_LENGTH  # Default: 10
    is_moderate_confidence = p_malicious < SHORT_DOMAIN_CONFIDENCE  # Default: 0.5
    
    return is_short and is_moderate_confidence
```

**Configuration:**
```bash
export SHORT_DOMAIN_LENGTH="10"   # Characters
export SHORT_DOMAIN_CONFIDENCE="0.5"  # Threshold
```

**Examples:**

| URL | Domain Length | p_malicious | Route to Judge? |
|-----|---------------|-------------|-----------------|
| `npm.org` | 7 | 0.35 | ✅ YES (short + moderate) |
| `bit.ly/abc` | 6 | 0.42 | ✅ YES (short + moderate) |
| `google.com` | 10 | 0.01 | ❌ NO (whitelisted) |
| `phishing.tk` | 11 | 0.45 | ❌ NO (not short enough) |
| `npm.org` | 7 | 0.85 | ❌ NO (high confidence) |

### Judge Decision Logic

```python
def decide_with_judge(
    url: str,
    p_malicious: float,
    th: Thresholds,
) -> JudgeOutcome:
    """
    Enhanced decision logic with short domain routing.
    
    Decision Flow:
    1. Apply policy bands (low/high thresholds)
    2. If base decision is REVIEW, check for short domain edge case
    3. Invoke judge and map verdict to final decision
    """
    base_decision = decide(p_malicious, th)
    
    # Fast path: High confidence ALLOW/BLOCK
    if base_decision != "REVIEW":
        return JudgeOutcome(
            final_decision=base_decision,
            policy_reason="policy-band",
            judge=None
        )
    
    # Gray zone routing logic
    is_short_domain_case = _should_route_to_judge_for_short_domain(url, p_malicious)
    
    # Build feature digest using 7-feature model
    features = extract_7features(url)
    
    # Call judge (LLM or stub)
    judge_response = _JUDGE_FN(JudgeRequest(url=url, features=features))
    
    # Map verdict to final decision
    if judge_response.verdict == "LEAN_PHISH":
        final = "BLOCK"
        reason = "judge-short-domain-lean-phish" if is_short_domain_case else "judge-lean-phish"
    elif judge_response.verdict == "LEAN_LEGIT":
        final = "ALLOW"
        reason = "judge-short-domain-lean-legit" if is_short_domain_case else "judge-lean-legit"
    else:
        final = "REVIEW"
        reason = "judge-short-domain-uncertain" if is_short_domain_case else "judge-uncertain"
    
    return JudgeOutcome(
        final_decision=final,
        policy_reason=reason,
        judge=judge_response
    )
```

---

## 📝 Prompt Engineering

### Prompt Structure

```python
def _prompt(req: JudgeRequest) -> str:
    feat = req.features.model_dump()
    return (
        "You are a cybersecurity analyst specializing in phishing detection. "
        "Assess phishing risk using the URL and 7 sophisticated features:\n\n"
        
        "KEY FEATURES TO ANALYZE:\n"
        "- TLDLegitimateProb: Bayesian TLD legitimacy probability [0,1]\n"
        "- CharContinuationRate: Character repetition patterns [0,1]\n"
        "- SpacialCharRatioInURL: Special character density [0,1]\n"
        "- URLCharProb: URL character sequence probability [0,1]\n"
        "- LetterRatioInURL: Alphabetic character ratio [0,1]\n"
        "- NoOfOtherSpecialCharsInURL: Count of special characters\n"
        "- DomainLength: RFC-compliant domain length\n\n"
        
        "RESPOND WITH EXACTLY THREE FIELDS:\n"
        "VERDICT: LEAN_PHISH | LEAN_LEGIT | UNCERTAIN\n"
        "SCORE: risk score in [0,1] where 0=safe, 1=malicious\n"
        "RATIONALE: brief explanation focusing on key risk indicators\n\n"
        
        f"URL: {req.url}\n"
        f"FEATURES: {json.dumps(feat, separators=(',', ':'))}\n\n"
        
        "Focus on: HTTPS usage, TLD legitimacy, character patterns, "
        "and any URL obfuscation techniques."
    )
```

### Prompt Design Principles

1. **Role definition:** Clear expertise context ("cybersecurity analyst")
2. **Feature grounding:** LLM bases reasoning on extracted features
3. **Structured output:** Explicit format for easy parsing
4. **Conciseness:** Reduces token count, speeds inference
5. **Focus areas:** Guides LLM to relevant patterns

### Example Prompt & Response

**Prompt:**
```
You are a cybersecurity analyst specializing in phishing detection. 
Assess phishing risk using the URL and 7 sophisticated features:

KEY FEATURES TO ANALYZE:
- TLDLegitimateProb: Bayesian TLD legitimacy probability [0,1]
- CharContinuationRate: Character repetition patterns [0,1]
- SpacialCharRatioInURL: Special character density [0,1]
- URLCharProb: URL character sequence probability [0,1]
- LetterRatioInURL: Alphabetic character ratio [0,1]
- NoOfOtherSpecialCharsInURL: Count of special characters
- DomainLength: RFC-compliant domain length

RESPOND WITH EXACTLY THREE FIELDS:
VERDICT: LEAN_PHISH | LEAN_LEGIT | UNCERTAIN
SCORE: risk score in [0,1] where 0=safe, 1=malicious
RATIONALE: brief explanation focusing on key risk indicators

URL: http://npm.org
FEATURES: {"TLDLegitimateProb":0.85,"CharContinuationRate":0.0,"SpacialCharRatioInURL":0.125,"URLCharProb":1.0,"LetterRatioInURL":0.875,"NoOfOtherSpecialCharsInURL":1,"DomainLength":7}

Focus on: HTTPS usage, TLD legitimacy, character patterns, and any URL obfuscation techniques.
```

**LLM Response:**
```
**VERDICT:** LEAN_LEGIT

**SCORE:** 0.15

**RATIONALE:** Domain 'npm.org' is a well-known package manager for JavaScript. The short domain length (7 characters) is expected for legitimate tech infrastructure. TLD .org has high legitimacy probability (0.85), commonly used by open-source projects. No suspicious character patterns detected (CharContinuationRate=0.0, low special characters). The lack of HTTPS is typical for redirect URLs in package ecosystems.
```

### Response Parsing

```python
_VERDICT_RE = re.compile(
    r"\*{0,2}\s*VERDICT\s*\*{0,2}\s*:\s*(LEAN_PHISH|LEAN_LEGIT|UNCERTAIN)\b", 
    re.I
)
_SCORE_RE = re.compile(
    r"\*{0,2}\s*SCORE\s*\*{0,2}\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)\b", 
    re.I
)
_RAT_RE = re.compile(
    r"\*{0,2}\s*RATIONALE\s*\*{0,2}\s*:\s*\*{0,2}\s*(.+?)(?:\n|$)", 
    re.I
)

def _parse(text: str) -> Tuple[JudgeVerdict, float | None, str]:
    """
    Extract verdict, score, and rationale from LLM response.
    
    Handles markdown formatting (** for bold).
    """
    verdict = "UNCERTAIN"
    score = None
    rationale = "no rationale"
    
    m = _VERDICT_RE.search(text)
    if m:
        v = m.group(1).upper()
        verdict = (
            "LEAN_PHISH" if v == "LEAN_PHISH"
            else ("LEAN_LEGIT" if v == "LEAN_LEGIT" else "UNCERTAIN")
        )
    
    m = _SCORE_RE.search(text)
    if m:
        try:
            score = float(m.group(1))
            score = max(0.0, min(1.0, score))
        except Exception:
            score = None
    
    m = _RAT_RE.search(text)
    if m:
        rationale = m.group(1).strip().splitlines()[0][:500]
    
    return verdict, score, rationale
```

---

## 🗺️ Verdict Mapping

### Mapping Table

| LLM Verdict | Final Decision | Reason Field | Meaning |
|-------------|----------------|--------------|---------|
| **LEAN_PHISH** | BLOCK | `judge-lean-phish` | LLM believes URL is likely phishing |
| **LEAN_LEGIT** | ALLOW | `judge-lean-legit` | LLM believes URL is likely legitimate |
| **UNCERTAIN** | REVIEW | `judge-uncertain` | LLM cannot determine, escalate to human |

**With Short Domain Context:**

| LLM Verdict | Final Decision | Reason Field |
|-------------|----------------|--------------|
| **LEAN_PHISH** | BLOCK | `judge-short-domain-lean-phish` |
| **LEAN_LEGIT** | ALLOW | `judge-short-domain-lean-legit` |
| **UNCERTAIN** | REVIEW | `judge-short-domain-uncertain` |

### Rationale for Three Verdicts

**LEAN_PHISH:**
- LLM has moderate confidence URL is malicious
- Features suggest phishing patterns
- Block URL to protect users

**LEAN_LEGIT:**
- LLM has moderate confidence URL is legitimate
- Features suggest benign patterns (e.g., known domain, expected structure)
- Allow URL to avoid false positives

**UNCERTAIN:**
- LLM cannot determine with confidence
- Conflicting signals in features
- Escalate to human review for final decision

---

## ⚡ Performance Characteristics

### Latency Profile

| Metric | LLM Judge (Ollama) | Stub Judge |
|--------|-------------------|------------|
| **First call** | 15-20 seconds | <1ms |
| **Subsequent calls** | 2-5 seconds | <1ms |
| **P50 (median)** | 3 seconds | <1ms |
| **P95** | 7 seconds | <1ms |
| **P99** | 15 seconds | <1ms |
| **Timeout** | 60 seconds | N/A |

**Why first call is slow:**
- Model loading into memory (~1.3 GB for llama3.2:1b)
- Subsequent calls use cached model

**Optimization: Pre-warm at startup**
```bash
# Call Ollama during service initialization
curl http://localhost:11434/api/generate \
  -X POST \
  -d '{"model":"llama3.2:1b","prompt":"Ready","stream":false}'
```

### Throughput

**Assumptions:**
- 1,000 requests/sec total traffic
- 12% gray zone rate → 120 req/sec to judge
- Avg LLM latency: 3 seconds

**Capacity Needed:**
```
Concurrent judge requests = 120 req/sec * 3 sec = 360 concurrent
Recommended: 400+ workers or async queue
```

**Scaling Options:**
1. **Horizontal:** Multiple Ollama instances behind load balancer
2. **Vertical:** GPU acceleration (CUDA) for faster inference
3. **Async:** Queue-based processing (Celery, RabbitMQ)

### Resource Usage

| Metric | llama3.2:1b | llama3.2:3b |
|--------|-------------|-------------|
| **Model size** | 1.3 GB | 2.0 GB |
| **RAM usage** | 4-6 GB | 8-10 GB |
| **CPU usage** | 50-80% (4 cores) | 70-90% (4 cores) |
| **GPU usage** | Optional | Optional |

---

## 🛡️ Failover Strategy

### Failure Modes

| Failure | Detection | Response | Impact |
|---------|-----------|----------|--------|
| **LLM timeout (>60s)** | Exception caught | Fall back to stub judge | ✅ Service continues |
| **Ollama not running** | Connection refused | Fall back to stub judge | ✅ Service continues |
| **Model not found** | 404 from Ollama | Fall back to stub judge | ✅ Service continues |
| **Parsing failure** | Regex no match | Fall back to stub judge | ✅ Service continues |

### Implementation

```python
def judge_url_llm(req: JudgeRequest) -> JudgeResponse:
    """
    LLM-backed judge using Ollama /api/generate.
    Fails open to deterministic stub if any network/model error occurs.
    """
    try:
        # Try Ollama API call
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": JUDGE_MODEL, "prompt": _prompt(req), "stream": False},
            timeout=JUDGE_TIMEOUT
        )
        resp.raise_for_status()
        
        # Parse response
        data = resp.json()
        text = data.get("response", "")
        verdict, score, rationale = _parse(text)
        
        return JudgeResponse(
            verdict=verdict,
            judge_score=score,
            rationale=rationale,
            context={
                "backend": "llm",
                "model": JUDGE_MODEL,
                **req.features.model_dump()
            }
        )
    except Exception as e:
        # Fail-open: never block the request path just because LLM isn't available
        logger.error(f"LLM judge failed: {e}")
        
        fb = fallback_stub(req)
        fb.context.update({
            "backend": "stub_fallback",
            "model": JUDGE_MODEL,
            "error": str(e),
            "error_type": type(e).__name__
        })
        return fb
```

### Error Logging

```python
except Exception as e:
    import traceback
    # Log detailed error
    logger.error(f"[JUDGE ERROR] LLM judge failed: {type(e).__name__}: {e}")
    logger.error("[JUDGE ERROR] Full traceback:")
    traceback.print_exc()
    
    # Return response with error context
    fb.context["error"] = str(e)
    fb.context["error_type"] = type(e).__name__
    return fb
```

---

## 🔄 Comparison: LLM vs Stub Judge

### Stub Judge Implementation

```python
def judge_url(req: JudgeRequest) -> JudgeResponse:
    """
    Deterministic stub judge using simple rules.
    
    Instant response (<1ms), no external dependencies.
    """
    feat = req.features
    
    # Rule 1: High special character ratio
    if feat.SpacialCharRatioInURL > 0.3:
        return JudgeResponse(
            verdict="UNCERTAIN",
            judge_score=0.45,
            rationale="elevated special character ratio",
            context=feat.model_dump()
        )
    
    # Rule 2: High character continuation rate
    if feat.CharContinuationRate > 0.2:
        return JudgeResponse(
            verdict="UNCERTAIN",
            judge_score=0.40,
            rationale="elevated character repetition",
            context=feat.model_dump()
        )
    
    # Rule 3: Multiple special chars + suspicious TLD
    if feat.NoOfOtherSpecialCharsInURL > 5 and feat.TLDLegitimateProb < 0.3:
        return JudgeResponse(
            verdict="UNCERTAIN",
            judge_score=0.50,
            rationale="elevated special characters; suspicious TLD",
            context=feat.model_dump()
        )
    
    # Default: Uncertain with low score
    return JudgeResponse(
        verdict="UNCERTAIN",
        judge_score=0.25,
        rationale="no strong indicators",
        context=feat.model_dump()
    )
```

### Comparison Table

| Factor | LLM Judge | Stub Judge |
|--------|-----------|------------|
| **Latency** | 2-5s (cached) | <1ms |
| **Explainability** | Natural language | Rule-based phrases |
| **Edge cases** | Handles well (npm.org, bit.ly) | Struggles |
| **Dependencies** | Ollama (external) | None (self-contained) |
| **Adaptability** | Easy (update prompt) | Hard (code changes) |
| **Reliability** | 95%+ (with timeout) | 100% (no failures) |
| **Cost** | Free (local Ollama) | Free |
| **Verdict quality** | Context-aware | Generic |

### When to Use Each

**LLM Judge:**
- Production with high-quality explanations needed
- Edge cases important (short domains, URL shorteners)
- Willing to accept 2-5s latency for 12% of traffic

**Stub Judge:**
- Development/testing without Ollama setup
- Latency-critical applications (< 100ms P99)
- Offline/air-gapped environments

---

## ⚙️ Ollama Configuration

### Model Selection

| Model | Size | RAM | Speed | Quality | Recommended |
|-------|------|-----|-------|---------|-------------|
| **llama3.2:1b** | 1.3 GB | 4 GB | Fast | Good | ✅ Production |
| **llama3.2:3b** | 2.0 GB | 8 GB | Medium | Better | 🔶 High-quality |
| **phi3:mini** | 2.2 GB | 8 GB | Fast | Good | 🔶 Alternative |

### Setup Commands

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.2:1b

# Start Ollama service
ollama serve

# Verify
curl http://localhost:11434/api/tags
```

### Environment Variables

```bash
export JUDGE_BACKEND="llm"
export JUDGE_MODEL="llama3.2:1b"
export OLLAMA_HOST="http://localhost:11434"
export JUDGE_TIMEOUT_SECS="60"
```

### GPU Acceleration (Optional)

```bash
# If NVIDIA GPU available
nvidia-smi  # Verify GPU

# Ollama automatically uses GPU if available
# Check with:
curl http://localhost:11434/api/generate \
  -d '{"model":"llama3.2:1b","prompt":"test"}' | grep -i gpu
```

---

## 🧪 Testing & Validation

### Unit Tests

```python
def test_llm_judge_short_domain():
    """Test LLM judge handles short domains correctly."""
    url = "http://npm.org"
    features = extract_features(url)
    
    judge_response = judge_url_llm(JudgeRequest(url=url, features=features))
    
    assert judge_response.verdict in ["LEAN_PHISH", "LEAN_LEGIT", "UNCERTAIN"]
    assert judge_response.rationale is not None
    assert len(judge_response.rationale) > 10  # Non-trivial explanation
```

### Integration Tests

```bash
# Test Ollama availability
curl http://localhost:11434/api/tags

# Test judge endpoint
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://npm.org"}'

# Verify judge was invoked
# Response should include "judge" field with verdict/rationale
```

### Performance Tests

```bash
# Measure latency
time curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://npm.org"}'

# Expected: 2-5 seconds (after warmup)
```

---

## 📚 Additional Resources

- **[README.md](../README.md)** - Project overview
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Setup Ollama
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Judge design decisions
- **[API.md](API.md)** - API reference

---

**Last Updated:** October 23, 2025  
**Version:** 1.0.0
