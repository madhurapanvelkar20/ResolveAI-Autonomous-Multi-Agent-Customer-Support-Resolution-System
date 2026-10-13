FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application packages and policies
COPY resolveai ./resolveai
COPY docs ./docs
COPY scripts ./scripts

# Ensure runtime directories exist
RUN mkdir -p /app/data /app/traces

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "resolveai.api:app", "--host", "0.0.0.0", "--port", "8000"]
