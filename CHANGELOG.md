# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-10-15

### Added
- **8-Feature Model**: Complete upgrade to production-ready 8-feature phishing detection
  - `IsHTTPS`: Binary HTTPS indicator for security baseline
  - `TLDLegitimateProb`: Bayesian TLD legitimacy probability with 1401+ TLD dataset
  - `CharContinuationRate`: Character repetition pattern detection
  - `SpacialCharRatioInURL`: Special character density analysis
  - `URLCharProb`: URL character sequence probability scoring
  - `LetterRatioInURL`: Alphabetic character ratio for readability assessment
  - `NoOfOtherSpecialCharsInURL`: Special character count for complexity analysis
  - `DomainLength`: RFC-compliant domain length validation
- **Enhanced Judge System**: Modernized LLM integration with 8-feature model
  - Updated judge contracts to use production features
  - Enhanced stub logic with sophisticated heuristics
  - Improved LLM prompts with detailed feature descriptions
  - Graceful fallback from modern to legacy features
- **Comprehensive Test Suite**: 52 tests with 100% pass rate
  - Updated all tests for 8-feature model compatibility
  - Enhanced integration tests for microservice communication
  - Modernized judge system tests with production features
  - Fixed whitelist behavior validation

### Changed
- **Great Expectations**: Updated data validation for 8-feature model
  - Migrated from 3-feature legacy validation to 8-feature production validation
  - Updated thresholds and expectations for new feature ranges
  - Enhanced data contract validation with feature-specific checks
- **Judge System Architecture**: Complete alignment with production features
  - FeatureDigest contract updated with 8 required + 3 optional legacy fields
  - Enhanced decision logic using modern feature signals
  - Improved context and audit trail with comprehensive feature logging
- **GitHub Workflows**: Updated CI/CD for modern project structure
  - Enhanced data contract workflow with 8-feature model support
  - Updated CI workflow with better error reporting
  - Added fallback logic for legacy data file compatibility

### Removed
- **Feature Service**: Eliminated redundant microservice
  - Removed `src/feature_svc/` directory and related code
  - Updated Docker compose to remove feature service dependency
  - Cleaned up unused `docker/feature.Dockerfile`
  - Streamlined architecture to gateway + model services only
- **Legacy Scripts**: Deprecated obsolete feature extraction
  - Identified `scripts/materialize_url_features.py` as obsolete
  - Removed references to deprecated 3-feature model components

### Fixed
- **Docker Configuration**: Enhanced for 8-feature model deployment
  - Added `data/` directory to Docker images for TLD probability data
  - Updated environment variables for proper service communication
  - Fixed `.dockerignore` to include necessary data files
- **Test Infrastructure**: Resolved all compatibility issues
  - Fixed whitelist behavior in integration tests
  - Updated API contract expectations for current implementation
  - Resolved version mismatches and dependency issues
  - Enhanced test reliability with non-whitelisted test domains

### Technical Details
- **Feature Engineering**: Advanced URL-only features with statistical and linguistic analysis
- **Data Validation**: 31 comprehensive Great Expectations rules for production data quality
- **Performance**: Maintained 204ms API response time with enhanced feature extraction
- **Compatibility**: Backward compatibility maintained through optional legacy feature support

---

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