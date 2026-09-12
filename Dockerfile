FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 STOCKROOM_CONTAINER=1
WORKDIR /app
RUN groupadd --gid 10001 stockroom && useradd --uid 10001 --gid stockroom --create-home stockroom \
    && mkdir /data && chown stockroom:stockroom /data
COPY monitor/app.py monitor/core.py monitor/purchase.py ./
COPY monitor/web ./web
COPY config/files/stores.json ./stores.json
COPY LICENSE SOURCES.md ./
USER stockroom
VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/',timeout=3)" || exit 1
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8765", "--no-browser", "--data-dir", "/data"]
