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

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata \
    PORT=8080 \   
    # Changed to 8080 for DigitalOcean
    MAX_WORKERS=1 \
    LOG_LEVEL=info \
    ENVIRONMENT=production

# ... previous Dockerfile content ...

# Expose FastAPI port - DigitalOcean uses 8080
EXPOSE 8080

# Health check for FastAPI endpoint - use 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use port 8080 in CMD
CMD ["uvicorn", "src.stock_opt_api:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \  
     # Changed to 8080
     "--workers", "1", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]