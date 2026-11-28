"""HTTP server: the public graveyard page and the owner-only feeding endpoint."""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, store, tasting

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
MAX_MEAL_CHARS = 20000


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _reply(self, status, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _is_owner(self):
        return bool(config.OWNER_KEY) and self.headers.get("X-Taster-Key") == config.OWNER_KEY

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        last_part = url.path.rsplit("/", 1)[-1]

        if url.path == "/":
            with open(PAGE, "rb") as page:
                return self._reply(200, page.read(), "text/html; charset=utf-8")
        if url.path == "/api/whoami":
            return self._reply(200, {"owner": self._is_owner(), "busy": tasting.is_busy()})
        if url.path == "/api/deaths":
            return self._reply(200, store.recent())
        if url.path.startswith("/api/deaths/"):
            death = store.get(last_part)
            return self._reply(200, death) if death else self._reply(404, {"error": "no such case"})
        if url.path.startswith("/api/jobs/"):
            job = tasting.job(last_part)
            if not job:
                return self._reply(404, {"error": "no such job"})
            # The page polls with ?since=N to get only the events it has not seen.
            since = int(urllib.parse.parse_qs(url.query).get("since", ["0"])[0])
            return self._reply(200, {"events": job["events"][since:], "done": job["done"], "death": job["death"]})
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/taste":
            return self._reply(404, {"error": "not found"})
        if not self._is_owner():
            return self._reply(401, {"error": "only the owner may feed the Taster"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            meal = (body.get("meal") or "").strip()
        except ValueError:
            return self._reply(400, {"error": "bad json"})
        if not meal or len(meal) > MAX_MEAL_CHARS:
            return self._reply(400, {"error": f"meal must be 1 to {MAX_MEAL_CHARS} characters"})
        if tasting.is_busy():
            return self._reply(409, {"error": "the Taster is already eating"})

        source = "command"
        if re.fullmatch(r"https?://\S+", meal):
            # A bare URL: the Taster downloads the script itself, then runs it.
            source, meal = meal, f"curl -fsSL {json.dumps(meal)} -o /var/tmp/dish.sh && bash /var/tmp/dish.sh"
        self._reply(200, {"job": tasting.start(meal, source)})


def serve():
    print(f"butler listening on :{config.PORT}, feeding {config.TASTER}")
    ThreadingHTTPServer(("0.0.0.0", config.PORT), Handler).serve_forever()
