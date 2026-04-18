#!/usr/bin/env python3
"""
Minimal HTTP server that serves feed.xml with strict no-cache headers
so FritzFon always reads fresh data from the server instead of its own cache.

Port: env PORT (default 5000 for Docker; pass as first argument to override).
"""
import http.server
import os
import sys

PORT = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 5000))
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Only log errors, suppress normal access noise
        if args and str(args[1]) not in ("200", "304"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    os.chdir(SERVE_DIR)
    with http.server.HTTPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"Serving feed.xml on http://0.0.0.0:{PORT}/feed.xml")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
