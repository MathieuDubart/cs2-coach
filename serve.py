"""Local Coach CS2 app with live analysis: python serve.py  (opens http://127.0.0.1:8765)

The search bar of the page sends any Steam link / SteamID here; the full pipeline runs on this PC
(Steam open, CS2 closed for Valve match info) and the new player appears in the page when done.
"""
import json
import re
import sys
import threading
import time
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
LOCAL_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


def run_job(query, task=None, extra=None):
    """One analysis at a time (search, or Steam history sync when task is given). The caller holds LOCK.
    extra: what the page shows at the end (the view and the match of a re-analysis)."""
    try:   # everything inside: the lock is released whatever happens
        JOB.update({"running": True, "log": [], "done": False, "error": None, "steamid": None, "query": query, "partial": None,
                    "players": None, "view": None, "match": None, **(extra or {})})
        cs2coach.LOG_HOOK = lambda m: JOB["log"].append(m)
        cs2coach.PARTIAL_HOOK = publish_partial
        res = task() if task else cs2coach.run_for(query)
        ids = [p["steamid"] for p in res["match_players"]] if isinstance(res, dict) else [str(res)]
        entries = {i: build_app.write_player(i) for i in ids}
        idx = [x for x in load_index() if x["steamid"] not in entries] + [e for e in entries.values() if e]
        config.write_json(os.path.join(build_app.SITE, "index.json"), idx)
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
        config.write_json(os.path.join(build_app.SITE, "index.json"), idx)
        JOB["partial"] = sid


def load_index():
    return config.read_json(os.path.join(build_app.SITE, "index.json"), [])


