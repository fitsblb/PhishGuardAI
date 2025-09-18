# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-09-17

### Added
- **Gateway Service**: Complete `/predict` endpoint with policy bands, gray-zone handling, and intelligent judge integration
  - `/config` endpoint for runtime configuration inspection
  - `/stats` endpoint with counters for policy vs final decisions and judge verdict tallies
  - `/stats/reset` endpoint for clearing metrics
  - **LLM judge integration** via Ollama with safe stub fallback for demonstrations
- **Model Service**: Serves calibrated URL-only phishing detection model
  - Automatic model loading from `models/dev/` directory
  - Heuristic fallback when model unavailable
  - `/health` and `/predict` endpoints with comprehensive error handling
- **Observability**: Comprehensive metrics and monitoring
  - Split counters distinguishing policy decisions from final outcomes
  - Judge verdict tallies for performance analysis
  - Health checks across all services
- **Data Contract**: Lightweight validation system for URL-only feature sets
  - Column presence and data type validation
  - Range checks for numeric features
  - Model compatibility verification
  - Automated CI integration for data quality assurance
- **Docker Support**: Production-ready containerization
  - Slim multi-stage Docker images optimizing for size and security
  - **Docker Quick Start** guide in README for rapid deployment
  - Environment-based configuration for flexible deployment
- **Development Runbook**: Comprehensive local-first development workflow
  - Support for both stub and LLM judge backends
  - Flexible threshold configuration via `configs/dev/thresholds.json`
  - Detailed troubleshooting guide and common issues resolution

### Fixed / Hardened
- **Input Validation**: Robust request validation and security measures
  - URL length validation with configurable limits (max 8192 characters)
  - HTTP 413 body size protection against oversized payloads
  - Localhost-only CORS policy for development security
- **Testing Suite**: Comprehensive test coverage ensuring reliability
  - Unit tests for core functionality and edge cases
  - End-to-end integration tests using FastAPI TestClient
  - Judge wiring tests validating LLM and stub backend integration
  - Import stability tests with editable package installation

### Technical Details
- **Gray-zone Configuration**: Currently ~14% gray-zone rate (fully configurable via thresholds)
- **LLM Judge Behavior**: Graceful degradation to stub judge when Ollama/model unavailable (fail-open for demos)
- **Model Architecture**: Calibrated XGBoost classifier with isotonic calibration for probability reliability
- **Feature Engineering**: URL-only feature extraction supporting real-time inference

### Dependencies
- Python 3.11+ with comprehensive ML and web service stack
- Optional: Ollama for LLM judge functionality
- Docker support for containerized deployments

---

## [Unreleased]

### Planned
- Enhanced model variants beyond URL-only features
- Advanced judge prompt engineering and model selection
- Production deployment guides for cloud environments
- Performance benchmarking and optimization guides