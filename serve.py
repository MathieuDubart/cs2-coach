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


# the base grows by itself (grow.py, its own process at the lowest priority): started and stopped in Settings, back
# on after a restart of the app; its state in out/grow.json, its switch in out/grow_ctl.json
GROW_STATE = os.path.join(config.OUT, "grow.json")
GROW_CTL = os.path.join(config.OUT, "grow_ctl.json")


def grow_alive():
    pid = (config.read_json(GROW_STATE, {}) or {}).get("pid")
    try:
        import psutil
        return bool(pid) and any("grow.py" in a for a in psutil.Process(pid).cmdline())
    except Exception:
        return False


def grow_start():
    if grow_alive():
        return
    import subprocess
    subprocess.Popen([sys.executable, "grow.py"], cwd=os.path.dirname(os.path.abspath(__file__)),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "IDLE_PRIORITY_CLASS", 0))


def grow_status():
    st = config.read_json(GROW_STATE, {}) or {}
    c = config.read_json(GROW_CTL, {}) or {}
    tail = []
    try:
        with open(os.path.join(config.OUT, "grow.log"), encoding="utf-8") as f:
            tail = [x.rstrip() for x in f.readlines()[-6:]]
    except OSError:
        pass
    import shutil
    return {"on": bool(c.get("on")), "target": int(c.get("target") or 5000), "alive": grow_alive(), "status": st.get("status"),
            "n": st.get("n"), "codes": len(st.get("codes") or []), "players": len(st.get("players") or []),
            "looked": len(st.get("looked") or {}), "counts": st.get("counts") or {}, "updated": st.get("updated"),
            "free_gb": round(shutil.disk_usage(config.CACHE).free / 2 ** 30), "log": tail}


def grow_wait():
    """A match the base-growing loop is extracting: the app's analysis waits for its end (they write the same files)."""
    t = time.time()
    while time.time() - t < 300:
        st = config.read_json(GROW_STATE, {}) or {}
        if not st.get("step") or not grow_alive():
            return
        if time.time() - t < 2.5:
            cs2coach.log("The base-growing loop finishes its current match first…")
        time.sleep(2)


def run_job(query, task=None, extra=None):
    """One analysis at a time (search, or Steam history sync when task is given). The caller holds LOCK.
    extra: what the page shows at the end (the view and the match of a re-analysis)."""
    try:   # everything inside: the lock is released whatever happens
        JOB.update({"running": True, "log": [], "done": False, "error": None, "steamid": None, "query": query, "partial": None,
                    "players": None, "view": None, "match": None, **(extra or {})})
        cs2coach.LOG_HOOK = lambda m: JOB["log"].append(m)
        cs2coach.PARTIAL_HOOK = publish_partial
        grow_wait()
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


# the app's addresses (like csrep's): the page is served there, and reads them
APP_PAGES = re.compile(r"/(?:player/\d{17}(?:/[a-z]+)?|match/[A-Za-z0-9-]{1,40}|team|players|pros|settings)/?")


