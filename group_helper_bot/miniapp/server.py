"""Minimal static HTTP server for the NOVA Help Telegram Mini App."""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"nova-help-miniapp"}')
            return
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        # Avoid logging query strings or user-supplied content.
        super().log_message(fmt, *args)


def main():
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"NOVA Help Mini App listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
