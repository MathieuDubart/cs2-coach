"""Your team's plan with one key (06/10, the user: "un bind pour A, un bind pour mid, un bind pour B, un bind pour rush,
un bind pour slow, un bind pour contrôle map"): numpad 1, 2, 3 say the direction (A, mid, B), 4, 5, 6 the tempo (rush,
slow, map control) in the team chat, only what you pressed ("Rush A", 07/10: "si la touche veut dire A tu ne peux pas
écrire A from Ramp"), and tell Wily: Live then shows the way in that wins most, its odds and its grenades, with a ping. On CT the same keys only tell Wily (1-2-3 where you play, 4-5-6 what the
Ts do): nothing in the chat.

CS2 runs a config file each time a key bound to `exec` is pressed, and reads it from the disk again: the app rewrites
small files in CS2's cfg folder (coach_path1.cfg to coach_path3.cfg for the ways, kept from the time they said three
paths, coach_rush.cfg, coach_slow.cfg, coach_ctrl.cfg) whenever the page's plan changes, and the keys run them. Nothing is sent by the app itself: you press the key. One time only, in CS2's
console: `exec coach_binds` (the binds then stay in your CS2 settings).

The text written is cleaned (no quote, semicolon or line break, plain characters, 120 at most): a file can only ever
say one line in the team chat, plus, when the path ends on a site, CS2's own chat wheel order for it ("Go A" / "Go B",
the one bots follow: `playerchatwheel CW.GoA`), a fixed line. Never another command."""
import os
import re
import time

import gsi

KEYS = {1: "KP_1", 2: "KP_2", 3: "KP_3"}   # numpad 1, 2, 3: CS2's names (the physical key, num lock on or off); KP_END etc. were CS:GO's
WAYS = {1: "A", 2: "MID", 3: "B"}          # what numpad 1, 2, 3 say since 06/10 (they were paths 1, 2, 3 of the page)
TEMPO = {"rush": "KP_4", "slow": "KP_5", "ctrl": "KP_6"}   # numpad 4, 5, 6: rush, slow, map control
TEMPO_STATE = {"rush": "rush", "slow": "slow", "ctrl": "control"}
FOCUS_OFF = "KP_MINUS"   # numpad minus: drop the focus on a path
EXTRA = {"eco": "KP_DEL", "sit": "KP_0"}   # numpad ".": the economy plan; numpad 0: the situation, recent and global
SITE_KEYS = {"A": "KP_7", "B": "KP_9"}   # numpad 7 / 9: A / B (CT: the site you play; once planted, both sides: the bomb's site)
TEAM_KEY = "KP_SLASH"
LINEUP_KEY = "KP_PLUS"   # numpad +: the next lineup's photo, in a photo session on the training server (lineshots.py, 06/10)   # numpad /: your team agreed to be recorded (what you hear, for this match: 04/10)
OLD_KEYS = {"KP_MULTIPLY": "exec coach_team"}   # numpad *, the team key of 04/10 21:40: already used for something else
                                                # of yours; unbound by exec coach_binds while it still runs the coach's file
BINDS = "coach_binds.cfg"
_LAST = {}
WHEEL = {"A": 'playerchatwheel CW.GoA "#Chatwheel_aplan"', "B": 'playerchatwheel CW.GoB "#Chatwheel_bplan"'}   # the chat wheel's Go A / Go B


def clean(t):
    t = str(t or "").replace("·", "-").replace("→", ">").replace("’", "'").replace("⚡", "rush ")
    t = re.sub(r'["\\;\r\n\t/]', " ", t)
    t = "".join(ch for ch in t if 32 <= ord(ch) < 127)
    return re.sub(r"\s+", " ", t).strip()[:120]


def _keys_file():
    """Your CS2 key settings (where the binds stay)."""
    import config
    own = config.logged_in_account()[0]
    return os.path.join(config.steam_path(), "userdata", str(int(own) - 76561197960265728), "730", "local", "cfg", "cs2_user_keys_0_slot0.vcfg")


def _stale():
    """Keys the coach no longer uses that your CS2 settings still bind to its files."""
    try:
        t = open(_keys_file(), encoding="utf-8", errors="replace").read()
    except Exception:
        return []
    return [k for k, cmd in OLD_KEYS.items() if re.search(rf'"{k}"\s+"{re.escape(cmd)}"', t)]


