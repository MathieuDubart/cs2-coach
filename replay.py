"""Training on a local server: situations of your own demos played again. The bots follow exactly the recorded paths of
the nine other players (where they went, where they looked), they shoot back on their own when they see you, and you
take your own spot again (actor) or watch it all (spectator: a bot plays your spot too).

- scenarios(sid): the situations worth playing again: your deaths that lost the round or were not traded, the clutches
  you lost, from your last matches with a demo in cache.
- build(sid, mid, rnd, kind): one scenario from the demo (positions of the ten players every 2 ticks, their loadouts,
  who killed whom) written to the server's coach/scenarios folder.
- start(map) / stop() / status(): the server (a separate copy made by tools/make_server.py), hidden, 127.0.0.1 only; the
  plugin CoachReplay (plugin/CoachReplay) plays the scenario and appends each try to coach/results.jsonl.
Nothing here touches the game: the server is its own copy, and the game joins it like any community server."""
import json
import os
import secrets
import socket
import struct
import subprocess
import time

import pandas as pd

import config

SERVER = os.environ.get("COACH_CS2SERVER", r"E:\CS2Server")
EXE = os.path.join(SERVER, "game", "bin", "win64", "cs2.exe")
CSGO = os.path.join(SERVER, "game", "csgo")
COACH = os.path.join(CSGO, "coach")   # scenarios/, results.jsonl, live.json (the plugin's heartbeat)
SCEN = os.path.join(COACH, "scenarios")
PORT = 27015
STATE_F = os.path.join(config.OUT, "train.json")
STEP = 2   # one position every 2 ticks (32 a second); the plugin interpolates
BEFORE, AFTER, CLUTCH = 7, 6, 35   # seconds of a death situation before and after it; length of a clutch
NO_WINDOW = 0x08000000

ITEMS = {"AK-47": "ak47", "M4A4": "m4a1", "M4A1-S": "m4a1_silencer", "AWP": "awp", "SSG 08": "ssg08", "AUG": "aug",
         "SG 553": "sg556", "FAMAS": "famas", "Galil AR": "galilar", "G3SG1": "g3sg1", "SCAR-20": "scar20",
         "MAC-10": "mac10", "MP9": "mp9", "MP7": "mp7", "MP5-SD": "mp5sd", "UMP-45": "ump45", "P90": "p90",
         "PP-Bizon": "bizon", "Nova": "nova", "XM1014": "xm1014", "MAG-7": "mag7", "Sawed-Off": "sawedoff",
         "M249": "m249", "Negev": "negev", "Glock-18": "glock", "USP-S": "usp_silencer", "P2000": "hkp2000",
         "P250": "p250", "Five-SeveN": "fiveseven", "Tec-9": "tec9", "CZ75-Auto": "cz75a", "Desert Eagle": "deagle",
         "R8 Revolver": "revolver", "Dual Berettas": "elite", "Zeus x27": "taser", "High Explosive Grenade": "hegrenade",
         "Flashbang": "flashbang", "Smoke Grenade": "smokegrenade", "Molotov": "molotov",
         "Incendiary Grenade": "incgrenade", "Decoy Grenade": "decoy", "C4 Explosive": "c4"}


def _item(name):
    if not name:
        return None
    if name in ITEMS:
        return "weapon_" + ITEMS[name]
    low = str(name).lower()
    if "knife" in low or "bayonet" in low or "karambit" in low or "dagger" in low:
        return "weapon_knife"
    return None


# ---------------------------------------------------------------- the situations

