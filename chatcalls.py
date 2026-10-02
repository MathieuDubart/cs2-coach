"""Your team's way in the team chat with one key: numpad 1, 2 or 3 says path 1, 2 or 3 of the In game page.

CS2 runs a config file each time a key bound to `exec` is pressed, and reads it from the disk again: the app rewrites
three small files in CS2's cfg folder (coach_path1.cfg, coach_path2.cfg, coach_path3.cfg) every round with the paths
the page shows, and the keys run them. Nothing is sent by the app itself: you press the key. One time only, in CS2's
console: `exec coach_binds` (the binds then stay in your CS2 settings).

The text written is cleaned (no quote, semicolon or line break, plain characters, 120 at most): a file can only ever
say one line in the team chat, plus, when the path ends on a site, CS2's own chat wheel order for it ("Go A" / "Go B",
the one bots follow: `playerchatwheel CW.GoA`), a fixed line. Never another command."""
import os
import re
import time

import gsi

KEYS = {1: "KP_1", 2: "KP_2", 3: "KP_3"}   # numpad 1, 2, 3: CS2's names (the physical key, num lock on or off); KP_END etc. were CS:GO's
FOCUS_OFF = "KP_MINUS"   # numpad minus: drop the focus on a path
BINDS = "coach_binds.cfg"
_LAST = {}
WHEEL = {"A": 'playerchatwheel CW.GoA "#Chatwheel_aplan"', "B": 'playerchatwheel CW.GoB "#Chatwheel_bplan"'}   # the chat wheel's Go A / Go B


def clean(t):
    t = str(t or "").replace("·", "-").replace("→", ">").replace("’", "'").replace("⚡", "rush ")
    t = re.sub(r'["\\;\r\n\t/]', " ", t)
    t = "".join(ch for ch in t if 32 <= ord(ch) < 127)
    return re.sub(r"\s+", " ", t).strip()[:120]


def binds_text():
    lines = ["// Coach CS2: numpad 1, 2 and 3 say path 1, 2 and 3 of the In game page in the team chat"]
    lines += [f'bind "{k}" "exec coach_path{i}"' for i, k in KEYS.items()]
    lines += [f'bind "{FOCUS_OFF}" "exec coach_focus0"']
    lines += ['echo "Coach CS2: numpad 1-2-3 say the paths in the team chat"']
    return "\n".join(lines) + "\n"


def write(paths):
    """paths: [{"rank": 1, "text": "..."}, ...] from the page; a rank without a path only prints a note in the console."""
    d = gsi.cfg_dir()
    if not d:
        return False
    bf = os.path.join(d, BINDS)
    if not os.path.exists(bf) or open(bf, encoding="utf-8").read() != binds_text():
        open(bf, "w", encoding="utf-8").write(binds_text())
    ff = os.path.join(d, "coach_focus0.cfg")
    if not os.path.exists(ff):
        open(ff, "w", encoding="utf-8").write('echo "Coach CS2: focus off"\n')
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
        body = (f'say_team "{by[i]}"\n' + (WHEEL[site[i]] + "\n" if i in site else "")) if i in by else 'echo "Coach CS2: no path for this key this round"\n'
        if _LAST.get(i) != body:
            open(os.path.join(d, f"coach_path{i}.cfg"), "w", encoding="utf-8").write(body)
            _LAST[i] = body
    return True


def bound():
    """True when numpad 1 runs coach_path1 in your CS2 key settings (the binds were set once)."""
    try:
        import config
        own = config.logged_in_account()[0]
        f = os.path.join(config.steam_path(), "userdata", str(int(own) - 76561197960265728), "730", "local", "cfg", "cs2_user_keys_0_slot0.vcfg")
        return "exec coach_path1" in open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def bound_focus():
    try:
        import config
        own = config.logged_in_account()[0]
        f = os.path.join(config.steam_path(), "userdata", str(int(own) - 76561197960265728), "730", "local", "cfg", "cs2_user_keys_0_slot0.vcfg")
        return "exec coach_focus0" in open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return False


def console_file():
    d = gsi.cfg_dir()
    return os.path.join(os.path.dirname(d), "console.log") if d else None


KEY_RE = re.compile(r"execing coach_(?:path([123])|focus0)\b")


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
                    if m:
                        gsi.set_focus(int(m.group(1)) if m.group(1) else 0)
        except Exception:
            pass
        time.sleep(0.3)


def status():
    d = gsi.cfg_dir()
    if d and not os.path.exists(os.path.join(d, BINDS)):
        open(os.path.join(d, BINDS), "w", encoding="utf-8").write(binds_text())
    cf = console_file()
    fresh = bool(cf and os.path.exists(cf) and time.time() - os.path.getmtime(cf) < 2 * 86400)
    return {"cfg": bool(d), "binds_file": bool(d and os.path.exists(os.path.join(d, BINDS))), "bound": bound(), "focus_bound": bound_focus(),
            "console": fresh}