def binds_text():
    lines = ["// Wily: numpad 1, 2, 3 = A, mid, B; 4, 5, 6 = rush, slow, map control (T: said in the team chat too)"]
    lines += [f'unbind "{k}"' for k in _stale()]
    lines += [f'bind "{k}" "exec coach_path{i}"' for i, k in KEYS.items()]
    lines += [f'bind "{k}" "exec coach_{name}"' for name, k in TEMPO.items()]
    lines += [f'bind "{FOCUS_OFF}" "exec coach_focus0"']
    lines += [f'bind "{k}" "exec coach_{name}"' for name, k in EXTRA.items()]
    lines += [f'bind "{k}" "exec coach_site{site}"' for site, k in SITE_KEYS.items()]
    lines += [f'bind "{TEAM_KEY}" "exec coach_team"']
    lines += [f'bind "{LINEUP_KEY}" "exec coach_lineup"']
    lines += ['echo "Wily: numpad 1-2-3 = A / mid / B, 4-5-6 = rush / slow / map control, minus drops them, / your team agreed to be recorded"']
    return "\n".join(lines) + "\n"


def write(paths, extra=None, tempo=None):
    """paths: [{"rank": 1, "text": "...", "site": "A"}, ...] from the page (rank 1, 2, 3: numpad 1, 2, 3: the ways A, mid,
    B since 06/10); a rank without a text only prints a note in the console.
    extra: {"eco": "...", "sit": "..."}, the economy plan and the situation, for numpad "." and 0 (one line each).
    tempo: {"rush": "...", "slow": "...", "ctrl": "..."}, the lines of numpad 4, 5, 6 (empty: Wily only)."""
    d = gsi.cfg_dir()
    if not d:
        return False
    bf = os.path.join(d, BINDS)
    if not os.path.exists(bf) or open(bf, encoding="utf-8").read() != binds_text():
        open(bf, "w", encoding="utf-8").write(binds_text())
    ff = os.path.join(d, "coach_focus0.cfg")
    if not os.path.exists(ff):
        open(ff, "w", encoding="utf-8").write('echo "Coach CS2: focus off"\n')
    _site_files(d)
    by, site = {}, {}
    for p in paths or []:
        try:
            r = int(p.get("rank"))
        except (TypeError, ValueError, AttributeError):
            continue
        t = clean(p.get("text"))
        if r in KEYS and t:
            by[r] = t
            if p.get("site") in WHEEL:
                site[r] = p["site"]
    for i in KEYS:
        body = (f'say_team "{by[i]}"\n' + (WHEEL[site[i]] + "\n" if i in site else "")) if i in by else f'echo "Wily: {WAYS[i]}"\n'
        if _LAST.get(i) != body:
            open(os.path.join(d, f"coach_path{i}.cfg"), "w", encoding="utf-8").write(body)
            _LAST[i] = body
    for name in EXTRA:
        t = clean((extra or {}).get(name)) if isinstance(extra, dict) else ""
        body = f'say_team "{t}"\n' if t else f'echo "Coach CS2: nothing to say for this key now"\n'
        if _LAST.get(name) != body:
            open(os.path.join(d, f"coach_{name}.cfg"), "w", encoding="utf-8").write(body)
            _LAST[name] = body
    for name in TEMPO:   # always a file: the key must reach Wily even with nothing to say (its line in the console)
        t = clean((tempo or {}).get(name)) if isinstance(tempo, dict) else ""
        body = f'say_team "{t}"\n' if t else f'echo "Wily: {TEMPO_STATE[name]}"\n'
        f = os.path.join(d, f"coach_{name}.cfg")
        if _LAST.get(name) != body or not os.path.exists(f):
            open(f, "w", encoding="utf-8").write(body)
            _LAST[name] = body
    return True


