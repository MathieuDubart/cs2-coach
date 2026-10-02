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

import gsi

KEYS = {1: "KP_1", 2: "KP_2", 3: "KP_3"}   # numpad 1, 2, 3: CS2's names (the physical key, num lock on or off); KP_END etc. were CS:GO's
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


def status():
    d = gsi.cfg_dir()
    if d and not os.path.exists(os.path.join(d, BINDS)):
        open(os.path.join(d, BINDS), "w", encoding="utf-8").write(binds_text())
    return {"cfg": bool(d), "binds_file": bool(d and os.path.exists(os.path.join(d, BINDS))), "bound": bound()}
