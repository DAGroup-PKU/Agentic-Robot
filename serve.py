"""Dependency-free local preview with content watching and browser refresh."""
import argparse
import functools
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from build import ROOT, OUT, build

state = {"version": 1, "error": None}


def fingerprint():
    files = [ROOT / "build.py"]
    for directory in ("assets", "content", "templates"):
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    return tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files))


def watch():
    previous = fingerprint()
    while True:
        time.sleep(0.6)
        try:
            current = fingerprint()
            if current == previous:
                continue
            previous = current
            # Reload the generator too, so layout edits do not need a restart.
            import importlib
            import build as generator
            importlib.reload(generator).build()
            state.update(version=state["version"] + 1, error=None)
            print("Rebuilt; refreshing browsers.", flush=True)
        except Exception as error:
            state["error"] = str(error)
            print(f"Build failed: {error}", flush=True)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if urlsplit(self.path).path == "/__version":
            body = json.dumps(state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (OUT / "404.html").exists():
            body = (OUT / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, format, *args):
        if not self.path.startswith("/__version"):
            super().log_message(format, *args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    build()
    server = ThreadingHTTPServer((args.host, args.port), functools.partial(Handler, directory=str(OUT)))
    threading.Thread(target=watch, daemon=True).start()
    print(f"Agent × Robot → http://{args.host}:{args.port}\nWatching content/, assets/ and templates/. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
