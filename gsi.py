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
LOG_DIR = os.path.join(config.OUT, "gsi")
WEAPON_FR = {"ak47": "AK-47", "m4a1": "M4A4", "m4a1_silencer": "M4A1-S", "awp": "AWP", "aug": "AUG", "sg556": "SG 553",
             "famas": "FAMAS", "galilar": "Galil AR", "ssg08": "SSG 08", "g3sg1": "G3SG1", "scar20": "SCAR-20", "mac10": "MAC-10",
             "mp9": "MP9", "mp7": "MP7", "mp5sd": "MP5-SD", "ump45": "UMP-45", "p90": "P90", "bizon": "PP-Bizon", "nova": "Nova",
             "xm1014": "XM1014", "mag7": "MAG-7", "sawedoff": "Sawed-Off", "negev": "Negev", "m249": "M249"}
PRIMARY_TYPES = {"Rifle", "SniperRifle", "Submachine Gun", "Shotgun", "Machine Gun"}
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
        "player_weapons"     "1"
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


def refresh(port):
    """An installed config from an older version or another port is rewritten (CS2 reads it at its next start)."""
    d = cfg_dir()
    f = os.path.join(d, NAME) if d else None
    if f and os.path.exists(f) and open(f, encoding="utf-8").read() != config_text(port):
        open(f, "w", encoding="utf-8").write(config_text(port))
        return True
    return False


def log_event(ev):
    """Timeline of the match (map, round, phase, side) with the time: lets any recording be aligned on the rounds later."""
    import json
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, time.strftime("%Y%m%d") + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(ev, t=round(time.time(), 2)), ensure_ascii=False) + "\n")


def timeline(start, end):
    """Round events logged between two times (seconds since epoch)."""
    import json
    out = []
    if not os.path.exists(LOG_DIR):
        return out
    for fn in sorted(os.listdir(LOG_DIR)):
        for line in open(os.path.join(LOG_DIR, fn), encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if start <= e.get("t", 0) <= end:
                out.append(e)
    return out


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
            prim = None
            for w in (pl.get("weapons") or {}).values():
                if w.get("type") in PRIMARY_TYPES:
                    n = str(w.get("name", "")).replace("weapon_", "")
                    prim = WEAPON_FR.get(n, n)
            STATE.update({"side": side or STATE.get("side"), "money": st.get("money"), "equip": st.get("equip_value"),
                          "armor": st.get("armor"), "helmet": st.get("helmet"), "primary": prim if pl.get("weapons") else STATE.get("primary"),
                          "health": st.get("health"), "round_kills": st.get("round_kills"),
                          "stats": pl.get("match_stats")})
        key = (STATE.get("map"), STATE.get("round"), STATE.get("round_phase"), STATE.get("side"))
        if STATE.get("map") and key != STATE.get("_key"):
            STATE["_key"] = key
            log_event({"map": key[0], "round": key[1], "phase": key[2], "side": key[3], "steamid": me})
    return True


def state():
    with LOCK:
        s = {k: v for k, v in STATE.items() if k != "_key"}
    if s:
        s["age"] = round(time.time() - s.pop("_t", 0), 1)
    return s
