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
PISTOL_NAMES = {"glock": "Glock-18", "usp_silencer": "USP-S", "hkp2000": "P2000", "p250": "P250", "deagle": "Desert Eagle", "tec9": "Tec-9",
                "fiveseven": "Five-SeveN", "cz75a": "CZ75-Auto", "elite": "Dual Berettas", "revolver": "R8 Revolver"}
LOCK = threading.Lock()
STATE = {}
HIST_F = os.path.join(LOG_DIR, "match.json")
HIST = {}   # the match being played: result and side of every round, and where the T attacked (marked by the player)


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
    "buffer"    "0.1"
    "throttle"  "0.25"
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
        "player_position"    "1"
        "phase_countdowns"   "1"
        "map_round_wins"     "1"
        "bomb"               "1"
        "allplayers_id"      "1"
        "allplayers_state"   "1"
        "allplayers_position" "1"
        "allplayers_weapons" "1"
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
        raise ValueError("CS2 folder not found: is CS2 installed with Steam on this PC?")
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


def _hist_save():
    import json
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        json.dump(dict(HIST, _t=time.time()), open(HIST_F, "w", encoding="utf-8"))
    except OSError:
        pass


def _hist_load():
    """After a restart of the app during a match, the rounds already played are still known."""
    import json
    try:
        h = json.load(open(HIST_F, encoding="utf-8"))
        if time.time() - h.get("_t", 0) < 2 * 3600:
            HIST.update(h)
    except (OSError, ValueError):
        pass


def _hist(mp, rd, side):
    """Round results (map.round_wins when the game sends it, round.win_team otherwise) and the side played each round."""
    name, rnum, phase = mp.get("name"), int(mp.get("round") or 0), rd.get("phase")
    changed = False
    if HIST.get("map") != name or mp.get("phase") == "warmup" or rnum + 1 < HIST.get("_max", 0):
        HIST.clear()
        HIST.update({"map": name, "start": time.time(), "rounds": {}, "sites": {}, "marks": {}, "_max": 0})
        changed = True
    R = HIST["rounds"]
    for k, v in (mp.get("round_wins") or {}).items():
        win = "T" if str(v).startswith("t_") else "CT" if str(v).startswith("ct_") else None
        if win and R.get(str(k), {}).get("win") != win:
            R.setdefault(str(k), {}).update(win=win, reason=v)
            changed = True
    cur = rnum if phase == "over" else rnum + 1
    if phase == "over" and rd.get("win_team") in ("T", "CT") and R.get(str(rnum), {}).get("win") != rd["win_team"]:
        R.setdefault(str(rnum), {}).update(win=rd["win_team"], bomb=rd.get("bomb"))
        changed = True
    if side and R.get(str(cur), {}).get("side") != side:
        R.setdefault(str(cur), {})["side"] = side
        changed = True
    HIST["_max"] = max(HIST.get("_max", 0), cur)
    if changed:
        _hist_save()


def set_site(rnd, site):
    """The player marks where the T attacked on a round (A, B, '-' for no clear attack, None to erase)."""
    with LOCK:
        if not HIST:
            return False
        if site in ("A", "B", "-"):
            HIST.setdefault("sites", {})[str(int(rnd))] = site
        else:
            HIST.setdefault("sites", {}).pop(str(int(rnd)), None)
        _hist_save()
        log_event({"map": HIST.get("map"), "round": int(rnd), "site_mark": site})
    return True


DYNS = ("rush", "fast", "exec", "late", "none")


def set_mark(rnd, fields):
    """What the player saw in a round: the first contact (zone, one T alone or several, when), when they saw the
    Ts on a site, the shape of the attack (rush, execute...) and whether the Ts lost a player alone.
    A field set to None is erased."""
    def num(v):
        return round(float(v), 1) if isinstance(v, (int, float)) and 0 <= v < 1000 else None
    clean = {}
    for k, v in fields.items():
        if k == "contact":
            clean[k] = str(v)[:40] if v else None
        elif k in ("alone", "lone"):
            clean[k] = bool(v) if v is not None else None
        elif k in ("contact_t", "site_t"):
            clean[k] = num(v)
        elif k == "dyn":
            clean[k] = v if v in DYNS else None
    if not clean:
        return True
    with LOCK:
        if not HIST:
            return False
        m = HIST.setdefault("marks", {}).setdefault(str(int(rnd)), {})
        for k, v in clean.items():
            if v is None:
                m.pop(k, None)
            else:
                m[k] = v
        _hist_save()
        log_event({"map": HIST.get("map"), "round": int(rnd), "mark": clean})
    return True


