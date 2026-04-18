#!/bin/sh
set -e

# Fetch fresh feed on every (re)start so the file is never stale
echo "[start] Scraper wird ausgeführt..."
python3 /app/scraper.py

# Start cron daemon in background (handles daily 06:00 update)
cron

# Run HTTP server in foreground (PID 1 signal target)
exec python3 /app/server.py
