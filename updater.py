"""The app's updates on a player's PC (05/10): wily.valentingassend.com/releases/latest.json says what is published,
its signature (latest.json.sig) is checked with the coach's public key (release_key.pub, in the code since the first
install): nothing unsigned is installed, a hosting account broken into could not push code to the players.

Three parts, each one only when it changed:
- code: the app's files, over the install (not out/, python/ or cache/); the app restarts;
- base: the base's references in out/ (the player's settings, matches, profile, voice never: a table of a match the
  player has here stays theirs, with their real rows); their profile is analyzed again with it;
- runtime: Python and its libraries; replaced while the app is stopped (its files are in use), then it restarts.

The check runs at start-up then every 30 minutes, never during a match. Automatic updates (08/10, on unless the player
turns them off in Settings): the new parts are downloaded when the app has nothing to do, and installed when nobody
uses it (no CS2, no analysis, no recording, no Wily page open for 5 minutes), so the restart is never in the way.
The coach's own app (role "server") makes the releases and never updates itself."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile

import config

URL = os.environ.get("COACH_UPDATE_URL") or "https://wily.valentingassend.com/releases/"
STATE_F = os.path.join(config.OUT, "update.json")
DL = os.path.join(config.OUT, "updates")
PUB_F = os.path.join(config.HERE, "release_key.pub")
VER_F = os.path.join(config.HERE, "VERSION.json")
EVERY = 6 * 3600
UA = "CoachCS2-updater"
ST = {"busy": None, "part": None, "done": 0, "total": 0, "error": None, "restarting": False}
# never written by a base update: what is the player's own (a base zip has none of it; a defense in depth)
MINE = {"settings.json", "players", "deep", "scenarios", "voice", "live", "gsi", "journal", "experiments", "teams",
        "updates", "contrib.json", "update.json", "refresh.json", "refresh_ctl.json", "train.json", "train_progress.json",
        "playing.json", "account.json"}


def enabled():
    return config.role() == "client" and os.path.exists(PUB_F) and os.path.exists(VER_F)


def auto_on():
    """Automatic updates (08/10): on unless the player turned them off in Settings."""
    return config.settings().get("auto_update", True) is not False


def current():
    v = config.read_json(VER_F, {}) or {}
    rt = os.path.join(config.HERE, "python", ".runtime")
    base = config.read_json(os.path.join(config.OUT, "base_pack.json"), {}) or {}
    return {"app": v.get("app"), "build": v.get("build"), "runtime": open(rt).read().strip() if os.path.exists(rt) else v.get("runtime"),
            "base": base.get("version"), "matches": base.get("matches")}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=timeout)


def verify(raw, sig):
    """True when the coach's key signed these bytes."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(open(PUB_F).read().strip())).verify(base64.b64decode(sig), raw)
        return True
    except (InvalidSignature, ValueError):
        return False


def _available(man, cur):
    out = []
    pub = (man.get("code") or {}).get("build")   # a new publication of the same version has a new build
    if man.get("code") and ((pub and pub != cur.get("build")) or (not pub and man.get("app") != cur["app"])):
        out.append({"part": "code", "version": man["app"] + (f" · build {pub}" if pub else ""), "size": man["code"]["size"]})
    if man.get("runtime") and man["runtime"].get("key") != cur["runtime"]:
        out.append({"part": "runtime", "version": man["runtime"]["key"], "size": man["runtime"]["size"]})
    if man.get("base") and str(man["base"].get("version") or "") > str(cur["base"] or ""):   # YYYYMMDD-HHMM: only a newer base
        out.append({"part": "base", "version": man["base"]["version"], "size": man["base"]["size"], "matches": man["base"].get("matches")})
    return out


def check(force=False):
    """latest.json and its signature: what can be installed. Kept in out/update.json."""
    st = config.read_json(STATE_F, {}) or {}
    if not enabled() or (not force and time.time() - st.get("checked", 0) < EVERY):
        return status()
    try:
        raw = _get(URL + "latest.json").read()
        sig = _get(URL + "latest.json.sig").read().decode().strip()
        if not verify(raw, sig):
            raise ValueError("this update isn't signed by my author: I won't install it")
        man = json.loads(raw)
        st.update(checked=time.time(), latest=man, raw=raw.decode(), sig=sig, error=None)
    except Exception as e:
        st.update(checked=time.time(), error=f"{type(e).__name__}: {str(e)[:160]}")
    config.write_json(STATE_F, st)
    return status()


