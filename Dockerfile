# Multi-arch: builds natively on the Ampere A1 (arm64) VM and on x86 laptops.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY traveldeal ./traveldeal
COPY app ./app
COPY data ./data
COPY schema ./schema
COPY .streamlit/config.toml ./.streamlit/config.toml

# /app/var holds the SQLite database (a Docker volume in docker-compose.yml). Creating it here
# owned by appuser means a fresh volume starts with the right permissions.
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/var && chown -R appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"

CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]
