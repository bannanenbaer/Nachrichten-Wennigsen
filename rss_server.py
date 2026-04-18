#!/usr/bin/env python3
from flask import Flask, make_response, send_file
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os

import scraper

app = Flask(__name__)

FEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed.xml")

# Initial scrape on startup so feed.xml exists immediately
try:
    scraper.main()
except Exception as exc:
    print(f"[startup] Scraper fehlgeschlagen: {exc}")

# Daily 06:00 refresh
_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(scraper.main, "cron", hour=6, minute=0)
_scheduler.start()
atexit.register(_scheduler.shutdown)


@app.route("/feed.xml")
@app.route("/feed.rss")
def feed():
    if not os.path.exists(FEED_FILE):
        try:
            scraper.main()
        except Exception as exc:
            return f"Feed nicht verfügbar: {exc}", 503
    resp = make_response(send_file(FEED_FILE, mimetype="application/rss+xml"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/health")
def health():
    return "ok"
