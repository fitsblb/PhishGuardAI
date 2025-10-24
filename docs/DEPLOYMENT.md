# 🚀 PhishGuardAI Deployment Guide

**Complete guide for deploying PhishGuardAI in local, staging, and production environments.**

---

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Local Development Setup](#local-development-setup)
3. [Environment Variables](#environment-variables)
4. [Ollama LLM Judge Setup](#ollama-llm-judge-setup)
5. [Docker Deployment](#docker-deployment)
6. [Health Checks](#health-checks)
7. [Monitoring & Observability](#monitoring--observability)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)

---

## 💻 System Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Disk** | 5 GB free | 20+ GB free |
| **OS** | Linux, macOS, Windows 10+ | Linux (Ubuntu 22.04+) |
| **Python** | 3.11.0 | 3.11.5+ |
| **Docker** | 20.10+ (optional) | Latest |

### For Ollama LLM Judge (Optional)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16+ GB |
| **Disk** | +2 GB (model) | +5 GB |
| **GPU** | Not required | NVIDIA GPU (CUDA) for faster inference |

---

## 🛠️ Local Development Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/fitsblb/PhishGuardAI.git
cd PhishGuardAI
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3.11 -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows PowerShell
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; import xgboost; import shap; print('✅ Dependencies installed')"
```

### Step 4: Download Model

```bash
# Model should be in models/ directory
ls -lh models/7_features_xgb_isotonic_prod.pkl

# If missing, download from releases or retrain:
# python notebooks/01_baseline_and_calibration.ipynb
```

### Step 5: Start Services

#### Terminal 1: Model Service

```bash
# Set environment
export MODEL_PATH="models/7_features_xgb_isotonic_prod.pkl"

# Start model service
uvicorn src.model_svc.main:app --host 0.0.0.0 --port 8002 --reload

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8002
```

#### Terminal 2: Gateway Service

```bash
# Set environment
export MODEL_SVC_URL="http://localhost:8002"
export THRESHOLDS_JSON="configs/dev/thresholds.json"
export JUDGE_BACKEND="stub"  # Use "llm" after Ollama setup

# Start gateway
uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status":"healthy","model_loaded":true}

# Test prediction
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://phishing-example.com"}'

# Expected: {"decision":"BLOCK","p_malicious":0.99,...}
```

---

## 🔐 Environment Variables

### Model Service

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MODEL_PATH` | ✅ | None | Path to pickled model file |
| `TLD_PROBS_PATH` | ❌ | `data/tld_probs.json` | TLD probability lookup table |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level (DEBUG, INFO, WARNING) |

### Gateway Service

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MODEL_SVC_URL` | ✅ | None | Model service URL |
| `THRESHOLDS_JSON` | ✅ | None | Path to thresholds config |
| `JUDGE_BACKEND` | ❌ | `stub` | Judge type: `stub` or `llm` |
| `CORS_ORIGINS` | ❌ | `["http://localhost:8000"]` | Allowed CORS origins |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |

### Judge Service (LLM)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JUDGE_MODEL` | ❌ | `llama3.2:1b` | Ollama model name |
| `OLLAMA_HOST` | ❌ | `http://localhost:11434` | Ollama API URL |
| `JUDGE_TIMEOUT_SECS` | ❌ | `60` | LLM request timeout (seconds) |
| `SHORT_DOMAIN_LENGTH` | ❌ | `10` | Short domain threshold (chars) |
| `SHORT_DOMAIN_CONFIDENCE` | ❌ | `0.5` | Confidence threshold for short domains |

### Optional: Audit Logging (MongoDB)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_URI` | ❌ | None | MongoDB connection string |
| `MONGO_DB` | ❌ | `phishguard` | Database name |

**Example:**
```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="phishguard_prod"
```

### Complete Example (.env file)

```bash
# Model Service
MODEL_PATH=models/7_features_xgb_isotonic_prod.pkl
TLD_PROBS_PATH=data/tld_probs.json
LOG_LEVEL=INFO

# Gateway Service
MODEL_SVC_URL=http://localhost:8002
THRESHOLDS_JSON=configs/dev/thresholds.json
JUDGE_BACKEND=llm
CORS_ORIGINS=["http://localhost:8000","https://phishguard.example.com"]

# LLM Judge
JUDGE_MODEL=llama3.2:1b
OLLAMA_HOST=http://localhost:11434
JUDGE_TIMEOUT_SECS=60
SHORT_DOMAIN_LENGTH=10
SHORT_DOMAIN_CONFIDENCE=0.5

# Optional: Audit Logging
# MONGO_URI=mongodb://localhost:27017
# MONGO_DB=phishguard
```

---

## 🤖 Ollama LLM Judge Setup

### Why Ollama?

- **Local inference:** No API costs, data privacy
- **Fast:** 2-5s per inference (after warmup)
- **Explainable:** Human-readable rationale for edge cases
- **Graceful fallback:** System continues with stub judge if Ollama unavailable

### Installation

#### Linux/macOS

```bash
# Download Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

#### Windows

1. Download from [ollama.com/download](https://ollama.com/download)
2. Run installer
3. Verify: `ollama --version` in PowerShell

### Model Selection

| Model | Size | RAM | Speed | Quality |
|-------|------|-----|-------|---------|
| **llama3.2:1b** ✅ | 1.3 GB | 4 GB | Fast (2-5s) | Good |
| **llama3.2:3b** | 2.0 GB | 8 GB | Medium (5-10s) | Better |
| **phi3:mini** | 2.2 GB | 8 GB | Fast (3-6s) | Good |

**Recommended:** `llama3.2:1b` for best balance of speed/quality.

### Setup Steps

#### 1. Pull Model

```bash
# Pull recommended model
ollama pull llama3.2:1b

# Verify
ollama list

# Expected output:
# NAME              SIZE
# llama3.2:1b       1.3 GB
```

#### 2. Start Ollama Service

```bash
# Start Ollama (keep this running)
ollama serve

# Expected output:
# Listening on 127.0.0.1:11434
```

#### 3. Test Ollama

```bash
# Test direct API call
curl http://localhost:11434/api/generate \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "prompt": "Say hello",
    "stream": false
  }'

# Expected: JSON response with "response" field
```

#### 4. Configure Gateway

```bash
# Terminal 2 (Gateway) - Stop and restart with LLM judge
export MODEL_SVC_URL="http://localhost:8002"
export THRESHOLDS_JSON="configs/dev/thresholds.json"
export JUDGE_BACKEND="llm"             # Changed from "stub"
export JUDGE_MODEL="llama3.2:1b"
export OLLAMA_HOST="http://localhost:11434"
export JUDGE_TIMEOUT_SECS="60"         # Increased for first call

uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000
```

#### 5. Test LLM Judge

```bash
# Test gray zone URL (should trigger judge)
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://npm.org","p_malicious":0.35}'

# Expected: Response with judge.backend="llm" and rationale
```

### Performance Optimization

#### Pre-warm Model at Startup

```bash
# Add to gateway startup script
curl http://localhost:11434/api/generate \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "prompt": "Ready",
    "stream": false
  }'
```

#### Keep Ollama Always-On

```bash
# Option 1: systemd service (Linux)
sudo systemctl enable ollama
sudo systemctl start ollama

# Option 2: Docker (see Docker section)
```

---

## 🐳 Docker Deployment

### Build Images

```bash
# Build model service
docker build -f docker/model_svc.Dockerfile -t phishguard-model:latest .

# Build gateway
docker build -f docker/gateway.Dockerfile -t phishguard-gateway:latest .

# Build Ollama (optional)
docker pull ollama/ollama:latest
```

### Docker Compose

**`docker-compose.yml`:**

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: serve
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  model-service:
    image: phishguard-model:latest
    ports:
      - "8002:8002"
    environment:
      - MODEL_PATH=/app/models/7_features_xgb_isotonic_prod.pkl
      - LOG_LEVEL=INFO
    volumes:
      - ./models:/app/models:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - ollama

  gateway:
    image: phishguard-gateway:latest
    ports:
      - "8000:8000"
    environment:
      - MODEL_SVC_URL=http://model-service:8002
      - THRESHOLDS_JSON=/app/configs/dev/thresholds.json
      - JUDGE_BACKEND=llm
      - JUDGE_MODEL=llama3.2:1b
      - OLLAMA_HOST=http://ollama:11434
      - JUDGE_TIMEOUT_SECS=60
    volumes:
      - ./configs:/app/configs:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - model-service
      - ollama

volumes:
  ollama_data:
```

### Deploy with Docker Compose

```bash
# Start all services
docker-compose up -d

# Pull Ollama model (one-time setup)
docker exec -it phishguard-ollama-1 ollama pull llama3.2:1b

# View logs
docker-compose logs -f gateway

# Stop services
docker-compose down
```

### Production Docker Configuration

**Multi-stage build for smaller images:**

```dockerfile
# gateway.Dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ src/
COPY configs/ configs/
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🏥 Health Checks

### Model Service Health

```bash
# Health endpoint
curl http://localhost:8002/health

# Expected response:
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "7-feature-production-v1",
  "timestamp": "2025-10-23T12:34:56Z"
}
```

### Gateway Health

```bash
# Health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "model_service": "connected",
  "judge_backend": "llm",
  "timestamp": "2025-10-23T12:34:56Z"
}
```

### Ollama Health

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Expected: List of available models
{
  "models": [
    {
      "name": "llama3.2:1b",
      "size": 1321098329,
      ...
    }
  ]
}
```

### Automated Health Monitoring

**Bash script (`scripts/health_check.sh`):**

```bash
#!/bin/bash

check_service() {
  local name=$1
  local url=$2
  
  if curl -sf "$url" > /dev/null; then
    echo "✅ $name: healthy"
    return 0
  else
    echo "❌ $name: unhealthy"
    return 1
  fi
}

check_service "Model Service" "http://localhost:8002/health"
check_service "Gateway" "http://localhost:8000/health"
check_service "Ollama" "http://localhost:11434/api/tags"
```

**Cron job (check every 5 minutes):**

```bash
*/5 * * * * /path/to/scripts/health_check.sh >> /var/log/phishguard/health.log 2>&1
```

---

## 📊 Monitoring & Observability

### Stats Endpoint

```bash
# Get decision statistics
curl http://localhost:8000/stats

# Response:
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

### Config Endpoint

```bash
# Get current configuration
curl http://localhost:8000/config

# Response:
{
  "thresholds": {
    "low": 0.011,
    "high": 0.998,
    "optimal": 0.5
  },
  "model_name": "7-feature-production-v1",
  "judge_backend": "llm",
  "judge_model": "llama3.2:1b"
}
```

### Logging

**Structured logging example:**

```python
# src/gateway/main.py
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log structured data
logger.info(json.dumps({
    "event": "prediction",
    "url": url,
    "decision": decision,
    "p_malicious": p_malicious,
    "latency_ms": latency
}))
```

### Prometheus Metrics (Planned)

**Example metrics:**

```python
# Planned implementation
from prometheus_client import Counter, Histogram

prediction_counter = Counter(
    'phishguard_predictions_total',
    'Total predictions',
    ['decision']
)

latency_histogram = Histogram(
    'phishguard_prediction_latency_seconds',
    'Prediction latency'
)

judge_invocations = Counter(
    'phishguard_judge_invocations_total',
    'Judge invocations',
    ['verdict', 'backend']
)
```

---

## 🔧 Troubleshooting

### Common Issues

#### Issue 1: Model Service Won't Start

**Symptoms:**
```
FileNotFoundError: models/7_features_xgb_isotonic_prod.pkl
```

**Solution:**
```bash
# Verify model exists
ls -lh models/

# If missing, retrain or download
python notebooks/01_baseline_and_calibration.ipynb
```

#### Issue 2: Gateway Can't Connect to Model Service

**Symptoms:**
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution:**
```bash
# Check model service is running
curl http://localhost:8002/health

# If not running, start it (Terminal 1)
export MODEL_PATH="models/7_features_xgb_isotonic_prod.pkl"
uvicorn src.model_svc.main:app --host 0.0.0.0 --port 8002

# Verify MODEL_SVC_URL is correct (Terminal 2)
echo $MODEL_SVC_URL  # Should be: http://localhost:8002
```

#### Issue 3: LLM Judge Falls Back to Stub

**Symptoms:**
```json
{
  "judge": {
    "context": {
      "backend": "stub_fallback"
    }
  }
}
```

**Diagnosis:**
```bash
# Check gateway logs for error
# Look for: [JUDGE ERROR] LLM judge failed: <error>

# Common errors:
# 1. ReadTimeout → Increase JUDGE_TIMEOUT_SECS
# 2. ConnectionRefusedError → Ollama not running
# 3. Model not found → Pull model with ollama pull
```

**Solutions:**

**Timeout:**
```bash
export JUDGE_TIMEOUT_SECS="120"  # Increase to 2 minutes
```

**Ollama not running:**
```bash
# Start Ollama (Terminal 3)
ollama serve
```

**Model not found:**
```bash
# Pull model
ollama pull llama3.2:1b

# Verify
ollama list
```

#### Issue 4: SHAP Endpoint Returns 500

**Symptoms:**
```json
{
  "error": "SHAP explanation failed: Model type not supported"
}
```

**Solution:**
This should be fixed in the latest code (base estimator unwrapping). If still occurring:

```bash
# Check model service logs
# Should see: "Unwrapped calibrated model. Base type: <class 'xgboost.sklearn.XGBClassifier'>"

# If not, update src/model_svc/main.py with base estimator unwrapping logic
```

#### Issue 5: Dashboard Shows "Failed to fetch"

**Symptoms:**
Dashboard loads but prediction fails with network error.

**Solution:**
```bash
# Check dashboard API URL (src/gateway/static/explain.html line ~12)
const API_BASE_URL = 'http://localhost:8000';  # Should match gateway port

# Verify CORS is configured
# In src/gateway/main.py:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # Add dashboard origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"

# Restart services
uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

### Performance Issues

**Symptom: Slow predictions (>1s)**

**Diagnosis:**
```bash
# Test each component
time curl http://localhost:8002/predict -X POST -d '{"url":"http://test.com"}'
# Should be: <100ms

time curl http://localhost:8000/predict -X POST -d '{"url":"http://test.com"}'
# Should be: <200ms (includes gateway overhead)
```

**Solutions:**

1. **Model service slow:**
   - Check CPU/RAM usage: `top` or `htop`
   - Optimize XGBoost threads: Set `n_jobs` in model config

2. **LLM judge slow:**
   - First call always slow (15-20s) - this is normal (model loading)
   - Subsequent calls should be 2-5s
   - Pre-warm model at startup (see Ollama setup)

3. **SHAP endpoint slow:**
   - SHAP computation is expensive (~200-500ms)
   - This is acceptable for `/explain` endpoint (not used for real-time decisions)
   - Don't call `/explain` in production prediction path

---

## 🔒 Security Considerations

### Production Hardening (Planned)

**Not yet implemented - planned improvements:**

#### 1. Authentication

```python
# Example: API key middleware
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key
```

#### 2. Rate Limiting

```python
# Example: slowapi rate limiter
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/predict")
@limiter.limit("100/minute")
async def predict(...):
    ...
```

#### 3. HTTPS/TLS

```bash
# Use reverse proxy (nginx) for TLS termination
# Example nginx config:
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

#### 4. Secrets Management

```bash
# Use environment variables or secrets manager
export API_KEY=$(cat /run/secrets/api_key)
export MONGO_URI=$(cat /run/secrets/mongo_uri)
```

### Current Security Measures

1. **CORS:** Restricted to specific origins
2. **No sensitive data logging:** URLs logged but not stored persistently (unless MongoDB configured)
3. **Graceful degradation:** Service continues if optional components fail
4. **Input validation:** Pydantic schemas validate all inputs

---

## 📚 Additional Resources

- **[README.md](../README.md)** - Project overview
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Design decisions
- **[API.md](API.md)** - Complete API reference
- **[JUDGE.md](JUDGE.md)** - LLM judge deep dive

---

## 🆘 Getting Help

**If you encounter issues:**

1. Check this troubleshooting guide
2. Review service logs for error messages
3. Verify all environment variables are set correctly
4. Open an issue on GitHub: [github.com/fitsblb/PhishGuardAI/issues](https://github.com/fitsblb/PhishGuardAI/issues)

---

**Last Updated:** October 23, 2025  
**Version:** 1.0.0
