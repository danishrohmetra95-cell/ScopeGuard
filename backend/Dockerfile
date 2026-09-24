# ScopeGuard Backend
FROM python:3.11-slim

WORKDIR /app

# Install git for GitPython
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENV SCOPEGUARD_HOST=0.0.0.0
ENV SCOPEGUARD_PORT=8000
ENV SCOPEGUARD_ENVIRONMENT=production

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
