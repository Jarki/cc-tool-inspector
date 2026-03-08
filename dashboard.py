#!/usr/bin/env python3
"""
Claude Code tool tracker dashboard — session timeline view.
Run this script then open http://localhost:7337
"""
import os
from http.server import HTTPServer

from handler import Handler
from db import DB_PATH

HOST = os.environ.get("TRACKER_HOST", "127.0.0.1")
PORT = int(os.environ.get("TRACKER_PORT", "7337"))

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Dashboard running at http://{HOST}:{PORT}")
    print(f"Database: {DB_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
