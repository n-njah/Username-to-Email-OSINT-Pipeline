# Username-to-Email OSINT Pipeline

A comprehensive Python tool for chaining username enumeration with email discovery pivots. Designed for security researchers and penetration testers conducting authorized investigations.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Deployment Options](#deployment-options)
- [Module Architecture](#module-architecture)
- [Output Formats](#output-formats)
- [Testing](#testing)
- [Development](#development)
- [Legal & Ethical Considerations](#legal--ethical-considerations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

| Capability | Description |
|------------|-------------|
| **Username Enumeration** | Scan across 3,000+ platforms via Maigret & Sherlock integration |
| **Gravatar Pivot** | Reverse MD5 hash lookups to discover associated emails |
| **GitHub Commit Extraction** | Parse `.patch` endpoints for exposed author emails |
| **Breach Indexing** | Query breach corpora by username field |
| **Profile Scraping** | Extract contact info from discovered profile URLs |
| **Correlation Engine** | Deduplicate and score findings across sources |
| **MCP Support** | Native Model Context Protocol integration for agent workflows |
| **Multi-format Output** | JSON, CSV, HTML reports with confidence scoring |
| **Containerized Deployments** | Docker Compose with Tor, Redis, API gateway support |

---

## Project Structure

```
username-to-email-osint/
├── main.py                     # CLI entry point
├── enumeration.py              # Username discovery module
├── pivots.py                   # Email discovery pivots
├── correlation.py              # Deduplication & scoring
├── outputs.py                  # Report generators
├── config.yaml                 # Application configuration
├── requirements.txt            # Core dependencies
├── optional-requirements.txt   # Experimental feature deps
├── Dockerfile                  # Multi-stage container build
├── docker-compose.yml          # Production orchestration
├── docker-compose.dev.yml      # Development override
├── docker-compose.test.yml     # Testing override
├── tests/                      # Pytest test suite
├── src/                        # Source modules (alternative layout)
├── results/                    # Generated reports (gitignored)
└── cache/                      # Result caching (gitignored)
```

---

## Installation

### Prerequisites

- Python 3.9+
- pip or pipx
- Docker & Docker Compose (optional, for containerized deployment)
- Virtual environment recommended

### Option 1: Direct Installation

```bash
# Clone the repository
git clone https://github.com/n-njah/Username-to-Email-OSINT-Pipeline.git
cd Username-to-Email-OSINT-Pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install OSINT tool dependencies (Maigret, Sherlock)
pip install maigret sherlock-project
```

### Option 2: Docker Installation

```bash
# Build and start containers
docker-compose up -d

# Run a scan through the container
docker-compose exec osint-pipeline python main.py \
  --username "target_handle" \
  --output /results/report.json
```

### Option 3: Development Setup

```bash
# Build dev container with hot-reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Access VS Code Server (port 8081)
open http://localhost:8081

# Or run locally with dev dependencies
pip install -r optional-requirements.txt
pre-commit install
```

---

## Quick Start

### Minimal Local Run

```bash
# Single username lookup
python main.py --username "target_handle" --output report.json

# With verbose output
python main.py --username "target_handle" -v
```

### Docker Run

```bash
# Standalone run
docker run -it --rm -v $(pwd)/results:/app/results \
  username-osint:latest \
  --username "target_handle" --output /results/report.json
```

### With Anonymization (Tor)

```bash
# Start with Tor proxy
TOR_ENABLED=true docker-compose up -d

# Run scan through Tor
docker-compose exec osint-pipeline python main.py \
  --username "target_handle" \
  --proxy socks5://tor:9050 \
  --output /results/report.json
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | No | Personal access token for GitHub API |
| `BREACH_API_KEY` | No | Key for breach database services (IntelX, etc.) |
| `TOR_ENABLED` | No | Set to "true" to route requests through Tor |
| `PROXY_URL` | No | HTTP/S proxy for all requests |
| `MCP_AUTH_TOKEN` | No | Authentication for MCP endpoints |

### Config File

Create `config.yaml` in the project root. Defaults are provided in the repository. Key sections:

```yaml
runtime:
  request_timeout: 30
  threads: 10

rate_limits:
  per_site_delay: 1.0
  requests_per_minute: 60

modules:
  enumeration:
    enabled: true
    engines:
      - maigret
      - sherlock
  gravatar:
    enabled: true
  github:
    enabled: true
  breach:
    enabled: true
  profile_scrape:
    enabled: true
```

---

## Usage Examples

### Basic Usage

```bash
# Single username lookup
python main.py --username "target_handle" --output report.json

# Verbosity control
python main.py --username "target_handle" -v  # Enable debug logging

# Custom timeout for slow sites
python main.py --username "target_handle" --timeout 30
```

### Output Formats

```bash
# JSON (default)
python main.py --username "target_handle" --format json

# CSV for spreadsheet analysis
python main.py --username "target_handle" --format csv

# Interactive HTML report
python main.py --username "target_handle" --format html
```

### Advanced Options

```bash
# Exclude specific modules
python main.py --username "target_handle" --exclude github,breach

# Include only specific pivots
python main.py --username "target_handle" --only gravatar,github

# Set API keys via environment
export BREACH_API_KEY="your_key"
export GITHUB_TOKEN="your_token"
python main.py --username "target_handle"

# Threaded execution
python main.py --username "target_handle" --threads 10

# Use custom config file
python main.py --username "target_handle" --config custom-config.yaml
```

### Docker Commands

```bash
# Build image
docker-compose build

# Run scan
docker-compose exec osint-pipeline python main.py \
  --username "target_handle" --output /results/report.json

# View logs
docker-compose logs -f osint-pipeline

# Stop all services
docker-compose down

# Clean everything (including volumes)
docker-compose down -v
```

### MCP Integration

```python
# Python client example
from mpc_client import mpc_enumerate, mpc_pivot, mpc_correlate

# Enumerate
enum_results = await mpc_enumerate("target_handle")

# Pivot
pivot_results = await mpc_pivot("gravatar", "target_handle", {"names": ["John", "Doe"]})

# Correlate
final_report = await mpc_correlate(enum_results + pivot_results)
```

---

## Deployment Options

| Option | Complexity | Best For |
|--------|------------|----------|
| **Local Python** | Low | Individual investigators |
| **Docker (single container)** | Low | Portable deployment |
| **Docker Compose** | Medium | Teams with shared infrastructure |
| **Docker Compose + Tor** | Medium-High | Anonymous investigations |
| **Kubernetes** | High | Large-scale production |

### Production Deployment

```bash
# Use minimal production stage
docker-compose build osint-pipeline
docker-compose -f docker-compose.yml up -d osint-pipeline

# Verify health
docker-compose ps osint-pipeline
```

### Scaling Recommendations

- **CPU**: 4 cores minimum for parallel scanning
- **Memory**: 4GB minimum, 8GB recommended for large batches
- **Storage**: 1GB for caches and reports
- **Network**: Unrestricted outbound access required

---

## Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      main.py                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  ArgumentParser                        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌─────────────────────┐        ┌─────────────────────┐
│   enumeration.py    │        │   correlation.py    │
│  ┌───────────────┐  │        │  ┌───────────────┐  │
│  │   Maigret     │  │        │  │ Deduplicator │  │
│  │   Sherlock    │  │        │  │ Scorer       │  │
│  └───────────────┘  │        │  └───────────────┘  │
└─────────────────────┘        └─────────────────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
              ┌─────────────────────┐
              │    pivots.py         │
              │ ┌─────────────────┐ │
              │ │ Gravatar        │ │
              │ │ GitHub          │ │
              │ │ Breach          │ │
              │ │ ProfileScrape   │ │
              │ └─────────────────┘ │
              └─────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │    outputs.py        │
              │  JSON | CSV | HTML   │
              └─────────────────────┘
```

### Module Descriptions

| Module | Responsibility | Key Functions |
|--------|---------------|---------------|
| **main.py** | CLI orchestration | Arg parsing, pipeline routing, MCP hooks |
| **enumeration.py** | Username discovery | Maigret/Sherlock wrappers, profile validation |
| **pivots.py** | Email pivots | Gravatar reversal, GitHub extraction, breach lookup |
| **correlation.py** | Deduplication & scoring | Normalization, confidence scoring, evidence chains |
| **outputs.py** | Report generation | JSON/CSV/HTML exporters with styling |

---

## Output Formats

### JSON (Default)

Structured data suitable for programmatic consumption and API integration.

### CSV

Flat table format for spreadsheet analysis and data export.

Columns: `source,email,confidence,first_seen,platform_context`

### HTML

Interactive report with expandable sections, search functionality, and visual confidence meters.

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=. --cov-report=html

# Specific test file
pytest tests/test_enumeration.py -v
```

### Integration Tests

```bash
# Run with mocked external services
docker-compose -f docker-compose.yml -f docker-compose.test.yml up

# Clean test artifacts
rm -rf ./tests/output/*
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run all hooks manually
pre-commit run --all-files
```

---

## Development

### Setting Up Dev Environment

```bash
# Clone and setup
git clone https://github.com/n-njah/Username-to-Email-OSINT-Pipeline.git
cd Username-to-Email-OSINT-Pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -r optional-requirements.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests Locally

```bash
# Standard test run
pytest tests/ -v

# With debug output
pytest tests/ -v -s

# Watch mode (auto-run on changes)
pytest tests/ -v --watch
```

### Code Quality

```bash
# Linting
flake8 src/
black src/ --check
isort src/ --check-only

# Type checking
mypy src/ --strict
```

### Adding New Modules

1. Create new module in `src/pivots/` or `src/enumeration/`
2. Implement standard interface (`discover(target) -> List`)
3. Register in module registry
4. Add unit tests in `tests/`
5. Update documentation

---

## Legal & Ethical Considerations

### Authorization Checklist

Before running this tool, ensure you have:

- [ ] **Written authorization** from the system owner
- [ ] **Defined scope** clearly documented
- [ ] **RoE (Rules of Engagement)** signed off
- [ ] **Data handling policy** in place
- [ ] **Retention schedule** for collected data

### Compliance Notes

- Gravatar queries access **public data only**
- GitHub commits are **public metadata**
- Breach data may fall under **different legal frameworks** (GDPR, CCPA)
- **Do not** use for unauthorized access, harassment, or stalking

### Responsible Disclosure

If you discover exposed credentials:

1. Verify the exposure is unintentional
2. Notify affected parties through official channels
3. Document findings without retaining passwords
4. Follow coordinated disclosure timelines

### OpSec Recommendations

- Use Tor or proxy chain for sensitive investigations
- Never run scans from production IP ranges
- Sanitize reports before sharing externally
- Encrypt stored data at rest

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Rate limit errors | Increase `per_site_delay` in `config.yaml` or enable Tor |
| False positives on common usernames | Require manual review flag; use unique handles only |
| Empty breach results | Check `BREACH_API_KEY` validity |
| Slow enumeration | Reduce concurrent threads or exclude heavy modules |
| Gravatar timeout | Increase `request_timeout` parameter |
| Docker container exits | Check `docker-compose logs osint-pipeline` |

### Debug Mode

```bash
python main.py --username "test" --debug 2>&1 | tee debug.log
```

### Known Limitations

- GitHub API rate limit: 60/hour unauthenticated, 5,000/hour authenticated
- Gravatar does not guarantee email accuracy
- Breach databases vary in freshness
- Profile scrapers fail behind CAPTCHA/anti-bot systems

---

## License

MIT License - See LICENSE file for details.

This tool is provided for educational and authorized security research purposes only. Users are responsible for compliance with applicable laws and regulations.

---

## Disclaimer

This software is intended for legitimate security research, ethical hacking, and authorized penetration testing. The developers are not responsible for misuse of this tool. Always obtain proper authorization before investigating any target.

---

## References

- [Maigret Documentation](https://github.com/soxoj/maigret)
- [Sherlock Project](https://github.com/sherlock-project/sherlock)
- [OSINT Framework](https://osintframework.com/)
- [Gravatar API](https://en.gravatar.com/site/implement/images/)
- [GitHub API Docs](https://docs.github.com/en/rest)

---

## Changelog

### 1.0.0 (2026-10-28)
- Initial release
- Core enumeration engine (Maigret + Sherlock)
- Gravatar pivot implementation
- GitHub commit extraction
- Breach index integration (stubbed)
- Profile scraping module
- Multi-format output support (JSON/CSV/HTML)
- Docker Compose orchestration
- Tor anonymization support
- MCP agent integration hooks

---

*Last updated: October 2026*
