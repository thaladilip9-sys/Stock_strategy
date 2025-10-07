# syntax=docker/dockerfile:1.4
# Build stage
FROM python:3.11-slim-bullseye AS builder
ENV TZ=Asia/Kolkata
# Set working directory
WORKDIR /app

# Set build environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim-bullseye

LABEL maintainer="Trading System" \
      version="1.0" \
      description="FastAPI Trading Hours Monitor Controller"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata \
    PORT=10000 \
    MAX_WORKERS=1 \
    LOG_LEVEL=info \
    ENVIRONMENT=production

# Create non-root user and necessary directories
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/logs /app/stock_interaday_json /app/env && \
    chown -R app:app /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/* && \
    cp /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# Create volume mount points for persistent data
VOLUME ["/app/logs", "/app/stock_interaday_json", "/app/env"]

# Expose FastAPI port
EXPOSE 10000

# Health check for FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

# Use exec form with hardcoded values for Render compatibility
CMD ["uvicorn", "src.stock_opt_api:app", \
     "--host", "0.0.0.0", \
     "--port", "10000", \
     "--workers", "1", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]