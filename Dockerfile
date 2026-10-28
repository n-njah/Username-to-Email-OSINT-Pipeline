FROM python:3.11-slim-bookworm AS base

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Non-root user for security
RUN groupadd --gid 1000 osint && \
    useradd --uid 1000 --gid osint --shell /bin/bash --create-home osint

WORKDIR /app

# Install system dependencies for web scraping
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    curl \
    wget \
    git \
    tor \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
COPY optional-requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install OSINT tools globally (they run as subprocesses)
RUN pip install --no-cache-dir maigret sherlock-project || echo "Warning: OSINT tools install skipped - will be added separately"

# Copy application code
COPY --chown=osint:osint . /app

# Switch to non-root user
USER osint

# Expose port for web interface (if applicable)
EXPOSE 8080

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]


# =============================================================================
# Development Stage
# =============================================================================
FROM base AS dev

# Install development dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

# Install pre-commit hooks
RUN pre-commit install --install-hooks

# Mount volume for development
VOLUME ["/app/tests"]

# Enable debug mode
ENV DEBUG=true


# =============================================================================
# Production Stage (Minimal)
# =============================================================================
FROM python:3.11-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 osint && \
    useradd --uid 1000 --gid osint --shell /bin/bash --create-home osint

WORKDIR /app

# Copy only runtime requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=osint:osint . /app

USER osint

ENTRYPOINT ["python", "main.py"]


# =============================================================================
# Builder Stage (for building wheels offline)
# =============================================================================
FROM python:3.11-bookworm AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --wheel --dest=/wheels -r requirements.txt

# Create tarball for offline installation
RUN tar czf /wheels.tar.gz /wheels


# =============================================================================
# Health Check
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0 if __import__('os').path.exists('/app/main.py') else 1)"


# =============================================================================
# Labels
# =============================================================================
LABEL maintainer="Security Research Team" \
      version="1.0.0" \
      description="Username-to-Email OSINT Pipeline Container" \
      org.opencontainers.image.source="https://github.com/org/username-to-email-osint" \
      org.opencontainers.image.vendor="OSINT Pipeline" \
      org.opencontainers.image.licenses="MIT"