class Handler(BaseHTTPRequestHandler):
    def foreign(self, write=False):
        """True for a request coming from another site. Without this, a page you visit could start the microphone,
        change or remove your Steam access, delete data or launch analyses (a form or a fetch sent to 127.0.0.1),
        or read your data through a domain name pointed at 127.0.0.1 (DNS rebinding: the Host is then that name).
        The page of the app, CS2 (Game State Integration) and command-line tools pass."""
        host = self.headers.get("Host")
        if host is not None and host.lower() not in LOCAL_HOSTS:
            return True
        if write:   # a change: the browser says where the request comes from (Origin, else Sec-Fetch-Site)
            origin = self.headers.get("Origin")
            if origin is not None:
                return origin.lower() not in {f"http://{h}" for h in LOCAL_HOSTS}
            return self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none")
        return False

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
        if self.foreign(write=u.path == "/api/analyze"):   # the only GET that starts something
            return self.send(403, {"error": "request from another site refused"})
        if u.path in ("/", "/index.html"):
            # standards mode (the claude.ai host adds this wrapper itself when publishing)
            head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">'
            return self.send(200, head + build_app.shell_html(load_index(), local=True) + "</body></html>", "text/html; charset=utf-8")
        if u.path == "/api/voice/status":
            return self.send(200, voice_status())
        if u.path == "/api/voice/devices":
            try:
                import voice
                return self.send(200, voice.devices())
            except Exception as e:
                return self.send(200, {"error": str(e)})
        if u.path == "/api/gsi/state":
            import gsi
            s = gsi.state()
            try:
                import voice
                s["mic"] = voice.REC.recording()
                s["mic_silent"] = voice.REC.recording() and time.time() - (voice.REC.meta or {}).get("start", time.time()) > 60 and voice.REC.peak < 0.01
                s["mic_auto"] = bool(voice.settings().get("auto"))
            except Exception:
                pass
            return self.send(200, s)
        if u.path == "/api/gsi/raw":   # what the game really sends (key paths and a few whole messages)
            import gsi
            return self.send(200, {"keys": dict(sorted(gsi.RAW["keys"].items())), "samples": gsi.RAW["samples"]})
        if u.path == "/api/gsi/status":
            import gsi
            return self.send(200, gsi.status())
        if u.path == "/api/team/suggest":
            import team
            sid = (q.get("sid") or [""])[0]
            return self.send(200, team.suggestions(sid) if sid.isdigit() else [])
        if u.path in ("/index.json", "/pros.json") or u.path.startswith(("/players/", "/radars/", "/replays/", "/teams/")):
            f = os.path.normpath(os.path.join(build_app.SITE, u.path.lstrip("/")))
            if f.startswith(os.path.normpath(build_app.SITE) + os.sep) and os.path.isfile(f):
                return self.send(200, config._retry(lambda: open(f, "rb").read(), f))
            return self.send(404, {"error": "not found"})
        if u.path == "/api/ping":
            return self.send(200, {"ok": True})
        if u.path == "/api/analyze":
            query = (q.get("q") or [""])[0].strip()
            if not query:
                return self.send(400, {"error": "Empty search"})
            if not LOCK.acquire(blocking=False):
                return self.send(409, {"error": "An analysis is already running", "query": JOB["query"]})
            threading.Thread(target=run_job, args=(query,), daemon=True).start()
            return self.send(200, {"started": True})
        if u.path == "/api/job":
            return self.send(200, JOB)
        if u.path == "/api/steam/status":
            import steamlink
            sid = (q.get("sid") or [""])[0] or str(config.settings().get("own_steamid") or config.logged_in_account()[0] or "")
            if not sid.isdigit():
                return self.send(200, {"steamid": None, "links": {"key": steamlink.KEY_URL, "auth": steamlink.AUTH_URL}})
            return self.send(200, steamlink.status(sid))
        if u.path == "/api/steam/login":  # sign in through Steam: Steam's own page, then back to /api/steam/callback
            import steamlink
            base = f"http://127.0.0.1:{PORT}"
            return self.redirect(steamlink.login_url(base + "/api/steam/callback", base + "/"))
        if u.path == "/api/steam/callback":
            import steamlink
            params = {k: v[0] for k, v in q.items()}
            sid = steamlink.verify(params, f"http://127.0.0.1:{PORT}/api/steam/callback")
            if not sid:
                return self.redirect("/?steam=refused#settings")
            name = None
            try:
                if steamlink.api_key():
                    name = steamlink.check_key(steamlink.api_key(), sid).get("personaname")
            except steamlink.SteamError:
                pass
            if not name:
                own, own_name = config.logged_in_account()
                name = own_name if own and int(own) == sid else (config.settings().get("players", {}).get(str(sid)) or {}).get("name")
            steamlink.save_login(sid, name)
            return self.redirect("/?steam=ok#settings")
        return self.send(404, {"error": "not found"})

    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        """Journal check-ins and experiments: saved in out/, then the player's plan and page are rebuilt."""
        u = urlparse(self.path)
        if self.foreign(write=True):
            return self.send(403, {"error": "request from another site refused"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send(400, {"error": "invalid request"})
        if u.path == "/api/gsi":  # CS2 Game State Integration: the game itself, many times per round
            import gsi
            ok = gsi.update(body)
            if ok:
                try:
                    import voice
                    if voice.settings().get("auto") or voice.REC.recording():
                        voice.on_gsi(gsi.state())
                except Exception as e:
                    print("calls:", e, flush=True)
            return self.send(200 if ok else 403, {})
        if u.path.startswith("/api/voice/"):
            import gsi
            import voice
            act = u.path.rsplit("/", 1)[-1]
            try:
                if act == "settings":
                    voice.save_settings(**{k: body[k] for k in ("auto", "device") if k in body})
                elif act == "start":
                    g = gsi.state()
                    voice.pause_transcription()
                    voice.REC.start(g.get("map"), body.get("sid") or config.settings().get("own_steamid"), "manual")
                elif act == "stop":
                    voice.finish()
                elif act == "transcribe":
                    if not voice.start_transcription(str(body.get("id") or "")):
                        return self.send(409, {"error": "A transcription is already running."})
                elif act == "delete":
                    rid = str(body.get("id") or "")
                    if re.fullmatch(r"[\w-]+", rid):
                        voice.delete(rid)
                else:
                    return self.send(404, {"error": "not found"})
            except Exception as e:
                return self.send(400, {"error": f"Microphone: {e}"})
            return self.send(200, voice_status())
        if u.path == "/api/gsi/site":  # the player marks where the T attacked, and what they saw in the round
            import gsi
            try:
                rnd = int(body.get("round"))
                ok = gsi.set_site(rnd, body.get("site")) if "site" in body else True
                mark = {k: body[k] for k in ("contact", "alone", "contact_t", "site_t", "dyn", "lone") if k in body}
                ok = ok and (gsi.set_mark(rnd, mark) if mark else True)
            except (TypeError, ValueError):
                return self.send(400, {"error": "invalid round"})
            return self.send(200 if ok else 409, gsi.state())
        if u.path == "/api/reanalyze":  # one match again, from its demo (button of the Matches view)
            sid, mid = str(body.get("sid") or ""), str(body.get("mid") or "")
            if not sid.isdigit() or not mid.isdigit():
                return self.send(400, {"error": "invalid match"})
            if not LOCK.acquire(blocking=False):
                return self.send(409, {"error": "An analysis is already running", "query": JOB["query"]})
            threading.Thread(target=run_job, args=("re-analysis of the match", lambda: cs2coach.reanalyze_match(sid, mid)),
                             kwargs={"extra": {"view": "matches", "match": mid}}, daemon=True).start()
            return self.send(200, {"started": True})
        if u.path in ("/api/gsi/install", "/api/gsi/uninstall"):
            import gsi
            try:
                return self.send(200, gsi.install(PORT) if u.path.endswith("install") and not u.path.endswith("uninstall") else gsi.uninstall())
            except (ValueError, OSError) as e:
                return self.send(400, {"error": str(e)})
        sid = str(body.get("sid") or "")
        if not sid.isdigit():
            return self.send(400, {"error": "missing player"})
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
            if u.path == "/api/team":
                import team
                ids = [str(i) for i in body.get("ids") or [] if str(i).isdigit()]
                p = team.build(ids, owner=sid)
                build_app.write_teams()
                return self.send(200, {"ok": True, "id": p["id"]})
            if u.path == "/api/team/delete":
                import team
                tid = str(body.get("id") or "")
                f = os.path.join(team.TEAMS, f"{tid}.json")
                if tid.isalnum() and os.path.exists(f):
                    os.remove(f)
                build_app.write_teams()
                return self.send(200, {"ok": True})
            if u.path.startswith("/api/steam/"):
                import steamlink
                act = u.path.rsplit("/", 1)[-1]
                try:
                    if act == "credentials":
                        saved = steamlink.set_credentials(sid, body.get("api_key"), body.get("auth_code"), body.get("known_code"))
                        return self.send(200, {"ok": True, "saved": saved, "status": steamlink.status(sid)})
                    if act == "options":
                        s = config.settings()
                        s.setdefault("players", {}).setdefault(sid, {})["auto_sync"] = bool(body.get("auto_sync"))
                        config.save_settings(s)
                        return self.send(200, {"ok": True, "status": steamlink.status(sid)})
                    if act == "forget":
                        steamlink.forget(sid)
                        return self.send(200, {"ok": True, "status": steamlink.status(sid)})
                    if act == "sync":
                        if not LOCK.acquire(blocking=False):
                            return self.send(409, {"error": "An analysis is already running", "query": JOB["query"]})
                        threading.Thread(target=run_job, args=("Steam sync", lambda: cs2coach.sync_steam(sid)), daemon=True).start()
                        return self.send(200, {"started": True})
                except steamlink.SteamError as e:
                    return self.send(400, {"error": str(e)})
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self.send(500, {"error": str(e)})
        return self.send(404, {"error": "not found"})


def refresh_plan(sid):
    cs2coach.attach_plan(sid)
    build_app.write_player(sid)


def voice_status():
    try:
        import voice
    except Exception as e:
        return {"available": False, "error": str(e)}
    m = voice.REC.meta
    return {"available": True, "settings": voice.settings(), "device": voice.chosen_device(), "cs2_device": voice.cs2_voice_device(),
            "recording": bool(m), "level": round(voice.REC.peak, 4) if m else None,
            "current": m and {k: m[k] for k in ("id", "map", "start_iso", "device", "source")},
            "transcribing": voice.transcribing(), "recordings": voice.recordings()[:12]}


def voice_watch(every=15):
    """Stops an automatic recording when the game is gone, and refreshes the plan once a transcription is done."""
    import time
    done = set()
    while True:
        time.sleep(every)
        try:
            import gsi
            import voice
            voice.watchdog(gsi.state())
            p = voice.JOB.get("proc")
            if p and p.poll() is not None and voice.JOB.get("id") not in done:
                done.add(voice.JOB["id"])
                sid = config.settings().get("own_steamid")
                if sid and p.returncode == 0 and not LOCK.locked():
                    refresh_plan(sid)
        except Exception as e:
            print("microphone watch:", e, flush=True)


def auto_sync(every=1800):
    """Steam history connected: check for new matches at start-up, then every 30 minutes (only when idle)."""
    import time
    time.sleep(20)
    while True:
        while config.in_match():   # never start downloads and analyses during a match: after it
            time.sleep(30)
        s = config.settings()
        sid = str(s.get("own_steamid") or "")
        p = s.get("players", {}).get(sid, {})
        if sid.isdigit() and p.get("authcode") and p.get("auto_sync", True) and LOCK.acquire(blocking=False):
            print("Automatic Steam sync…", flush=True)
            run_job("Steam sync", lambda: cs2coach.sync_steam(sid))  # releases LOCK
        # teammates whose history code you added: their matches without you too
        for other, op in list(config.settings().get("players", {}).items()):
            if other != sid and other.isdigit() and op.get("authcode") and op.get("auto_sync", True) and LOCK.acquire(blocking=False):
                print(f"Automatic Steam sync of {op.get('name') or other}…", flush=True)
                run_job(f"Steam sync of {op.get('name') or other}", lambda o=other: cs2coach.sync_steam(o))
        time.sleep(every)


if __name__ == "__main__":
    if sys.stdout is None:  # started with pythonw (no console): keep a log file instead
        sys.stdout = sys.stderr = open(os.path.join(config.CACHE, "serve.log"), "a", encoding="utf-8", buffering=1)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(os.path.join(build_app.SITE, "index.json")):
        print("First build of the site…")
        build_app.build()
    ThreadingHTTPServer.allow_reuse_address = False  # a second instance must fail instead of sharing the port
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Coach CS2 is already running: open http://127.0.0.1:{PORT}/#ingame")
        if "--no-browser" not in sys.argv:
            webbrowser.open(f"http://127.0.0.1:{PORT}/#ingame")
        sys.exit(0)
    url = f"http://127.0.0.1:{PORT}/#ingame"
    print(f"Coach CS2: {url}  (Ctrl+C to stop)")
    if os.environ.get("COACH_TEST"):  # a test copy: leaves the game's settings, the Steam sync and the microphone alone
        print("test copy: game detection, sync and microphone left to the main app")
    else:
        try:
            import gsi
            if gsi.refresh(PORT):
                print("Game detection updated: restart CS2 so it picks it up.")
        except Exception as e:
            print("game detection:", e)
        threading.Thread(target=auto_sync, daemon=True).start()
        threading.Thread(target=voice_watch, daemon=True).start()
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()