def status():
    st = config.read_json(STATE_F, {}) or {}
    cur = current()
    man = st.get("latest") or {}
    return {"enabled": enabled(), "auto": auto_on(), "current": cur, "checked": st.get("checked"), "error": st.get("error"),
            "latest": {k: man.get(k) for k in ("app", "released", "notes")} if man else None,
            "available": _available(man, cur) if man and enabled() else [], "progress": dict(ST)}


def _download(entry):
    """One part into out/updates, its sha256 checked against the signed manifest."""
    os.makedirs(DL, exist_ok=True)
    path = os.path.join(DL, entry["file"])
    if os.path.exists(path) and _sha(path) == entry["sha256"]:
        return path
    ST.update(done=0, total=entry["size"])
    h = hashlib.sha256()
    with _get(URL + entry["file"], timeout=60) as r, open(path + ".part", "wb") as f:
        for b in iter(lambda: r.read(1 << 20), b""):
            f.write(b)
            h.update(b)
            ST["done"] += len(b)
    if h.hexdigest() != entry["sha256"]:
        os.remove(path + ".part")
        raise ValueError(f"{entry['file']}: not the file my author signed, I won't install it")
    os.replace(path + ".part", path)
    return path


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _inside(root, name):
    p = os.path.normpath(os.path.join(root, name))
    return p if p == root or p.startswith(root + os.sep) else None


def apply_code(path):
    """The app's files over the install: never out/, python/, cache/ (a zip naming them is refused)."""
    root = os.path.normpath(config.HERE)
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            first = m.filename.replace("\\", "/").split("/")[0]
            if first in ("out", "python", "cache") or not _inside(root, m.filename):
                raise ValueError(f"{m.filename}: not a file of the app")
        z.extractall(root)


def apply_base(path):
    """The base's references in out/: what is the player's own stays (MINE), and so does every table of a match they
    have here (out/deep/<id>): it holds their real rows."""
    root = os.path.normpath(config.OUT)
    old = config.read_json(os.path.join(root, "base_pack.json"), {}) or {}
    kept = 0
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            name = m.filename.replace("\\", "/")
            parts = name.split("/")
            stem = parts[-1][:-8] if parts[-1].endswith(".parquet") else None
            if parts[0] in MINE or not _inside(root, name):
                continue
            if stem and stem.isdigit() and os.path.isdir(os.path.join(root, "deep", stem)):
                kept += 1
                continue
            z.extract(m, root)
    new = config.read_json(os.path.join(root, "base_pack.json"), {}) or {}
    if old.get("player_matches"):   # the matches that came from the base with a player's package: never shared back
        new["player_matches"] = old["player_matches"]
        config.write_json(os.path.join(root, "base_pack.json"), new)
    return kept


def _restart(runtime_zip=None):
    """The app stops, a small script waits for it, puts the new runtime in place if there is one, and starts it again.
    Windows' own tools by their full path (a PATH with Git's tools first gave it GNU find: 05/10), in a hidden console
    of its own, out of the app's job (it must outlive the app); each step written to out/updates/restart.log."""
    bat = os.path.join(DL, "restart.bat")
    logf = os.path.join(DL, "restart.log")
    here = config.HERE
    sysd = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    tasklist, find, ping, tar = (os.path.join(sysd, x) for x in ("tasklist.exe", "find.exe", "PING.EXE", "tar.exe"))
    pid = os.getpid()
    lines = ["@echo off", f'echo %date% %time% waiting for {pid} >> "{logf}"', ":wait",
             f'"{tasklist}" /FI "PID eq {pid}" /NH 2>nul | "{find}" "{pid}" >nul && ("{ping}" -n 2 127.0.0.1 >nul & goto wait)',
             f'echo %date% %time% stopped >> "{logf}"']
    if runtime_zip:   # unpacked beside, then swapped: a failed step leaves the old runtime in place
        new, old = os.path.join(here, "_runtime_new"), os.path.join(here, "_runtime_old")
        lines += [f'rmdir /s /q "{new}" 2>nul', f'mkdir "{new}"', f'"{tar}" -xf "{runtime_zip}" -C "{new}" || goto start',
                  f'if not exist "{os.path.join(new, "python", "python.exe")}" goto start',
                  f'rmdir /s /q "{old}" 2>nul', f'move "{os.path.join(here, "python")}" "{old}" || goto start',
                  f'move "{os.path.join(new, "python")}" "{os.path.join(here, "python")}" || move "{old}" "{os.path.join(here, "python")}"',
                  f'rmdir /s /q "{old}" 2>nul', f'rmdir /s /q "{new}" 2>nul', f'echo %date% %time% runtime replaced >> "{logf}"', ":start"]
    lines += [f'cd /d "{here}"', "set PYTHONNOUSERSITE=1", f'start "" "{os.path.join(here, "python", "pythonw.exe")}" -s serve.py --no-browser',
              f'echo %date% %time% started >> "{logf}"', '(goto) 2>nul & del "%~f0"']
    open(bat, "w", encoding="utf-8", newline="\r\n").write("\r\n".join(lines) + "\r\n")
    flags = config.NO_WINDOW | 0x00000200   # a hidden console of its own, a process group of its own
    try:
        subprocess.Popen([os.path.join(sysd, "cmd.exe"), "/c", bat], cwd=here, creationflags=flags | 0x01000000, close_fds=True)   # out of the job
    except OSError:   # a job that does not allow it
        subprocess.Popen([os.path.join(sysd, "cmd.exe"), "/c", bat], cwd=here, creationflags=flags, close_fds=True)
    ST["restarting"] = True
    threading.Timer(1.5, lambda: os._exit(0)).start()   # the answer reaches the page first