def _hist_times(cur, phase, bomb, prev_phase, prev_bomb, health, prev_health, kills, prev_kills, now, hp=None, prev_hp=None, pos=None):
    """Seconds since the end of the freeze time, per round: the plant, the end of the round, your death, your kills,
    the first damage you took, and where you stood until 20 s in. Read the Ts' tempo (a plant 35 s in is a fast hit)
    and what happens at your spot (a fight there or nothing yet) without any click."""
    if not HIST or not cur:
        return
    r = HIST.setdefault("rounds", {}).setdefault(str(cur), {})
    changed = False
    if phase == "live" and prev_phase != "live" and "live" not in r:
        r["live"], changed = round(now, 2), True
    t0 = r.get("live")
    if t0:
        el = round(now - t0, 1)
        if bomb == "planted" and prev_bomb != "planted" and "plant" not in r:
            r["plant"], changed = el, True
        if phase == "over" and prev_phase == "live" and "end" not in r:
            r["end"], changed = el, True
        if phase == "live" and health == 0 and (prev_health or 0) > 0 and "dead" not in r:
            r["dead"], changed = el, True
        if phase == "live" and kills and prev_kills is not None and kills > prev_kills:
            r.setdefault("kills", []).extend([el] * min(5, kills - prev_kills))
            changed = True
        if phase == "live" and hp is not None and prev_hp is not None and hp < prev_hp and "hurt" not in r:
            r["hurt"], changed = el, True
        if phase == "live" and pos and health and el <= 20 and r.get("pos15") != pos:   # the last spot before 20 s
            r["pos15"] = pos
            changed = changed or el >= 12
    if changed:
        _hist_save()


NADE_KEY = {"flashbang": "flash", "smokegrenade": "smoke", "hegrenade": "he", "molotov": "molotov", "incgrenade": "molotov", "decoy": "decoy"}


RAW = {"keys": {}, "samples": []}


def _sample(payload):
    """What the game really sends (it keeps a lot for spectators only): every key path seen, how often, and a few
    whole messages at different moments, without the auth token. Read with /api/gsi/raw."""
    def walk(o, path, depth=0):
        if isinstance(o, dict) and depth < 3:
            for k, v in o.items():
                if k == "auth":
                    continue
                p = f"{path}.{k}" if path else k
                RAW["keys"][p] = RAW["keys"].get(p, 0) + 1
                walk(v, p, depth + 1)
    walk(payload, "")
    ph = ((payload.get("round") or {}).get("phase"), (payload.get("map") or {}).get("phase"), bool(payload.get("allplayers")),
          bool((payload.get("player") or {}).get("position")), str((payload.get("player") or {}).get("steamid")) == str((payload.get("provider") or {}).get("steamid")))
    if sum(1 for x in RAW["samples"] if x[0] == ph) < 2 and len(RAW["samples"]) < 40:
        RAW["samples"].append((ph, {k: v for k, v in payload.items() if k != "auth"}))