def _own_matches(sid, n=15):
    md = os.path.join(config.player_dir(sid), "matches")
    out = []
    for mid in os.listdir(md) if os.path.isdir(md) else []:
        deep = os.path.join(config.OUT, "deep", mid)
        if os.path.exists(os.path.join(config.CACHE, f"{mid}.dem")) and os.path.exists(os.path.join(deep, "duels.parquet")):
            try:
                st = json.load(open(os.path.join(md, mid, "stats.json"), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append((mid, st.get("map")))
    return sorted(out, key=lambda x: int(x[0]), reverse=True)[:n]


def scenarios(sid, n=15):
    """The situations worth playing again, the worst first: the 1v1 and 1v2 you lost, your opening deaths not traded in a
    lost round, then the rest (1v3, deaths with one of the three)."""
    sid = str(sid)
    out = []
    for mid, mp in _own_matches(sid, n):
        deep = os.path.join(config.OUT, "deep", mid)
        D = pd.read_parquet(os.path.join(deep, "duels.parquet"))
        L = pd.read_parquet(os.path.join(deep, "loadout.parquet"), columns=["round", "steamid", "side", "won", "primary", "pistol"])
        L["steamid"] = L.steamid.astype(str)
        me = L[L.steamid == sid].set_index("round")
        D["killer"], D["victim"] = D.killer.astype(str), D.victim.astype(str)
        for _, d in D[D.victim == sid].iterrows():
            r = int(d["round"])
            won = bool(me.won.get(r)) if r in me.index else None
            score = (2 if won is False else 0) + (1 if not d.get("traded") else 0) + (1 if d.get("opening") else 0)
            out.append({"id": f"{mid}_r{r}_d", "mid": mid, "map": mp, "round": r, "kind": "death", "t": round(float(d.t), 1),
                        "side": d.victim_side, "zone": d.victim_zone, "by": d.killer_name, "weapon": d.weapon,
                        "mine": (me.primary.get(r) or me.pistol.get(r)) if r in me.index else None,
                        "opening": bool(d.get("opening")), "traded": bool(d.get("traded")), "won": won, "score": score})
        # clutches: the last teammate falls while you are alive, enemies left
        for r, R in D.groupby("round"):
            if r not in me.index:
                continue
            side = me.side.get(r)
            mates = set(L[(L["round"] == r) & (L.side == side) & (L.steamid != sid)].steamid)
            dead = R.sort_values("tick")
            gone = dead[dead.victim.isin(mates)]
            if len(mates) < 1 or len(gone.victim.unique()) < len(mates):
                continue
            last = gone.iloc[-1]
            mine = dead[dead.victim == sid]
            if len(mine) and mine.tick.iloc[0] < last.tick:
                continue
            foes = 5 - int(((dead.victim_side != side) & (dead.tick <= last.tick)).sum())
            if not 1 <= foes <= 3 or bool(me.won.get(r)):   # 1v4, 1v5: nothing much to learn
                continue
            out.append({"id": f"{mid}_r{int(r)}_c", "mid": mid, "map": mp, "round": int(r), "kind": "clutch",
                        "t": round(float(last.t), 1), "side": side, "zone": last.victim_zone, "vs": foes,
                        "mine": me.primary.get(r) or me.pistol.get(r), "won": False, "score": {1: 5, 2: 4}.get(foes, 3)})
    return sorted(out, key=lambda s: (-s["score"], -int(s["mid"]), s["round"]))


# ---------------------------------------------------------------- one scenario from the demo

def build(sid, mid, rnd, kind="death"):
    from demoparser2 import DemoParser
    sid, mid, rnd = str(sid), str(mid), int(rnd)
    deep = os.path.join(config.OUT, "deep", mid)
    R = pd.read_parquet(os.path.join(deep, "rounds.parquet")).set_index("round")
    D = pd.read_parquet(os.path.join(deep, "duels.parquet"))
    D["killer"], D["victim"] = D.killer.astype(str), D.victim.astype(str)
    mp = json.load(open(os.path.join(deep, "meta.json"), encoding="utf-8"))["map"]
    t0, t_end = int(R.start_tick[rnd]), int(R.end_tick[rnd])
    Dr = D[D["round"] == rnd].sort_values("tick")
    if kind == "clutch":
        sc = next(s for s in scenarios(sid) if s["mid"] == mid and s["round"] == rnd and s["kind"] == "clutch")
        key = int(Dr[Dr.t <= sc["t"] + 0.05].tick.iloc[-1])
        start, end = max(t0, key - 64), min(t_end, key + CLUTCH * 64)
    else:
        key = int(Dr[Dr.victim == sid].tick.iloc[0])
        start, end = max(t0, key - BEFORE * 64), min(t_end, key + AFTER * 64)
    p = DemoParser(os.path.join(config.CACHE, f"{mid}.dem"))
    ticks = list(range(start, end + 1, STEP))
    T = p.parse_ticks(["X", "Y", "Z", "yaw", "pitch", "is_alive", "team_num", "ducking"], ticks=ticks)
    T["steamid"] = T.steamid.astype(str)
    S = p.parse_ticks(["team_num", "inventory", "active_weapon_name", "health", "armor_value", "has_helmet", "is_alive"], ticks=[start])
    S["steamid"] = S.steamid.astype(str)
    players = []
    for _, s in S.iterrows():
        if s.team_num not in (2, 3) or not s.is_alive:
            continue
        g = T[T.steamid == s.steamid].sort_values("tick")
        alive = g.is_alive.to_numpy()
        death = next((i for i in range(len(alive)) if not alive[i]), -1)
        k = g if death < 0 else g.iloc[:death]
        path = []
        for x, y, z, yw, pt in zip(k.X, k.Y, k.Z, k.yaw, k.pitch):
            path += [round(float(x), 1), round(float(y), 1), round(float(z), 1), round(float(yw), 1), round(float(pt), 1)]
        duck = [int(i) for i, v in enumerate(k.ducking.fillna(False)) if v]
        died = Dr[(Dr.victim == s.steamid) & (Dr.tick >= start) & (Dr.tick <= end)]
        weapons = [w for w in (_item(i) for i in (s.inventory or [])) if w]
        players.append({"sid": s.steamid, "name": str(s["name"])[:31], "team": int(s.team_num), "me": s.steamid == sid,
                        "hp": int(s.health), "armor": int(s.armor_value), "helmet": bool(s.has_helmet),
                        "weapons": weapons, "active": _item(s.active_weapon_name), "path": path, "duck": duck,
                        "death": death, "killer": str(died.killer.iloc[0]) if len(died) else ""})
    me = next((q for q in players if q["me"]), None)
    if not me:
        raise ValueError("you are not alive at the start of this situation")
    teams = {q["sid"]: q["team"] for q in players}
    zone = (Dr[Dr.victim == sid].victim_zone.iloc[0] if kind == "death" and len(Dr[Dr.victim == sid]) else "")
    sc = {"id": f"{mid}_r{rnd}_{kind[0]}", "map": mp, "match": mid, "round": rnd, "kind": kind, "rate": 64, "step": STEP,
          "start_tick": start, "key": (key - start) // STEP, "team": me["team"], "zone": zone,
          "title": f"{mp.replace('de_', '').replace('cs_', '').title()} R{rnd} · {'clutch' if kind == 'clutch' else 'death'}"
                   f"{' · ' + zone if zone else ''}", "players": players, "nades": _nades(p, start, end, teams)}
    os.makedirs(SCEN, exist_ok=True)
    f = os.path.join(SCEN, f"{sc['id']}.json")
    json.dump(sc, open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return sc


NADES = {"CSmokeGrenadeProjectile": "smoke", "CFlashbangProjectile": "flash", "CHEGrenadeProjectile": "he",
         "CMolotovProjectile": "molotov", "CDecoyProjectile": "decoy"}


def _nades(p, start, end, teams):
    """The grenades thrown in the window: frame, type, thrower, first position and speed (the server flies them again
    from there; a thrower dead in the replay throws nothing)."""
    try:
        g = p.parse_grenades()
    except Exception:
        return []
    g = g[g.grenade_type.isin(list(NADES)) & g.x.notna() & (g.tick >= start) & (g.tick <= end)].sort_values("tick")
    out = []
    for (_, sid, typ), e in g.groupby(["grenade_entity_id", "steamid", "grenade_type"]):
        t = e.tick.to_numpy()
        cuts = [0] + [i for i in range(1, len(t)) if t[i] - t[i - 1] > 2] + [len(t)]   # an entity id is reused by later throws
        for a, b in zip(cuts, cuts[1:]):
            r = e.iloc[a:b]
            if len(r) < 2 or int(r.tick.iloc[0]) <= start:   # already flying when the situation starts
                continue
            dt = (int(r.tick.iloc[1]) - int(r.tick.iloc[0])) / 64
            v = [(float(r[c].iloc[1]) - float(r[c].iloc[0])) / dt for c in ("x", "y", "z")]
            v[2] += 0.5 * 320 * dt   # gravity over that first step (0.4 x 800)
            sid = str(sid)
            out.append({"f": (int(r.tick.iloc[0]) - start) // STEP, "type": NADES[typ], "by": sid,
                        "life": int(r.tick.iloc[-1]) - int(r.tick.iloc[0]),   # ticks until it pops (a smoke: until it fades)
                        "inc": NADES[typ] == "molotov" and teams.get(sid) == 3,
                        "p": [round(float(r[c].iloc[0]), 1) for c in ("x", "y", "z")], "v": [round(x, 1) for x in v]})
    return sorted(out, key=lambda n: n["f"])


# ---------------------------------------------------------------- the server

def _state():
    try:
        return json.load(open(STATE_F, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(s):
    json.dump(s, open(STATE_F, "w", encoding="utf-8"))


def _password():
    s = _state()
    if not s.get("rcon"):
        s["rcon"] = secrets.token_hex(8)   # our own server's password, not a user credential: local and random
        _save_state(s)
    return s["rcon"]


def rcon(cmd, timeout=3.0):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)

    def send(i, t, body):
        b = struct.pack("<ii", i, t) + body.encode("utf-8") + b"\x00\x00"
        s.sendall(struct.pack("<i", len(b)) + b)

    def exact(n):
        d = b""
        while len(d) < n:
            c = s.recv(n - len(d))
            if not c:
                raise ConnectionError("rcon closed")
            d += c
        return d

    def recv():
        n = struct.unpack("<i", exact(4))[0]
        d = exact(n)
        i, t = struct.unpack("<ii", d[:8])
        return i, t, d[8:-2].decode("utf-8", "replace")

    try:
        send(1, 3, _password())
        while True:
            i, t, _ = recv()
            if t == 2:
                if i == -1:
                    raise PermissionError("rcon password refused")
                break
        send(2, 2, cmd)
        out = []
        s.settimeout(0.6)
        try:
            while True:
                out.append(recv()[2])
        except (socket.timeout, ConnectionError):
            pass
        return "".join(out)
    finally:
        s.close()


def _pid_alive(pid):
    if not pid:
        return False
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=NO_WINDOW)
    return "cs2.exe" in r.stdout


def installed():
    return os.path.exists(EXE) and os.path.isdir(os.path.join(CSGO, "addons", "counterstrikesharp", "plugins", "CoachReplay"))


def heartbeat():
    """The plugin's heartbeat: who is on the server, what is playing (None when the server is down)."""
    try:
        h = json.load(open(os.path.join(COACH, "live.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return h if time.time() - (h.get("t") or 0) < 8 else None


def on_server():
    """You are on the training server right now (the coach's GSI treats it as practice)."""
    h = heartbeat()
    return bool(h and h.get("humans"))


def status():
    s = _state()
    up = _pid_alive(s.get("pid"))
    h = heartbeat() if up else None
    return {"installed": installed(), "running": up, "map": s.get("map") if up else None,
            "humans": (h or {}).get("humans", 0), "scenario": (h or {}).get("scenario"), "state": (h or {}).get("state"),
            "connect": f"connect 127.0.0.1:{PORT}"}


def _update():
    """After a CS2 update the server copy still links the old files (the game would refuse it): linked again first."""
    import sys
    sys.path.insert(0, os.path.join(config.HERE, "plugin"))
    import make_server
    if not make_server.current():
        make_server.main()


def start(mp):
    """The server on this map (started hidden, or its map changed); back when it answers."""
    if not installed():
        raise RuntimeError("training server not installed (tools/make_server.py, then the CoachReplay plugin)")
    s = _state()
    if _pid_alive(s.get("pid")):
        if s.get("map") != mp:
            rcon(f"changelevel {mp}")
            s["map"] = mp
            _save_state(s)
            time.sleep(8)
        return status()
    _update()
    args = [EXE, "-dedicated", "-usercon", "-ip", "127.0.0.1", "-port", str(PORT), "-condebug", "-nohltv",
            "+sv_lan", "1", "+rcon_password", _password(), "+game_type", "0", "+game_mode", "1", "+map", mp]
    si = subprocess.STARTUPINFO()   # its own console, hidden: without one the server logs a console error every frame
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0   # SW_HIDE: never shown, never takes the focus
    pr = subprocess.Popen(args, cwd=os.path.dirname(EXE), creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
    s.update(pid=pr.pid, map=mp, started=time.time())
    _save_state(s)
    # rcon only once the map runs (the plugin's heartbeat): an early try counts as a failed login and the server then
    # refuses 127.0.0.1
    for _ in range(120):
        time.sleep(1)
        h = heartbeat()
        if h and (h.get("t") or 0) > s["started"]:
            return status()
        if pr.poll() is not None:
            raise RuntimeError("the training server stopped while starting")
    raise RuntimeError("the training server did not start in 120 s")


def stop():
    s = _state()
    pid = s.get("pid")
    if _pid_alive(pid):
        try:
            rcon("quit")
        except OSError:
            pass
        for _ in range(10):
            time.sleep(0.5)
            if not _pid_alive(pid):
                break
        else:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=NO_WINDOW)
    s.pop("pid", None)
    _save_state(s)
    return status()


def idle_check(after=20 * 60):
    """Stops the server when nobody has been on it for 20 minutes (it holds about 1 GB of memory)."""
    s = _state()
    if not s.get("pid") or not _pid_alive(s.get("pid")):
        return
    h = heartbeat()
    now = time.time()
    if h and h.get("humans"):
        s["seen"] = now
        _save_state(s)
    elif now - max(s.get("seen") or 0, s.get("started") or 0) > after:
        stop()


def play(sid, mid, rnd, kind="death", mode="actor", diff=2):
    """Build the scenario, the server on its map, and tell the plugin: it starts as soon as you are in (or now)."""
    sc = build(sid, mid, rnd, kind)
    start(sc["map"])
    rcon(f"css_replay {sc['id']} {mode} {max(0, min(3, int(diff)))}")
    return {**status(), "scenario": {k: sc[k] for k in ("id", "title", "map", "round", "kind")}}


def results():
    """Every try, per scenario: tries, wins, last outcome."""
    out = {}
    try:
        lines = open(os.path.join(COACH, "results.jsonl"), encoding="utf-8").read().splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        e = out.setdefault(r.get("id"), {"tries": 0, "won": 0, "survived": 0, "last": None, "kills": 0, "watched": 0})
        if r.get("mode") == "spec":   # watched: a bot played your spot
            e["watched"] += 1
            continue
        e["tries"] += 1
        e["won"] += r.get("outcome") == "won"
        e["survived"] += r.get("outcome") == "survived"
        e["kills"] += r.get("kills") or 0
        e["last"] = r.get("outcome")
    return out
