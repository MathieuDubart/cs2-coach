"""Local Coach CS2 app with live analysis: python serve.py  (opens http://127.0.0.1:8765)

The search bar of the page sends any Steam link / SteamID here; the full pipeline runs on this PC
(Steam open, CS2 closed for Valve match info) and the new player appears in the page when done.
"""
import json
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import os

import build_app
import config
import cs2coach

PORT = int(os.environ.get("COACH_PORT", 8765))
JOB = {"running": False, "log": [], "done": False, "error": None, "steamid": None, "query": None, "partial": None, "players": None}
LOCK = threading.Lock()


def run_job(query):
    JOB.update(running=True, log=[], done=False, error=None, steamid=None, query=query, partial=None, players=None)
    cs2coach.LOG_HOOK = lambda m: JOB["log"].append(m)
    cs2coach.PARTIAL_HOOK = publish_partial
    try:
        res = cs2coach.run_for(query)
        ids = [p["steamid"] for p in res["match_players"]] if isinstance(res, dict) else [str(res)]
        entries = {i: build_app.write_player(i) for i in ids}
        idx = [x for x in load_index() if x["steamid"] not in entries] + [e for e in entries.values() if e]
        json.dump(idx, open(os.path.join(build_app.SITE, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if isinstance(res, dict):
            JOB["players"] = [p for p in res["match_players"] if entries.get(p["steamid"])]
        else:
            JOB["steamid"] = ids[0]
    except ValueError as e:  # expected situations (nothing public, expired demo...): message only
        JOB["error"] = str(e)
        print(f"  -> {e}")
    except Exception as e:
        JOB["error"] = str(e)
        traceback.print_exc()
    finally:
        cs2coach.LOG_HOOK = None
        cs2coach.PARTIAL_HOOK = None
        JOB.update(running=False, done=True)
        LOCK.release()


def publish_partial(sid):
    """A first profile (Leetify, or the existing one) is ready: put it on the site right away."""
    sid = str(sid)
    e = build_app.write_player(sid)
    if e:
        idx = [x for x in load_index() if x["steamid"] != sid] + [e]
        json.dump(idx, open(os.path.join(build_app.SITE, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
        JOB["partial"] = sid


def load_index():
    p = os.path.join(build_app.SITE, "index.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            # standards mode (the claude.ai host adds this wrapper itself when publishing)
            head = '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">'
            return self.send(200, head + build_app.shell_html(load_index(), local=True) + "</body></html>", "text/html; charset=utf-8")
        if u.path in ("/index.json", "/pros.json") or u.path.startswith(("/players/", "/radars/", "/replays/")):
            f = os.path.normpath(os.path.join(build_app.SITE, u.path.lstrip("/")))
            if f.startswith(os.path.normpath(build_app.SITE)) and os.path.exists(f):
                return self.send(200, open(f, "rb").read())
            return self.send(404, {"error": "introuvable"})
        if u.path == "/api/ping":
            return self.send(200, {"ok": True})
        if u.path == "/api/analyze":
            query = (q.get("q") or [""])[0].strip()
            if not query:
                return self.send(400, {"error": "Recherche vide"})
            if not LOCK.acquire(blocking=False):
                return self.send(409, {"error": "Une analyse est déjà en cours", "query": JOB["query"]})
            threading.Thread(target=run_job, args=(query,), daemon=True).start()
            return self.send(200, {"started": True})
        if u.path == "/api/job":
            return self.send(200, JOB)
        return self.send(404, {"error": "introuvable"})

    def do_POST(self):
        """Journal check-ins and experiments: saved in out/, then the player's plan and page are rebuilt."""
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send(400, {"error": "requête invalide"})
        sid = str(body.get("sid") or "")
        if not sid.isdigit():
            return self.send(400, {"error": "joueur manquant"})
        try:
            if u.path == "/api/checkin":
                import context
                context.add_checkin(sid, body)
                refresh_plan(sid)
                return self.send(200, {"ok": True, "n": len(context.journal(sid))})
            if u.path == "/api/experiment":
                import experiments
                if body.get("action") == "start":
                    experiments.start(sid, body.get("template"), body.get("params") or {})
                elif body.get("action") == "stop":
                    experiments.stop(sid, body.get("id"), "done")
                else:
                    return self.send(400, {"error": "action inconnue"})
                refresh_plan(sid)
                return self.send(200, {"ok": True})
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self.send(500, {"error": str(e)})
        return self.send(404, {"error": "introuvable"})


def refresh_plan(sid):
    cs2coach.attach_plan(sid)
    build_app.write_player(sid)


if __name__ == "__main__":
    if sys.stdout is None:  # started with pythonw (no console): keep a log file instead
        sys.stdout = sys.stderr = open(os.path.join(config.CACHE, "serve.log"), "a", encoding="utf-8", buffering=1)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(os.path.join(build_app.SITE, "index.json")):
        print("Première construction du site…")
        build_app.build()
    ThreadingHTTPServer.allow_reuse_address = False  # a second instance must fail instead of sharing the port
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Coach CS2 tourne déjà : ouvre http://127.0.0.1:{PORT}/#avant")
        if "--no-browser" not in sys.argv:
            webbrowser.open(f"http://127.0.0.1:{PORT}/#avant")
        sys.exit(0)
    url = f"http://127.0.0.1:{PORT}/#avant"
    print(f"Coach CS2 : {url}  (Ctrl+C pour arrêter)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()