def match_info(code):
    """/match/<match id or share code>: its id, share code, map, time, whether its demo is analyzed, and the analyzed
    players who played it (you first, full profiles before light ones)."""
    import matchlist
    if re.fullmatch(cs2coach.SHARECODE_RE, code):
        try:
            mid, sc = str(matchlist.decode_sharecode(code)[0]), code
        except (ValueError, OverflowError):   # the shape of a share code, not one
            return None
    elif code.isdigit():
        mid, sc = code, None
    else:
        return None
    e = cs2coach.registry().get(mid) or {}
    d = os.path.join(config.DEEP, mid)
    ids = [str(76561197960265728 + int(a)) for a in e.get("accounts") or [] if a]
    if not ids and os.path.isfile(os.path.join(d, "samples.parquet")):
        import pandas as pd
        ids = [str(int(x)) for x in pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["steamid"]).steamid.unique() if x]
    idx = {x["steamid"]: x for x in load_index()}
    own = str(config.settings().get("own_steamid") or "")
    ps = sorted((x for x in dict.fromkeys(ids) if x in idx), key=lambda x: (x != own, bool(idx[x].get("light"))))
    return {"id": mid, "code": sc or e.get("sharecode"), "map": (config.read_json(os.path.join(d, "meta.json"), {}) or {}).get("map"),
            "time": e.get("time"), "analyzed": os.path.isdir(d), "players": ps}


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
        if u.path in ("/", "/index.html") or APP_PAGES.fullmatch(u.path):
            # standards mode (the claude.ai host adds this wrapper itself when publishing)
            head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">'
            return self.send(200, head + build_app.shell_html(load_index(), local=True) + "</body></html>", "text/html; charset=utf-8")
        if u.path == "/api/voice/status":
            return self.send(200, voice_status())
        if u.path == "/api/coach/status":
            import chatcalls
            return self.send(200, chatcalls.status())
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
        if u.path == "/api/train":   # the training server, your situations to play again, your tries
            import replay
            sid = (q.get("sid") or [""])[0] or str(config.settings().get("own_steamid") or "")
            try:
                sc, err = (replay.scenarios(sid)[:40] if sid.isdigit() else []), None
            except Exception as e:
                sc, err = [], str(e)
            try:
                import train
                prog, maps_ = train.summary(), (train.maps(sid) if sid.isdigit() else {})
            except Exception as e:
                prog, maps_, err = None, {}, err or str(e)
            return self.send(200, {"status": replay.status(), "scenarios": sc, "results": replay.results(), "progress": prog,
                                   "maps": maps_, "error": err})
        if u.path == "/api/team/suggest":
            import team
            sid = (q.get("sid") or [""])[0]
            return self.send(200, team.suggestions(sid) if sid.isdigit() else [])
        if u.path in ("/index.json", "/pros.json") or u.path.startswith(("/players/", "/radars/", "/replays/", "/teams/", "/nadecat/")):
            f = os.path.normpath(os.path.join(build_app.SITE, u.path.lstrip("/")))
            rm = re.fullmatch(r"/replays/(\d{17})/(\d{6,20})\.json", u.path)
            if rm and not os.path.isfile(f):   # a 2D replay not made yet: from the match's detailed extraction, now
                try:
                    import deepdive
                    import shutil
                    src = deepdive.ensure_replay(rm.group(1), rm.group(2))
                    if src:
                        os.makedirs(os.path.dirname(f), exist_ok=True)
                        shutil.copy(src, f)
                except Exception as e:
                    print("replay:", e, flush=True)
            if f.startswith(os.path.normpath(build_app.SITE) + os.sep) and os.path.isfile(f):
                return self.send(200, config._retry(lambda: open(f, "rb").read(), f))
            return self.send(404, {"error": "not found"})
        if u.path == "/api/match":   # an address /match/<match id or share code>
            m = match_info((q.get("code") or [""])[0].strip())
            return self.send(200, m) if m else self.send(404, {"error": "not a match id or share code"})
        if u.path == "/api/grow":   # the base-growing loop: its state (Settings)
            return self.send(200, grow_status())
        if u.path == "/api/codes":   # the share code of each match (the addresses /match/<share code>)
            return self.send(200, {k: e["sharecode"] for k, e in cs2coach.registry().items() if e.get("sharecode")})
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
                return self.redirect("/settings?steam=refused")
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
            return self.redirect("/settings?steam=ok")
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
                    voice.save_settings(**{k: body[k] for k in ("auto", "device", "live") if k in body})
                    if body.get("live") is False:
                        voice.LIVE.stop()
                elif act == "start":
                    g = gsi.state()
                    voice.pause_transcription()
                    voice.REC.start(g.get("map"), body.get("sid") or config.settings().get("own_steamid"), "manual")
                    voice.LIVE.start(g.get("map"))
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
        if u.path == "/api/coach/paths":   # the page's paths this round: numpad 1-2-3 say them in the team chat
            import chatcalls
            return self.send(200 if chatcalls.write(body.get("paths"), body.get("extra")) else 400, {})
        if u.path.startswith("/api/train/"):   # the training server (separate copy of the game, 127.0.0.1 only)
            import replay
            act = u.path.rsplit("/", 1)[-1]
            try:
                if act == "play":
                    if config.in_match() and not replay.on_server():
                        return self.send(409, {"error": "A match is running: training after it."})
                    mid, kind, mode = str(body.get("mid") or ""), body.get("kind") or "death", body.get("mode") or "actor"
                    if not mid.isdigit() or kind not in ("death", "clutch") or mode not in ("actor", "spec"):
                        return self.send(400, {"error": "invalid situation"})
                    sid = str(body.get("sid") or config.settings().get("own_steamid") or "")
                    return self.send(200, replay.play(sid, mid, int(body.get("round")), kind, mode, int(body["diff"]) if body.get("diff") is not None else 2))
                if act == "session":   # one Play: the whole training (server, session, the game sent to it)
                    if config.in_match() and not replay.on_server():
                        return self.send(409, {"error": "A match is running: training after it."})
                    import train
                    sid = str(body.get("sid") or config.settings().get("own_steamid") or "")
                    minutes = max(5, min(90, int(body.get("minutes") or 20)))
                    where = str(body.get("where") or "random")
                    if not re.fullmatch(r"random|mix|(de|cs|ar)_\w+", where):
                        return self.send(400, {"error": "invalid map"})
                    diff = int(body["diff"]) if body.get("diff") is not None else 2
                    return self.send(200, train.play(sid, minutes, where, diff))
                if act == "stop":
                    return self.send(200, replay.stop())
                if act == "cmd":   # the plugin's commands: again, next, previous, spec, difficulty
                    c = str(body.get("cmd") or "")
                    if not re.fullmatch(r"r|n|p|spec|stop|diff [0-3]", c):
                        return self.send(400, {"error": "unknown command"})
                    replay.rcon(f"css_{c}")
                    return self.send(200, replay.status())
            except (OSError, RuntimeError, ValueError, StopIteration) as e:
                return self.send(400, {"error": str(e) or "training server error"})
            return self.send(404, {"error": "not found"})
        if u.path in ("/api/grow/start", "/api/grow/stop"):   # the base-growing loop: on until the target, or off
            on = u.path.endswith("start")
            try:
                target = max(100, min(20000, int(body.get("target") or 5000)))
            except (TypeError, ValueError):
                return self.send(400, {"error": "invalid target"})
            config.write_json(GROW_CTL, {"on": on, "target": target})
            if on:
                grow_start()
            return self.send(200, grow_status())
        if u.path == "/api/live/log":   # what the In game page shows, a few times per round: checked after the match
            import livecheck
            return self.send(200 if livecheck.log(body) else 400, {})
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
                    return self.send(400, {"error": "unknown action"})
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
            "transcribing": voice.transcribing(), "recordings": voice.recordings()[:12],
            "live": {"on": voice.settings().get("live", True), "running": voice.LIVE.running(), "last": voice.LIVE.last}}


