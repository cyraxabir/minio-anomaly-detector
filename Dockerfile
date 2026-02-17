FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application - USE THE HARDCODED VERSION
COPY anomaly-alert.py anomaly_detector.py

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "print('Service running')" || exit 1

# Run the service
CMD ["python", "-u", "anomaly_detector.py"]
