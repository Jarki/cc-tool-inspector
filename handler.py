"""
HTTP request handler — serves the static frontend and JSON API endpoints.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from queries import get_sessions, get_session

STATIC_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
}

# Map URL paths to static filenames.
STATIC_ROUTES = {
    "/":           "index.html",
    "/index.html": "index.html",
    "/style.css":  "style.css",
    "/app.js":     "app.js",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        try:
            if parsed.path == "/api/sessions":
                self._json(get_sessions())
            elif parsed.path == "/api/session":
                sid = qs.get("id", [""])[0]
                self._json(get_session(sid))
            elif parsed.path in STATIC_ROUTES:
                self._static(STATIC_ROUTES[parsed.path])
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, filename):
        path = os.path.realpath(os.path.join(STATIC_DIR, filename))
        # Guard against path traversal.
        if not path.startswith(STATIC_DIR + os.sep) and path != STATIC_DIR:
            self.send_response(403)
            self.end_headers()
            return
        ext = os.path.splitext(filename)[1]
        ct = MIME_TYPES.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass
