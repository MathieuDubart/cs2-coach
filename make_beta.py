"""The app for another player's PC (05/10, the beta: "any player gets the same as me: the training server, the live
advice, everything"): one folder to unzip, with Python and its libraries inside, the code, the base's references, and
the player's own matches from the base.

    python make_beta.py --player <steamid64>            a player's first install: all of it, their matches from the base
    python make_beta.py --player <steamid64> --update   an update: the code, the base's references and their matches
                                                        from the base (their settings and profile stay: unzipped over
                                                        the old folder)

Always for one player: their own matches stay real in the base's tables (an update for nobody would turn them into
made-up ids on their PC).

Out: dist/CoachCS2/ and dist/CoachCS2-<date>[-<player>].zip.

What never leaves this PC: the settings (keys, codes, tokens), the voice, the other players' profiles, the raw demos,
the logs, the base loop's state. The base's tables are pseudonymized: the players of its matches get a stable made-up
SteamID (a keyed hash, in a range no Steam account uses; the key stays in out/pack_key.txt) and no name, except in the
player's own matches (theirs, as in their own demos) and in the pro matches (public). A last check refuses the package
when a real SteamID is left anywhere else."""
import ast
import glob
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

import config

DIST = os.path.join(config.HERE, "dist")
DL = os.path.join(DIST, "cache")
PY_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
# the versions this app runs with here: the players' copy behaves the same
REQS = {"demoparser2": "0.42.0", "pandas": "2.3.3", "numpy": "2.3.4", "pyarrow": "25.0.1", "pillow": "12.0.0", "psutil": "7.2.2",
        "scikit-learn": "1.7.2", "soundfile": "0.13.1", "sounddevice": "0.5.6", "soundcard": "0.4.6", "faster-whisper": "1.2.1"}
ENTRIES = ["serve", "refresh_all", "grow", "voice", "replay", "train", "build_app", "chatcalls", "focus", "heard", "cs2coach"]
FILES = ["app_template.html", "report_template.html"]
DIRS = ["maps", os.path.join("tools", "boiler")]
SERVER_ZIPS = ["mmsource.zip", "css-runtime.zip"]   # Metamod:Source and CounterStrikeSharp for the training server

LO, HI = 76561197960265728, 76561202255233023   # every Steam account (account ids up to 2^32)
FAKE_LO, FAKE_N = 76561190000000000, LO - 76561190000000000   # just below: no Steam account has one of these
NAME_COLS = {"name", "killer_name", "victim_name", "thrower_name", "attacker_name", "assister_name", "player_name"}
SID_RE = re.compile(r"(?<!\d)765611(?:979[6-9]|98\d\d|99\d\d|2[0-2]\d\d)\d{9}(?!\d)")
PER_MATCH = [os.path.join("population"), os.path.join("population", "buys"), os.path.join("population", "midround"),
             os.path.join("population", "routes"), os.path.join("population", "tside"), "style"]
# the pro matches (public, from HLTV): as they are; the pro references of a profile read their positions (proref)
PUBLIC = [os.path.join("population", "midround_pro"), os.path.join("population", "routes_pro"), "style_pro", "deep_pro"]
BASE_FILES = ["train_sites.json", "train_spots.json", "hostage.json", "cross.json", "cross_notes.json", os.path.join("pro", "matches.json")]
BASE_DIRS = ["lineups", "train_entries", os.path.join("site", "nadecat"), os.path.join("site", "radars")]
FRESH = 120   # a file the base loop wrote in the last 2 minutes may be half-written: left for the next package
SITUATIONS = 20   # situations to replay built per map of the player


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def fetch(url):
    os.makedirs(DL, exist_ok=True)
    p = os.path.join(DL, url.rsplit("/", 1)[-1])
    if not os.path.exists(p):
        log("download", url)
        urllib.request.urlretrieve(url, p + ".part")
        os.replace(p + ".part", p)
    return p


# ---------------------------------------------------------------- Python and its libraries

def runtime(dst):
    """python.org's embeddable Python 3.11 with the app's libraries: made once in dist/cache, copied into the package.
    Its ._pth puts the app's folder on the path (an embedded Python ignores the script's folder)."""
    key = hashlib.sha1(json.dumps([PY_URL, REQS], sort_keys=True).encode()).hexdigest()[:10]
    built = os.path.join(DL, f"python-{key}")
    py = os.path.join(built, "python.exe")
    if not os.path.exists(os.path.join(built, ".done")):
        shutil.rmtree(built, ignore_errors=True)
        zipfile.ZipFile(fetch(PY_URL)).extractall(built)
        pth = glob.glob(os.path.join(built, "python3*._pth"))[0]
        zname = os.path.basename(pth).replace("._pth", ".zip")
        open(pth, "w", encoding="utf-8").write(f"{zname}\n.\n..\nimport site\n")
        log("pip into the embedded Python…")
        subprocess.run([py, fetch(PIP_URL), "--no-warn-script-location"], check=True)
        log("the libraries…")
        subprocess.run([py, "-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check",
                        *[f"{k}=={v}" for k, v in REQS.items()]], check=True)
        subprocess.run([py, "-c", "import pandas, pyarrow, demoparser2, sklearn, psutil, PIL, soundfile, sounddevice, faster_whisper; print('libraries ok')"], check=True)
        open(os.path.join(built, ".done"), "w").write(key)
    if dst:
        # the libraries' own test suites (109 MB) stay out
        shutil.copytree(built, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".done", "__pycache__", "tests"))


# ---------------------------------------------------------------- the code

def modules():
    """The app's modules: everything its entry points import (the leftovers of other tools stay out), and the maps'
    zone modules map_analysis loads by name."""
    local = {f[:-3] for f in os.listdir(config.HERE) if f.endswith(".py")}
    seen, stack = set(), list(ENTRIES)
    while stack:
        m = stack.pop()
        if m in seen or m not in local:
            continue
        seen.add(m)
        for n in ast.walk(ast.parse(open(os.path.join(config.HERE, m + ".py"), encoding="utf-8").read())):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else (
                [n.module] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else [])
            stack += [x.split(".")[0] for x in names]
    return sorted(seen | {m for m in local if m.startswith("zones_")})


def copy_code(dst):
    ms = modules()
    for m in ms:
        shutil.copy2(os.path.join(config.HERE, m + ".py"), dst)
    for f in FILES:
        if os.path.exists(os.path.join(config.HERE, f)):
            shutil.copy2(os.path.join(config.HERE, f), dst)
    for d in DIRS:
        shutil.copytree(os.path.join(config.HERE, d), os.path.join(dst, d), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.ts"))
    pl = os.path.join(dst, "plugin")
    os.makedirs(os.path.join(pl, "CoachReplay", "bin", "out"), exist_ok=True)
    shutil.copy2(os.path.join(config.HERE, "plugin", "make_server.py"), pl)
    for f in ("CoachReplay.dll", "CoachReplay.pdb"):
        shutil.copy2(os.path.join(config.HERE, "plugin", "CoachReplay", "bin", "out", f), os.path.join(pl, "CoachReplay", "bin", "out"))
    sys.path.insert(0, os.path.join(config.HERE, "plugin"))
    import make_server
    for z in SERVER_ZIPS:
        shutil.copy2(make_server._zip(z), pl)
    open(os.path.join(dst, "requirements.txt"), "w", encoding="utf-8").write("".join(f"{k}=={v}\n" for k, v in REQS.items()))
    log(f"code: {len(ms)} modules")


# ---------------------------------------------------------------- the base, pseudonymized

class Pseudo:
    """Real SteamID -> a stable made-up one (HMAC-SHA256 with the server's key): the same player keeps one id across
    the base's tables (their matches still add up), and nobody without the key can go back to the account."""
    def __init__(self):
        f = os.path.join(config.OUT, "pack_key.txt")
        if not os.path.exists(f):
            open(f, "w").write(secrets.token_hex(32))
        self.key = bytes.fromhex(open(f).read().strip())
        self.memo = {}

    def __call__(self, sid):
        sid = int(sid)
        if sid not in self.memo:
            h = hmac.new(self.key, str(sid).encode(), hashlib.sha256).digest()
            self.memo[sid] = FAKE_LO + int.from_bytes(h[:8], "big") % FAKE_N
        return self.memo[sid]


def _ids_column(col, pseudo, keep=None):
    """A column with SteamIDs in it, every one replaced (keep: a mask of rows left as they are). None when it has none."""
    t = col.type
    if pa.types.is_dictionary(t):
        raise ValueError(f"dictionary column {t}: not handled")   # none in the base (05/10); refused rather than missed
    if pa.types.is_integer(t) or pa.types.is_floating(t):
        null = col.is_null().to_numpy(zero_copy_only=False) if col.null_count else None
        v = (col.fill_null(0) if col.null_count else col).to_numpy(zero_copy_only=False)
        with np.errstate(invalid="ignore"):
            real = (v >= LO) & (v <= HI)
        if null is not None:
            real &= ~null
        if keep is not None:
            real &= ~keep
        if not real.any():
            return None
        new = v.copy()
        new[real] = np.array([pseudo(x) for x in v[real].astype(np.int64)], dtype=v.dtype)
        return pa.array(new, type=t, mask=null)
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        vals = col.to_pylist()
        out, hit = [], False
        for i, x in enumerate(vals):
            if x is not None and x.isdigit() and LO <= int(x) <= HI and not (keep is not None and keep[i]):
                out.append(str(pseudo(x)))
                hit = True
            else:
                out.append(x)
        return pa.array(out, type=t) if hit else None
    return None


def pseudonymize(src, dst, pseudo, keep_match=None):
    """One table of the base: SteamIDs made up, names blank. keep_match: the match ids whose rows stay real (the
    player's own matches, in a table of every match)."""
    tb = pq.read_table(src)
    keep = None
    if keep_match and "match" in tb.column_names:
        keep = np.isin(np.array([str(x) for x in tb.column("match").to_pylist()]), list(keep_match))
    cols = []
    for name in tb.column_names:
        col = tb.column(name).combine_chunks()
        if name in NAME_COLS:
            v = col.to_pylist()
            new = pa.array([x if (keep is not None and keep[i]) or x is None else "" for i, x in enumerate(v)], type=col.type)
        else:
            new = _ids_column(col, pseudo, keep)
        cols.append(new if new is not None else col)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    pq.write_table(pa.Table.from_arrays(cols, schema=tb.schema), dst)


def lands(path):
    """Where each throw of the base landed in the world (x, y, z), from its match's demo extraction: the training's
    grenade drills show that very landing (train._land), and a player's PC has only its own matches' extractions."""
    import pandas as pd
    df = pd.read_parquet(path)
    key = ["match", "round", "type", "_x", "_y"]
    parts = []
    for mid in df["match"].astype(str).unique():
        f = os.path.join(config.DEEP, mid, "grenades.parquet")
        try:
            G = pd.read_parquet(f, columns=["round", "type", "X", "Y", "land_X", "land_Y", "land_Z"])
        except Exception:
            continue
        parts.append(G.assign(match=mid))
    L = pd.concat(parts, ignore_index=True)
    for d in (df, L):
        d["_x"], d["_y"] = d.X.round(0), d.Y.round(0)
    df["match"] = df["match"].astype(str)
    L = L.drop_duplicates(key)[key + ["land_X", "land_Y", "land_Z"]]
    out = df.merge(L, on=key, how="left").drop(columns=["_x", "_y"])
    assert len(out) == len(df)
    out.to_parquet(path, index=False)
    log(f"lineup landings: {int(out.land_X.notna().sum())} of {len(out)} throws")


def _settled(p):
    return time.time() - os.path.getmtime(p) > FRESH


def copy_base(dst, pseudo, mine):
    """The base's references: the summaries as they are (no player in them), the per-match tables pseudonymized
    (the player's own matches real), the pro tables and the lineup catalog as they are."""
    out = os.path.join(dst, "out")
    n = {"tables": 0, "skipped": 0}
    for d in PER_MATCH:
        src = os.path.join(config.OUT, d)
        for f in os.listdir(src):
            if not (f.endswith(".parquet") and f[:-8].isdigit()):
                continue
            s, t = os.path.join(src, f), os.path.join(out, d, f)
            try:
                if not _settled(s):
                    raise ValueError("being written")
                if f[:-8] in mine or d.endswith("tside"):   # tside: rounds and zones, no player in it
                    pq.read_metadata(s)
                    os.makedirs(os.path.dirname(t), exist_ok=True)
                    shutil.copy2(s, t)
                else:
                    pseudonymize(s, t, pseudo)
                n["tables"] += 1
            except Exception as e:
                n["skipped"] += 1
                print("  skipped", os.path.join(d, f), type(e).__name__, str(e)[:80])
    pseudonymize(os.path.join(config.OUT, "population", "nades.parquet"), os.path.join(out, "population", "nades.parquet"), pseudo, keep_match=mine)
    lands(os.path.join(out, "population", "nades.parquet"))
    for f in glob.glob(os.path.join(config.OUT, "population", "*.json")):
        shutil.copy2(f, os.path.join(out, "population"))
    for d in PUBLIC + BASE_DIRS:
        shutil.copytree(os.path.join(config.OUT, d), os.path.join(out, d), dirs_exist_ok=True)
    for f in BASE_FILES:
        if os.path.exists(os.path.join(config.OUT, f)):
            os.makedirs(os.path.dirname(os.path.join(out, f)), exist_ok=True)
            shutil.copy2(os.path.join(config.OUT, f), os.path.join(out, f))
    shutil.copy2(os.path.join(config.OUT, "site", "pros.json"), os.path.join(out, "site"))
    matches = len([f for f in os.listdir(os.path.join(out, "population")) if f.endswith(".parquet") and f[:-8].isdigit()])
    config.write_json(os.path.join(out, "base_pack.json"), {"built": int(time.time()), "matches": matches,
                                                            "players": len(pseudo.memo), "version": time.strftime("%Y%m%d")})
    log(f"base: {n['tables']} tables ({n['skipped']} left for the next package), {matches} matches, {len(pseudo.memo)} players pseudonymized")
    return matches


def copy_player(dst, sid, update):
    """The player's own matches from the base (their demos as extracted here: Valve keeps a demo about a month), their
    profile, their team. -> their match ids."""
    import cs2coach
    out = os.path.join(dst, "out")
    mine = set(cs2coach.player_matches(sid))
    for mid in mine:
        shutil.copytree(os.path.join(config.DEEP, mid), os.path.join(out, "deep", mid), dirs_exist_ok=True)
    if not update:   # their profile: from here the first time, then their PC keeps it up to date
        shutil.copytree(config.player_dir(sid), os.path.join(out, "players", sid), dirs_exist_ok=True)
    for f in glob.glob(os.path.join(config.OUT, "teams", "*.json")):
        t = config.read_json(f, {}) or {}
        if sid in {str(m.get("steamid") if isinstance(m, dict) else m) for m in t.get("members") or []}:
            os.makedirs(os.path.join(out, "teams"), exist_ok=True)
            shutil.copy2(f, os.path.join(out, "teams"))
    log(f"player {config.display_name(sid)}: {len(mine)} matches, their profile")
    return mine


def _situation(a):
    """One situation of the player's matches built from its demo, into the package (a worker process)."""
    import replay
    sid, s, out = a
    replay.SCEN = os.path.join(out, s["mid"])
    try:
        replay.build(sid, s["mid"], s["round"], s["kind"], s.get("t") if s["kind"] == "clutch" else None)
        return True
    except Exception as e:
        print("  situation", s["id"], type(e).__name__, str(e)[:100], flush=True)
        return False


def situations(dst, sid, per_map=SITUATIONS):
    """The training replays the situations of a player's matches from their demos, which stay here (200-300 MB each):
    the most important ones of each map are built here (4-6 s each) and go in the package (replay.PREBUILT)."""
    import multiprocessing
    import replay
    sc = replay.scenarios(sid, n=1000)   # the worst first
    pick, per = [], {}
    for s in sc:
        if per.get(s["map"], 0) < per_map:
            per[s["map"]] = per.get(s["map"], 0) + 1
            pick.append(s)
    cache = os.path.join(DL, "scenarios", sid)   # built once: the next package only builds the new ones
    todo = [s for s in pick if not os.path.exists(os.path.join(cache, s["mid"], f"{s['id']}.json"))]
    if todo:
        with multiprocessing.Pool(4) as pool:
            pool.map(_situation, [(sid, s, cache) for s in todo], chunksize=1)
    out, n = os.path.join(dst, "out", "scenarios"), 0
    for s in pick:
        f = os.path.join(cache, s["mid"], f"{s['id']}.json")
        if os.path.exists(f):
            os.makedirs(os.path.join(out, s["mid"]), exist_ok=True)
            shutil.copy2(f, os.path.join(out, s["mid"]))
            n += 1
    log(f"situations to replay: {n} of {len(pick)} ({len(todo)} built now; {len(sc)} in their matches, the {per_map} most important of each map)")


# ---------------------------------------------------------------- the last check

def check(dst, mine, sid):
    """No real SteamID in the package outside the player's own matches, their profile and team, and the pro data."""
    out = os.path.join(dst, "out")
    ok_dirs = [os.path.join(out, d) for d in ["deep", "scenarios", os.path.join("players", sid), "teams"] + PUBLIC]
    ok_files = {os.path.join(out, "site", "pros.json"), os.path.join(out, "pro", "matches.json"),
                os.path.join(out, "settings.json")}   # settings: their own id
    bad = []
    for root, _, fs in os.walk(out):
        if any(root == d or root.startswith(d + os.sep) for d in ok_dirs):
            continue
        for f in fs:
            p = os.path.join(root, f)
            if p in ok_files or f[:-8] in mine:
                continue
            if f.endswith(".parquet"):
                tb = pq.read_table(p)
                keep = (np.isin(np.array([str(x) for x in tb.column("match").to_pylist()]), list(mine))
                        if mine and "match" in tb.column_names else None)   # a table of every match: their own rows
                for c in tb.column_names:
                    if c in NAME_COLS:
                        if any(x for i, x in enumerate(tb.column(c).to_pylist()) if keep is None or not keep[i]):
                            bad.append(f"{p}: names in {c}")
                    elif _ids_column(tb.column(c).combine_chunks(), lambda x: 0, keep) is not None:
                        bad.append(f"{p}: SteamIDs in {c}")
            elif f.endswith((".json", ".jsonl", ".txt", ".csv")):
                if SID_RE.search(open(p, encoding="utf-8", errors="replace").read()):
                    bad.append(f"{p}: a SteamID")
    for f in ("settings.json", "pack_key.txt", "account.json", "train.json", "train_progress.json"):
        if os.path.exists(os.path.join(out, f)) and f != "settings.json":
            bad.append(f"{f} must stay on the coach's PC")
    if bad:
        raise SystemExit("REFUSED, personal data left:\n  " + "\n  ".join(bad[:20]))
    log("check: no real SteamID or name outside the player's own matches and the pro data")


# ---------------------------------------------------------------- the rest

LAUNCHER = r"""@echo off
rem Coach CS2: the app on this PC (http://127.0.0.1:8765). Its window stays hidden; the page opens in your browser.
cd /d "%~dp0"
start "" "%~dp0python\pythonw.exe" serve.py
"""
AUTOSTART = r"""@echo off
rem Starts Coach CS2 in the background each time you sign in to Windows (Win+R, shell:startup to remove it).
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%STARTUP%\Coach CS2.lnk'); $s.TargetPath='%~dp0python\pythonw.exe'; $s.Arguments='serve.py --no-browser'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo Coach CS2 now starts with Windows: http://127.0.0.1:8765
pause
"""
README = """COACH CS2 (beta)
================

Your coach for CS2: the live guide on your second screen, the warm-up before you play (map sheets and the training
server with bots), and the review after your matches. Everything runs on this PC.

INSTALL
1. Unzip this folder where you want to keep it, on a drive with a few GB free (not in Program Files).
2. Double-click "Coach CS2.bat". The app opens in your browser at http://127.0.0.1:8765
   (Windows may ask to confirm the first time: the app is not signed yet.)
3. Settings (the gear, top right):
   - Steam: your Steam Web API key and your match history authentication code (the links to get them are on the
     page). They stay in out/settings.json on this PC and only go to Steam's official API.
   - Game detection: turn it on, then restart CS2.
   - Microphone (optional): your calls, recorded and transcribed on this PC.
4. The numpad keys of the live guide: in Steam, CS2 > Properties > Launch options, add  -condebug
   (CS2 then writes the console log the app reads), and in CS2's console, once:  exec coach_binds
5. Prepare > Training: "Install the training server" (a few minutes, no extra space: its files are links to the game's).

DAILY USE
- "Coach CS2.bat" (or "Start with Windows.bat" once, to have it always running).
- Update (top bar): downloads and analyzes your new matches.
- Live during a match on your 2nd screen, Prepare before playing, Review after.

PRIVACY
- Your matches, your profile and your voice stay on this PC.
- Recording your teammates' voices needs their agreement, for each match (in France: article 226-1 of the Code penal).
  The app records the team's sound only after you confirm it in game (numpad /).
- The base's matches that come with the app are anonymized (no name, no real SteamID), except your own matches
  (as in your own demos) and the public pro matches.

UPDATES
Unzip the new version over this folder: your settings, matches and profile are kept.
"""


def extras(dst, sid, update):
    open(os.path.join(dst, "Coach CS2.bat"), "w", encoding="utf-8", newline="\r\n").write(LAUNCHER)
    open(os.path.join(dst, "Start with Windows.bat"), "w", encoding="utf-8", newline="\r\n").write(AUTOSTART)
    open(os.path.join(dst, "README.txt"), "w", encoding="utf-8", newline="\r\n").write(README)
    os.makedirs(os.path.join(dst, "cache"), exist_ok=True)
    if not update:   # a first install: this player's copy (an update leaves their settings alone)
        config.write_json(os.path.join(dst, "out", "settings.json"), {"role": "client", "own_steamid": sid}, indent=1)


def zip_dir(src, zpath):
    with zipfile.ZipFile(zpath + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, fs in os.walk(src):
            dirs.sort()
            rel = os.path.relpath(root, os.path.dirname(src))
            if not fs and not dirs:
                z.writestr(rel.replace(os.sep, "/") + "/", "")
            for f in sorted(fs):
                z.write(os.path.join(root, f), os.path.join(rel, f))
    os.replace(zpath + ".part", zpath)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--player" not in sys.argv:
        raise SystemExit(__doc__)
    sid, update = sys.argv[sys.argv.index("--player") + 1], "--update" in sys.argv
    if not os.path.exists(os.path.join(config.player_dir(sid), "advice.json")):
        raise SystemExit(f"no profile for {sid} here: analyze them first")
    dst = os.path.join(DIST, "CoachCS2")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "out", "site"))
    t0 = time.time()
    copy_code(dst)
    mine = copy_player(dst, sid, update)
    situations(dst, sid)
    copy_base(dst, Pseudo(), mine)
    extras(dst, sid, update)
    check(dst, mine, sid)
    if "--no-python" not in sys.argv:
        runtime(os.path.join(dst, "python"))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dst) for f in fs)
    log(f"folder: {dst} ({size / 2 ** 20:.0f} MB, {round(time.time() - t0)} s)")
    if "--no-zip" not in sys.argv:
        who = re.sub(r"[^\w-]", "", config.display_name(sid)) or sid
        z = os.path.join(DIST, f"CoachCS2-{time.strftime('%Y%m%d')}-{who}{'-update' if update else ''}.zip")
        zip_dir(dst, z)
        log(f"zip: {z} ({os.path.getsize(z) / 2 ** 20:.0f} MB)")


if __name__ == "__main__":
    main()