def _site_files(d):
    tf = os.path.join(d, "coach_team.cfg")   # numpad /: only a line in the console, the app reads it
    if not os.path.exists(tf):
        open(tf, "w", encoding="utf-8").write('echo "Coach CS2: team agreed"\n')
    lf = os.path.join(d, "coach_lineup.cfg")   # numpad +: rewritten during a photo session (lineshots.py)
    if not os.path.exists(lf):
        open(lf, "w", encoding="utf-8").write('echo "Wily: no lineup photo session (Prepare: Photos of the lineups)"\n')
    for site in SITE_KEYS:   # only a line in the console: the app reads it (CT: your site; planted: the bomb's site)
        sf = os.path.join(d, f"coach_site{site}.cfg")
        if not os.path.exists(sf):
            open(sf, "w", encoding="utf-8").write(f'echo "Coach CS2: {site}"\n')


def bound():
    """True when numpad 1 runs coach_path1 in your CS2 key settings (the binds were set once)."""
    try:
        f = _keys_file()
        return "exec coach_path1" in open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def bound_site():
    """True when numpad 7 runs coach_siteA in your CS2 key settings (exec coach_binds once more after this update)."""
    try:
        f = _keys_file()
        return "exec coach_siteA" in open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def bound_tempo():
    """True when numpad 4 runs coach_rush (exec coach_binds once more after the 06/10 update)."""
    try:
        return "exec coach_rush" in open(_keys_file(), encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def bound_focus():
    try:
        f = _keys_file()
        return "exec coach_focus0" in open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def console_file():
    d = gsi.cfg_dir()
    return os.path.join(os.path.dirname(d), "console.log") if d else None


KEY_RE = re.compile(r"execing coach_(?:path([123])|focus0|site([AB])|(team)|(rush|slow|ctrl)|(lineup))\b")


def watch():
    """Reads the new lines CS2 writes to its console log (from now on, never the past): a numpad key of the paths sets
    the focus on that path, numpad minus drops it. The file starts over with each CS2 session: read from its start."""
    pos, path = None, None
    while True:
        try:
            path = path or console_file()
            if not path or not os.path.exists(path):
                time.sleep(5)
                path = None
                continue
            size = os.path.getsize(path)
            if pos is None or size < pos:
                pos = size if pos is None else 0
            if size > pos:
                with open(path, "rb") as fh:
                    fh.seek(pos)
                    chunk = fh.read(size - pos)
                pos = size
                for line in chunk.decode("utf-8", "replace").splitlines():
                    m = KEY_RE.search(line)
                    if m and m.group(3):   # numpad /: your team agreed, what you hear is recorded too (this match)
                        try:
                            import voice
                            voice.TEAM.start("your team agreed: numpad / in game", gsi.state().get("map"))
                        except Exception as e:
                            print("team sound:", e, flush=True)
                    elif m and m.group(2):
                        gsi.set_site_key(m.group(2))
                    elif m and m.group(5):   # numpad +: a lineup's photo (a photo session on the training server)
                        try:
                            import lineshots
                            lineshots.on_key()
                        except Exception as e:
                            print("lineup photo:", e, flush=True)
                    elif m and m.group(4):   # numpad 4-5-6: the tempo
                        gsi.set_tdir(TEMPO_STATE[m.group(4)])
                    elif m and m.group(1):   # numpad 1-2-3: the way (A, mid, B); hostage maps keep their routes 1-2-3
                        if gsi.wily_answer(WAYS[int(m.group(1))]):   # Wily asked "from A or B?": the key answers
                            continue
                        gsi.set_focus(int(m.group(1)))
                        gsi.set_tdir(WAYS[int(m.group(1))])
                    elif m:   # numpad minus: no focus, no plan
                        gsi.set_focus(0)
                        gsi.drop_tdir()
        except Exception:
            pass
        time.sleep(0.3)


def status():
    d = gsi.cfg_dir()
    if d and (not os.path.exists(os.path.join(d, BINDS)) or open(os.path.join(d, BINDS), encoding="utf-8").read() != binds_text()):
        open(os.path.join(d, BINDS), "w", encoding="utf-8").write(binds_text())
    if d:
        _site_files(d)
    cf = console_file()
    fresh = bool(cf and os.path.exists(cf) and time.time() - os.path.getmtime(cf) < 2 * 86400)
    return {"cfg": bool(d), "binds_file": bool(d and os.path.exists(os.path.join(d, BINDS))), "bound": bound(), "focus_bound": bound_focus(),
            "site_bound": bound_site(), "tempo_bound": bound_tempo(),
            "console": fresh}