def voice_watch(every=15):
    """Stops an automatic recording when the game is gone, refreshes the plan once a transcription is done, and
    transcribes again the recordings a match stopped, one by one, while no map is loaded."""
    import time
    done, failed = set(), set()
    while True:
        time.sleep(every)
        try:
            import gsi
            import voice
            voice.watchdog(gsi.state())
            import replay
            replay.idle_check()   # the training server stops itself 20 min after you left it
            p = voice.JOB.get("proc")
            if p and p.poll() is not None and voice.JOB.get("id") not in done:
                done.add(voice.JOB["id"])
                if p.returncode != 0:
                    failed.add(voice.JOB["id"])
                sid = config.settings().get("own_steamid")
                if sid and p.returncode == 0 and not LOCK.locked():
                    refresh_plan(sid)
            gs = gsi.state() or {}
            if not gs.get("map") or gs.get("age", 0) > 120:   # the game in its menu or closed: what a match stopped, now
                voice.resume_pending(failed)
        except Exception as e:
            print("microphone watch:", e, flush=True)


def auto_sync(every=1800):
    """Only when you turned it on in Settings (off by default: the Update button in the header does it when you want):
    new matches at start-up, then every 30 minutes, never during a match."""
    import time
    time.sleep(20)
    while True:
        while config.in_match():   # never start downloads and analyses during a match: after it
            time.sleep(30)
        s = config.settings()
        sid = str(s.get("own_steamid") or "")
        p = s.get("players", {}).get(sid, {})
        if sid.isdigit() and p.get("authcode") and p.get("auto_sync", False) and LOCK.acquire(blocking=False):
            print("Automatic Steam sync…", flush=True)
            run_job("Steam sync", lambda: cs2coach.sync_steam(sid))  # releases LOCK
        # teammates whose history code you added: their matches without you too
        for other, op in list(config.settings().get("players", {}).items()):
            if other != sid and other.isdigit() and op.get("authcode") and op.get("auto_sync", False) and LOCK.acquire(blocking=False):
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
        import chatcalls
        threading.Thread(target=chatcalls.watch, daemon=True).start()   # numpad keys of the paths: the focus
        if (config.read_json(GROW_CTL, {}) or {}).get("on"):   # the base was growing: it goes on
            threading.Timer(60, grow_start).start()
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()
