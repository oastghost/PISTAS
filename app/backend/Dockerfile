# Build context is app (see docker-compose.yml), so db/ is available too.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

COPY backend/pyproject.toml /tmp/pyproject.toml
RUN python -c "import tomllib; [print(d) for d in tomllib.load(open('/tmp/pyproject.toml','rb'))['project']['dependencies']]"       > /tmp/requirements.txt  && pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app /srv/backend/app
COPY db /srv/db

RUN useradd --system --no-create-home pistas
USER pistas
WORKDIR /srv/backend
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
