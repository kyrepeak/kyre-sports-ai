FROM python:3.12-slim

ARG WNBA_RELEASE_REVISION=unknown
ARG WNBA_RELEASE_ID=unversioned

LABEL org.opencontainers.image.title="Kyre Sports API" \
      org.opencontainers.image.revision="${WNBA_RELEASE_REVISION}" \
      org.opencontainers.image.version="${WNBA_RELEASE_ID}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    WNBA_DEPLOYMENT_MODE=container \
    WNBA_DEPLOYMENT_REPLICA_COUNT=1 \
    WNBA_PERSISTENT_VOLUME_ROOT=/var/lib/kyre-sports-api \
    WNBA_RELEASE_BUILD_REVISION=${WNBA_RELEASE_REVISION} \
    WNBA_RELEASE_BUILD_ID=${WNBA_RELEASE_ID}

WORKDIR /app

COPY sports_api/requirements.txt /app/sports_api/requirements.txt
COPY sports_api/requirements-persistence.txt /app/sports_api/requirements-persistence.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/sports_api/requirements.txt \
    && python -m pip install --no-cache-dir -r /app/sports_api/requirements-persistence.txt

COPY sports_api /app/sports_api

RUN addgroup --system kyre \
    && adduser --system --ingroup kyre --home /app kyre \
    && mkdir -p /var/lib/kyre-sports-api \
    && chown -R kyre:kyre /app /var/lib/kyre-sports-api

USER kyre

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8000') + '/health', timeout=4)); raise SystemExit(0 if d.get('status') == 'ok' else 1)"

CMD ["sh", "-c", "exec uvicorn sports_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
