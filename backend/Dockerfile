FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["sh", "-c", "if [ -n \"$GOOGLE_APPLICATION_CREDENTIALS_JSON\" ]; then printf '%s' \"$GOOGLE_APPLICATION_CREDENTIALS_JSON\" > /tmp/gcp-credentials.json && export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-credentials.json; fi; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
