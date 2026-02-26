# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install ffmpeg for audio transcoding
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user before COPY so --chown works
RUN useradd --create-home appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code with correct ownership
COPY --chown=appuser:appuser audio_processor/ audio_processor/

USER appuser

# Cloud Run uses PORT env var (default 8080)
ENV PORT=8080

CMD ["python", "-m", "audio_processor.main"]