def update(payload):
    """A message from the game. Keeps only what the in-game sheet needs."""
    if (payload.get("auth") or {}).get("token") != config.settings().get("gsi_token"):
        return False
    try:
        _sample(payload)
    except Exception:
        pass
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
            try:
                _hist(mp, rd, side if own else None)
            except Exception as e:
                print("round history:", e, flush=True)
        elif pl.get("activity") == "menu":
            STATE.update({"map": None, "map_phase": None, "practice": False, "_pmap": None})
        now = time.time()
        alive = bool(own and (st.get("health") or 0) > 0)   # when dead, the game shows the teammate you spectate
        try:
            if STATE.get("map") and HIST.get("map") == STATE.get("map"):
                try:   # your own position (world units) while alive
                    mypos = [round(float(v)) for v in str(pl.get("position") or "").split(",")] if own and alive and pl.get("position") else None
                    mypos = mypos if mypos and len(mypos) == 3 else None
                except ValueError:
                    mypos = None
                _hist_times(STATE.get("round"), rd.get("phase"), rd.get("bomb"), STATE.get("round_phase"), STATE.get("bomb"),
                            1 if alive else 0, 1 if STATE.get("_alive") else 0,
                            st.get("round_kills") if own else None, STATE.get("round_kills"), now,
                            hp=st.get("health") if own else None, prev_hp=STATE.get("health") if STATE.get("_alive") or alive else None, pos=mypos)
        except Exception as e:
            print("round times:", e, flush=True)
        STATE["_alive"] = alive
        if rd.get("phase") == "live" and STATE.get("round_phase") != "live":
            STATE["live_since"] = now      # end of the freeze time: the round clock starts
        if rd.get("bomb") == "planted" and STATE.get("bomb") != "planted":
            STATE["planted_at"] = now
        # the game's own clock: seconds left in the phase (round, bomb, freeze time). Rounds are not always 1:55
        # (bot matches, other modes): the length of this round is read when it starts
        pc = payload.get("phase_countdowns") or {}
        try:
            ends = float(pc.get("phase_ends_in")) if pc.get("phase_ends_in") is not None else None
        except (TypeError, ValueError):
            ends = None
        if ends is not None:
            STATE.update(pc_phase=pc.get("phase"), pc_ends_at=now + ends)
            if pc.get("phase") == "live" and rd.get("phase") == "live" and STATE.get("live_since") and now - STATE["live_since"] < 3:
                STATE["round_len"] = round(ends + (now - STATE["live_since"]))
        STATE.update({"steamid": me, "round_phase": rd.get("phase"), "bomb": rd.get("bomb"), "win_team": rd.get("win_team"),
                      "activity": pl.get("activity"), "_t": now})
        if own:
            prim = None
            for w in (pl.get("weapons") or {}).values():
                if w.get("type") in PRIMARY_TYPES:
                    n = str(w.get("name", "")).replace("weapon_", "")
                    prim = WEAPON_FR.get(n, n)
            pist = None   # your pistol: in an eco or a force-buy, the round's plan depends on it (Tec-9, Deagle...)
            for w in (pl.get("weapons") or {}).values():
                if w.get("type") == "Pistol":
                    n = str(w.get("name", "")).replace("weapon_", "")
                    pist = PISTOL_NAMES.get(n, n)
            held = {}
            for w in (pl.get("weapons") or {}).values():
                if w.get("type") == "Grenade":
                    k = NADE_KEY.get(str(w.get("name", "")).replace("weapon_", ""))
                    if k:
                        held[k] = held.get(k, 0) + max(1, int(w.get("ammo_reserve") or 1))
            STATE["nades"] = held if pl.get("weapons") else STATE.get("nades")
            try:   # your own position (world units), to put you on the radar: only while you are alive
                pos = [round(float(v)) for v in str(pl.get("position") or "").split(",")] if pl.get("position") else None
                STATE["pos"] = pos if pos and len(pos) == 3 and alive else None
            except ValueError:
                STATE["pos"] = None
            STATE.update({"side": side or STATE.get("side"), "money": st.get("money"), "equip": st.get("equip_value"),
                          "armor": st.get("armor"), "helmet": st.get("helmet"), "primary": prim if pl.get("weapons") else STATE.get("primary"), "pistol": pist if pl.get("weapons") else STATE.get("pistol"),
                          "health": st.get("health"), "round_kills": st.get("round_kills"),
                          "stats": pl.get("match_stats")})
        if not own:
            STATE["pos"] = None   # dead: the game shows the teammate you spectate
        key = (STATE.get("map"), STATE.get("round"), STATE.get("round_phase"), STATE.get("side"))
        if STATE.get("map") and key != STATE.get("_key"):
            STATE["_key"] = key
            log_event({"map": key[0], "round": key[1], "phase": key[2], "side": key[3], "steamid": me})
        # a practice or custom server: more than the $16,000 a real match allows, or a round longer than any real one
        # (1:55 + 40 s of bomb): the live advice and the automatic recording stay off there (analyses still wait)
        if STATE.get("map") != STATE.get("_pmap"):
            STATE.update(_pmap=STATE.get("map"), practice=False)
        el = now - STATE["live_since"] if STATE.get("round_phase") == "live" and STATE.get("live_since") else 0
        if STATE.get("map") and ((own and (st.get("money") or 0) > 16000) or el > 240):
            STATE["practice"] = True
        on = bool(STATE.get("map") and STATE.get("map_phase") != "gameover")
    _playing_flag(on, now)
    return True


_FLAG = {"t": 0.0, "on": False}


def _playing_flag(on, now):
    """out/playing.json: 'a match is going on' for every process of the app (analyses wait for its end).
    Refreshed every 20 s while you play; gone at the final scoreboard or back in the menus."""
    try:
        if on and now - _FLAG["t"] > 20:
            config.write_json(config.PLAYING, {"until": now + 75, "map": STATE.get("map")})
            _FLAG.update(t=now, on=True)
        elif not on and _FLAG["on"]:
            if os.path.exists(config.PLAYING):
                os.remove(config.PLAYING)
            _FLAG.update(t=0.0, on=False)
    except OSError as e:
        print("match flag:", e, flush=True)


def state():
    with LOCK:
        s = {k: v for k, v in STATE.items() if k not in ("_key", "_alive", "_pmap")}
        if HIST and HIST.get("map") == s.get("map"):
            s["hist"] = {"rounds": HIST.get("rounds", {}), "sites": HIST.get("sites", {}), "marks": HIST.get("marks", {})}
    if s:
        s["age"] = round(time.time() - s.pop("_t", 0), 1)
        if s.get("round_phase") == "live" and s.get("live_since"):
            s["elapsed"] = round(time.time() - s["live_since"], 1)   # seconds since the end of the freeze time
        if s.get("pc_ends_at"):
            s["phase_left"] = round(max(0.0, s.pop("pc_ends_at") - time.time()), 1)   # the game's clock
        if s.get("bomb") == "planted" and s.get("planted_at"):
            s["since_plant"] = round(time.time() - s["planted_at"], 1)
    return s


_hist_load()
