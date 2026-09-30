"""CS2 Game State Integration (Valve's official feature, also used by HUDs and RGB keyboards).

With a small config file in CS2's cfg folder, the game sends the live state of YOUR match to the local app
(map, phase, round, score, your side, money, health, match stats). While playing, CS2 only exposes the local
player's own information: no information about opponents. The in-game sheet uses it to follow the match by itself.
"""
import os
import re
import secrets
import threading
import time

import config

NAME = "gamestate_integration_coachcs2.cfg"
LOCK = threading.Lock()
STATE = {}


def cfg_dir():
    """CS2's cfg folder, found through Steam's library list."""
    sp = config.steam_path()
    libs = [sp]
    try:
        txt = open(os.path.join(sp, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="replace").read()
        libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s*"([^"]+)"', txt)]
    except OSError:
        pass
    for lib in dict.fromkeys(libs):
        d = os.path.join(lib, "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo", "cfg")
        if os.path.isdir(d):
            return d
    return None


def token():
    s = config.settings()
    if not s.get("gsi_token"):
        s["gsi_token"] = secrets.token_hex(12)
        config.save_settings(s)
    return s["gsi_token"]


def config_text(port):
    return f'''"Coach CS2"
{{
    "uri"       "http://127.0.0.1:{port}/api/gsi"
    "timeout"   "2.0"
    "buffer"    "0.5"
    "throttle"  "1.0"
    "heartbeat" "30.0"
    "auth"
    {{
        "token" "{token()}"
    }}
    "data"
    {{
        "provider"           "1"
        "map"                "1"
        "round"              "1"
        "player_id"          "1"
        "player_state"       "1"
        "player_match_stats" "1"
    }}
}}
'''


def status():
    d = cfg_dir()
    f = os.path.join(d, NAME) if d else None
    return {"cfg_dir": d, "installed": bool(f and os.path.exists(f)), "path": f,
            "receiving": bool(STATE) and time.time() - STATE.get("_t", 0) < 90}


def install(port):
    d = cfg_dir()
    if not d:
        raise ValueError("Dossier de CS2 introuvable : CS2 est-il installé avec Steam sur ce PC ?")
    open(os.path.join(d, NAME), "w", encoding="utf-8").write(config_text(port))
    return status()


def uninstall():
    d = cfg_dir()
    if d and os.path.exists(os.path.join(d, NAME)):
        os.remove(os.path.join(d, NAME))
    return status()


def update(payload):
    """A message from the game. Keeps only what the in-game sheet needs."""
    if (payload.get("auth") or {}).get("token") != config.settings().get("gsi_token"):
        return False
    prov = payload.get("provider") or {}
    mp = payload.get("map") or {}
    rd = payload.get("round") or {}
    pl = payload.get("player") or {}
    me = str(prov.get("steamid") or "")
    own = str(pl.get("steamid") or "") == me  # when dead, "player" is the teammate being spectated
    st = pl.get("state") or {}
    team = pl.get("team") if own else None
    side = {"CT": "CT", "T": "T"}.get(team)
    tkey = "team_ct" if side == "CT" else "team_t" if side == "T" else None
    with LOCK:
        if mp.get("name"):
            STATE.update({"map": mp.get("name"), "mode": mp.get("mode"), "map_phase": mp.get("phase"),
                          "round": (mp.get("round") or 0) + (0 if rd.get("phase") == "over" else 1),
                          "score_ct": (mp.get("team_ct") or {}).get("score"), "score_t": (mp.get("team_t") or {}).get("score"),
                          "losses": (mp.get(tkey) or {}).get("consecutive_round_losses") if tkey else STATE.get("losses")})
        elif pl.get("activity") == "menu":
            STATE.update({"map": None, "map_phase": None})
        STATE.update({"steamid": me, "round_phase": rd.get("phase"), "bomb": rd.get("bomb"), "win_team": rd.get("win_team"),
                      "activity": pl.get("activity"), "_t": time.time()})
        if own:
            STATE.update({"side": side or STATE.get("side"), "money": st.get("money"), "equip": st.get("equip_value"),
                          "health": st.get("health"), "round_kills": st.get("round_kills"),
                          "stats": pl.get("match_stats")})
    return True


def state():
    with LOCK:
        s = dict(STATE)
    if s:
        s["age"] = round(time.time() - s.pop("_t", 0), 1)
    return s
