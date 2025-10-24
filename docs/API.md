# 📡 PhishGuardAI API Reference

**Complete API documentation for all PhishGuardAI endpoints.**

---

## 📋 Table of Contents

1. [Base URLs](#base-urls)
2. [Authentication](#authentication)
3. [Prediction Endpoints](#prediction-endpoints)
4. [Explainability Endpoints](#explainability-endpoints)
5. [Observability Endpoints](#observability-endpoints)
6. [Error Responses](#error-responses)
7. [Rate Limiting](#rate-limiting)
8. [Example Workflows](#example-workflows)

---

## 🌐 Base URLs

| Environment | Base URL |
|-------------|----------|
| **Local Development** | `http://localhost:8000` |
| **Docker Compose** | `http://gateway:8000` |
| **Production** | `https://phishguard.example.com` |

---

## 🔐 Authentication

**Current Status:** No authentication required (local development)

**Planned:** API key authentication via `X-API-Key` header

```bash
# Future implementation
curl -X POST "https://api.phishguard.com/predict" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://example.com"}'
```

---

## 🎯 Prediction Endpoints

### `POST /predict`

Classify a URL as legitimate, phishing, or uncertain.

**Request Body:**

```json
{
  "url": "string"  // Required: URL to analyze
}
```

**Response (200 OK):**

```json
{
  "url": "string",           // Analyzed URL
  "decision": "string",      // ALLOW | REVIEW | BLOCK
  "reason": "string",        // Decision rationale
  "p_malicious": "float",    // Phishing probability [0,1]
  "source": "string",        // whitelist | model
  "model_name": "string",    // Model identifier
  "features": {              // Extracted features
    "TLDLegitimateProb": "float",
    "CharContinuationRate": "float",
    "SpacialCharRatioInURL": "float",
    "URLCharProb": "float",
    "LetterRatioInURL": "float",
    "NoOfOtherSpecialCharsInURL": "int",
    "DomainLength": "int"
  },
  "judge": {                 // Present if gray zone
    "verdict": "string",     // LEAN_PHISH | LEAN_LEGIT | UNCERTAIN
    "rationale": "string",   // Human-readable explanation
    "judge_score": "float",  // Judge confidence [0,1]
    "context": {
      "backend": "string",   // llm | stub_fallback
      "model": "string"      // LLM model name
    }
  }
}
```

**Examples:**

**Example 1: Whitelisted Domain**

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com"}'
```

```json
{
  "url": "https://github.com",
  "decision": "ALLOW",
  "reason": "domain-whitelist",
  "p_malicious": 0.01,
  "source": "whitelist",
  "features": null,
  "judge": null
}
```

**Example 2: High-Confidence Phishing**

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://verify-account-urgent.tk"}'
```

```json
{
  "url": "http://verify-account-urgent.tk",
  "decision": "BLOCK",
  "reason": "policy-band",
  "p_malicious": 0.9995,
  "source": "model",
  "model_name": "7-feature-production-v1",
  "features": {
    "TLDLegitimateProb": 0.12,
    "CharContinuationRate": 0.08,
    "SpacialCharRatioInURL": 0.19,
    "URLCharProb": 1.0,
    "LetterRatioInURL": 0.81,
    "NoOfOtherSpecialCharsInURL": 5,
    "DomainLength": 24
  },
  "judge": null
}
```

**Example 3: Gray Zone with Judge**

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://npm.org"}'
```

```json
{
  "url": "http://npm.org",
  "decision": "ALLOW",
  "reason": "judge-short-domain-lean-legit",
  "p_malicious": 0.35,
  "source": "model",
  "model_name": "7-feature-production-v1",
  "features": {
    "TLDLegitimateProb": 0.85,
    "CharContinuationRate": 0.0,
    "SpacialCharRatioInURL": 0.125,
    "URLCharProb": 1.0,
    "LetterRatioInURL": 0.875,
    "NoOfOtherSpecialCharsInURL": 1,
    "DomainLength": 7
  },
  "judge": {
    "verdict": "LEAN_LEGIT",
    "rationale": "Domain 'npm.org' is a well-known package manager. Short domain length (7 chars) is expected for legitimate tech infrastructure. TLD .org is commonly used by open-source projects.",
    "judge_score": 0.15,
    "context": {
      "backend": "llm",
      "model": "llama3.2:1b",
      "is_short_domain_case": true
    }
  }
}
```

**Error Responses:**

```json
// 400 Bad Request - Missing URL
{
  "error": "Missing required field: url"
}

// 422 Unprocessable Entity - Invalid URL
{
  "error": "Invalid URL format"
}

// 503 Service Unavailable - Model service down
{
  "error": "Model service unavailable",
  "retry_after": 60
}
```

---

## 🔍 Explainability Endpoints

### `POST /predict/explain`

Get SHAP feature importance values for a URL prediction.

**Request Body:**

```json
{
  "url": "string"  // Required: URL to explain
}
```

**Response (200 OK):**

```json
{
  "url": "string",
  "p_malicious": "float",
  "base_value": "float",        // Model baseline
  "features": {
    "feature_name": {
      "value": "float",          // Actual feature value
      "shap_value": "float",     // SHAP contribution
      "importance": "float"      // |shap_value|
    }
  },
  "top_features": ["string"],    // Top 3 by importance
  "model_name": "string",
  "explanation": "string",
  "note": "string"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/predict/explain" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://suspicious-login.info"}'
```

```json
{
  "url": "http://suspicious-login.info",
  "p_malicious": 0.8542,
  "base_value": 0.318,
  "features": {
    "CharContinuationRate": {
      "value": 0.1,
      "shap_value": -0.523,
      "importance": 0.523
    },
    "NoOfOtherSpecialCharsInURL": {
      "value": 6,
      "shap_value": 0.342,
      "importance": 0.342
    },
    "TLDLegitimateProb": {
      "value": 0.43,
      "shap_value": -0.026,
      "importance": 0.026
    },
    "SpacialCharRatioInURL": {
      "value": 0.19,
      "shap_value": 0.145,
      "importance": 0.145
    },
    "URLCharProb": {
      "value": 1.0,
      "shap_value": 0.0,
      "importance": 0.0
    },
    "LetterRatioInURL": {
      "value": 0.81,
      "shap_value": 0.089,
      "importance": 0.089
    },
    "DomainLength": {
      "value": 21,
      "shap_value": -0.042,
      "importance": 0.042
    }
  },
  "top_features": [
    "CharContinuationRate",
    "NoOfOtherSpecialCharsInURL",
    "SpacialCharRatioInURL"
  ],
  "model_name": "7-feature-production-v1",
  "explanation": "Positive SHAP values push towards phishing; negative towards legitimate",
  "note": "SHAP computed on base estimator (before calibration) for approximate feature importance"
}
```

**Error Responses:**

```json
// 500 Internal Server Error - SHAP computation failed
{
  "error": "SHAP explanation failed: <error_message>",
  "details": "<traceback>"
}

// 503 Service Unavailable - SHAP not installed
{
  "error": "SHAP not installed. Install with: pip install shap"
}
```

**Dashboard Access:**

```bash
# Visual SHAP dashboard
open http://localhost:8000/explain
```

---

## 📊 Observability Endpoints

### `GET /health`

Service health check.

**Response (200 OK):**

```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_service": "connected",
  "judge_backend": "llm",
  "timestamp": "2025-10-23T12:34:56Z"
}
```

**Response (503 Service Unavailable):**

```json
{
  "status": "unhealthy",
  "model_loaded": false,
  "model_service": "disconnected",
  "timestamp": "2025-10-23T12:34:56Z"
}
```

---

### `GET /stats`

Decision statistics.

**Response (200 OK):**

```json
{
  "policy": {
    "ALLOW": 5234,     // Policy band ALLOWs
    "REVIEW": 678,     // Policy band REVIEWs
    "BLOCK": 3421      // Policy band BLOCKs
  },
  "judge": {
    "LEAN_PHISH": 234,    // Judge phishing verdicts
    "LEAN_LEGIT": 312,    // Judge legitimate verdicts
    "UNCERTAIN": 132      // Judge uncertain verdicts
  },
  "final": {
    "ALLOW": 5546,     // Final ALLOWs (policy + judge)
    "REVIEW": 132,     // Final REVIEWs (human escalation)
    "BLOCK": 3655      // Final BLOCKs (policy + judge)
  },
  "uptime_seconds": 3600
}
```

---

### `GET /config`

Current configuration.

**Response (200 OK):**

```json
{
  "thresholds": {
    "low": 0.011,
    "high": 0.998,
    "optimal": 0.5
  },
  "model_name": "7-feature-production-v1",
  "judge_backend": "llm",
  "judge_model": "llama3.2:1b",
  "gray_zone_rate": 0.12
}
```

---

## ❌ Error Responses

### Standard Error Format

```json
{
  "error": "string",      // Human-readable error message
  "details": "string",    // Optional: Additional context
  "timestamp": "string"   // ISO 8601 timestamp
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| **200** | OK | Successful request |
| **400** | Bad Request | Missing required field, invalid JSON |
| **422** | Unprocessable Entity | Invalid URL format |
| **500** | Internal Server Error | Model inference error, SHAP failure |
| **503** | Service Unavailable | Model service down, dependencies missing |

---

## 🚦 Rate Limiting

**Current Status:** No rate limiting (local development)

**Planned:**

```
Rate Limit: 100 requests/minute per IP
Headers:
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 95
  X-RateLimit-Reset: 1698012000
```

**Response (429 Too Many Requests):**

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## 🎬 Example Workflows

### Workflow 1: Basic URL Scanning

```bash
#!/bin/bash

# Scan a list of URLs
urls=(
  "https://google.com"
  "http://phishing-site.tk"
  "http://npm.org"
)

for url in "${urls[@]}"; do
  echo "Scanning: $url"
  
  response=$(curl -s -X POST "http://localhost:8000/predict" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\"}")
  
  decision=$(echo $response | jq -r '.decision')
  p_malicious=$(echo $response | jq -r '.p_malicious')
  
  echo "  Decision: $decision (p=$p_malicious)"
  echo ""
done
```

**Output:**
```
Scanning: https://google.com
  Decision: ALLOW (p=0.01)

Scanning: http://phishing-site.tk
  Decision: BLOCK (p=0.9995)

Scanning: http://npm.org
  Decision: ALLOW (p=0.35)
```

### Workflow 2: Bulk Scanning with Explanations

```python
import requests
import json

def scan_url(url: str):
    """Scan URL and get SHAP explanation if suspicious."""
    
    # Get prediction
    response = requests.post(
        "http://localhost:8000/predict",
        json={"url": url}
    )
    result = response.json()
    
    # If suspicious, get explanation
    if result["p_malicious"] > 0.5:
        explain_response = requests.post(
            "http://localhost:8000/predict/explain",
            json={"url": url}
        )
        result["shap"] = explain_response.json()
    
    return result

# Scan URLs
urls = [
    "http://example-shop.com",
    "http://verify-account.tk",
    "http://bit.ly/abc123"
]

for url in urls:
    result = scan_url(url)
    print(f"URL: {url}")
    print(f"  Decision: {result['decision']}")
    print(f"  p_malicious: {result['p_malicious']:.4f}")
    
    if "shap" in result:
        top_features = result["shap"]["top_features"]
        print(f"  Top features: {', '.join(top_features)}")
    print()
```

### Workflow 3: Monitoring Dashboard

```bash
# Get stats every 5 seconds
watch -n 5 'curl -s http://localhost:8000/stats | jq .'
```

**Output:**
```json
{
  "policy": {
    "ALLOW": 5234,
    "REVIEW": 678,
    "BLOCK": 3421
  },
  "judge": {
    "LEAN_PHISH": 234,
    "LEAN_LEGIT": 312,
    "UNCERTAIN": 132
  },
  "final": {
    "ALLOW": 5546,
    "REVIEW": 132,
    "BLOCK": 3655
  },
  "uptime_seconds": 3600
}
```

---

## 📚 Additional Resources

- **[README.md](../README.md)** - Project overview
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Design decisions
- **[JUDGE.md](JUDGE.md)** - LLM judge system

---

**Last Updated:** October 23, 2025  
**Version:** 1.0.0
