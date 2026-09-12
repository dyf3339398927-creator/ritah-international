#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if ! docker info >/dev/null 2>&1; then
  printf 'Please start Docker Desktop first, then run this launcher again.\n'
  read -r reply
  exit 1
fi
docker compose up -d --build
for attempt in {1..30}; do
  address=$(docker compose logs --no-log-prefix stockroom | sed -n 's/.*\(http:\/\/127.0.0.1:8765\/#[A-Za-z0-9_-]*\).*/\1/p' | tail -1)
  if [ -n "$address" ]; then
    open "$address"
    printf 'Stockroom is running. To stop: docker compose down\n'
    exit 0
  fi
  sleep 1
done
printf 'Startup not ready. Inspect: docker compose logs stockroom\n'
read -r reply
exit 1
