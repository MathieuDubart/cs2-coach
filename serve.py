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


def run_job(query, task=None):
    """One analysis at a time (search, or Steam history sync when task is given). The caller holds LOCK."""
    JOB.update(running=True, log=[], done=False, error=None, steamid=None, query=query, partial=None, players=None)
    cs2coach.LOG_HOOK = lambda m: JOB["log"].append(m)
    cs2coach.PARTIAL_HOOK = publish_partial
    try:
        res = task() if task else cs2coach.run_for(query)
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
        if u.path == "/api/gsi/status":
            import gsi
            return self.send(200, gsi.status())
        if u.path == "/api/team/suggest":
            import team
            sid = (q.get("sid") or [""])[0]
            return self.send(200, team.suggestions(sid) if sid.isdigit() else [])
        if u.path in ("/index.json", "/pros.json") or u.path.startswith(("/players/", "/radars/", "/replays/", "/teams/")):
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
                return self.redirect("/?steam=refus#steam")
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
            return self.redirect("/?steam=ok#steam")
        return self.send(404, {"error": "introuvable"})

    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        """Journal check-ins and experiments: saved in out/, then the player's plan and page are rebuilt."""
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send(400, {"error": "requête invalide"})
        if u.path == "/api/gsi":  # CS2 Game State Integration: the game itself, many times per round
            import gsi
            ok = gsi.update(body)
            if ok:
                try:
                    import voice
                    if voice.settings().get("auto") or voice.REC.recording():
                        voice.on_gsi(gsi.state())
                except Exception as e:
                    print("calls :", e, flush=True)
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
                        return self.send(409, {"error": "Une transcription est déjà en cours."})
                elif act == "delete":
                    rid = str(body.get("id") or "")
                    if re.fullmatch(r"[\w-]+", rid):
                        voice.delete(rid)
                else:
                    return self.send(404, {"error": "introuvable"})
            except Exception as e:
                return self.send(400, {"error": f"Micro : {e}"})
            return self.send(200, voice_status())
        if u.path == "/api/gsi/site":  # the player marks where the T attacked
            import gsi
            try:
                ok = gsi.set_site(int(body.get("round")), body.get("site"))
            except (TypeError, ValueError):
                return self.send(400, {"error": "round invalide"})
            return self.send(200 if ok else 409, gsi.state())
        if u.path in ("/api/gsi/install", "/api/gsi/uninstall"):
            import gsi
            try:
                return self.send(200, gsi.install(PORT) if u.path.endswith("install") and not u.path.endswith("uninstall") else gsi.uninstall())
            except (ValueError, OSError) as e:
                return self.send(400, {"error": str(e)})
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
                            return self.send(409, {"error": "Une analyse est déjà en cours", "query": JOB["query"]})
                        threading.Thread(target=run_job, args=("Synchronisation Steam", lambda: cs2coach.sync_steam(sid)), daemon=True).start()
                        return self.send(200, {"started": True})
                except steamlink.SteamError as e:
                    return self.send(400, {"error": str(e)})
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self.send(500, {"error": str(e)})
        return self.send(404, {"error": "introuvable"})


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
            print("surveillance du micro :", e, flush=True)


def auto_sync(every=1800):
    """Steam history connected: check for new matches at start-up, then every 30 minutes (only when idle)."""
    import time
    time.sleep(20)
    while True:
        s = config.settings()
        sid = str(s.get("own_steamid") or "")
        p = s.get("players", {}).get(sid, {})
        if sid.isdigit() and p.get("authcode") and p.get("auto_sync", True) and LOCK.acquire(blocking=False):
            print("Synchronisation Steam automatique…", flush=True)
            run_job("Synchronisation Steam", lambda: cs2coach.sync_steam(sid))  # releases LOCK
        time.sleep(every)


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
    if os.environ.get("COACH_TEST"):  # a test copy: leaves the game's settings, the Steam sync and the microphone alone
        print("copie de test : détection de la partie, synchronisation et micro laissés à l'application principale")
    else:
        try:
            import gsi
            if gsi.refresh(PORT):
                print("Détection de la partie mise à jour : relance CS2 pour qu'il la prenne en compte.")
        except Exception as e:
            print("détection de la partie :", e)
        threading.Thread(target=auto_sync, daemon=True).start()
        threading.Thread(target=voice_watch, daemon=True).start()
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()
