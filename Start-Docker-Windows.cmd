@echo off
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Please start Docker Desktop first.
  pause
  exit /b 1
)
docker compose up -d --build
if errorlevel 1 (
  pause
  exit /b 1
)
echo Open the complete http://127.0.0.1:8765/#... URL from the logs below.
docker compose logs --no-log-prefix stockroom
echo To stop: docker compose down
pause