def apply(parts=None):
    """Downloads and installs the parts asked (all the available ones by default), in a thread."""
    if ST["busy"]:
        return status()
    if config.in_match():
        raise ValueError("A match is running: update after it.")
    st = config.read_json(STATE_F, {}) or {}
    raw, sig = (st.get("raw") or "").encode(), st.get("sig") or ""
    if not enabled() or not raw or not verify(raw, sig):   # checked again: out/update.json is a file anyone could edit
        raise ValueError("No signed update to install: check again.")
    man = json.loads(raw)
    todo = [a["part"] for a in _available(man, current()) if parts is None or a["part"] in parts]

    def run():
        ST.update(busy=True, error=None)
        try:
            got = {}
            for p in ("code", "base", "runtime"):
                if p in todo:
                    ST["part"] = p
                    got[p] = _download(man[p])
            ST["part"] = "installing"
            if "base" in got:
                apply_base(got["base"])
            if "code" in got:
                apply_code(got["code"])
            if "base" in got and "code" not in got and "runtime" not in got:
                _refresh_mine()   # the profile against the new base; the app itself is the same
            if "code" in got or "runtime" in got:
                _flag_refresh("base" in got)
                _restart(got.get("runtime"))
        except Exception as e:
            ST["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        finally:
            ST.update(busy=None, part=None)
    threading.Thread(target=run, daemon=True).start()
    return status()


def _refresh_mine():
    subprocess.Popen([sys.executable, "refresh_all.py", "--mine"], cwd=config.HERE, creationflags=config.NO_WINDOW)


def _flag_refresh(on):
    st = config.read_json(STATE_F, {}) or {}
    st["refresh_after_restart"] = bool(on)
    config.write_json(STATE_F, st)


def after_start():
    """At start-up: the profile analyzed again when a base came with a code update (flagged before the restart)."""
    st = config.read_json(STATE_F, {}) or {}
    if st.pop("refresh_after_restart", False):
        config.write_json(STATE_F, st)
        _refresh_mine()


def _fetched(man, avail):
    """True when every part to install is already downloaded and checked (out/updates: a file there passed its sha256)."""
    return bool(avail) and all(os.path.exists(os.path.join(DL, man[a["part"]]["file"])) for a in avail)


def watch(busy=None, quiet=None):
    """At start-up, then every 30 minutes: what is published. Automatic updates on: the parts downloaded while busy()
    says nothing (no CS2, no analysis, no recording), installed once quiet() too (no Wily page open for 5 minutes)."""
    if not enabled():
        return
    after_start()
    time.sleep(60)
    while True:
        if not config.in_match():
            try:
                check()
                st = config.read_json(STATE_F, {}) or {}
                man = json.loads(st.get("raw") or "{}")
                avail = _available(man, current()) if man else []
                if auto_on() and avail and not ST["busy"] and not (busy and busy()):
                    for a in avail:   # downloaded ahead, quietly (each one checked against the signed manifest, once)
                        if not os.path.exists(os.path.join(DL, man[a["part"]]["file"])):
                            _download(man[a["part"]])
                    if _fetched(man, avail) and (quiet is None or quiet()) and not (busy and busy()) and not config.in_match():
                        print("automatic update: installing " + ", ".join(a["part"] for a in avail), flush=True)
                        apply()
            except Exception as e:
                print("update:", e, flush=True)
        time.sleep(1800)
