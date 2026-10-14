"""Your FACEIT matches (10/10, the user: "ajoute les matchs faceit"), through FACEIT's official Data API with the
coach's server-side key (out/settings.json "faceit_api_key", never versioned, never in the players' packages).

From a SteamID: its FACEIT account, then its CS2 matches of the last month, each with its date, map, score, the ten
players (their SteamIDs) and their kills, assists, deaths, headshots and MVPs. They join the match list without a demo
(like Valve's matches past their month): your times, sessions, streaks and group count them.

The demos: FACEIT gives them only through its Downloads API (POST https://open.faceit.com/download/v2/demos/download,
body {"resource_url": <the match's demo_url>} -> payload.download_url, a signed URL), with an Access Token that has the
Downloads API scope: an application at https://fce.gg/downloads-api-application, about 30 days (docs.faceit.com,
Guides > Download API, read 10/10). The demo's address is kept with each match ("faceit_demo") for the day it is."""
import datetime as dt
import json
import time
import urllib.error
import urllib.request

from wily.core import config

API = "https://open.faceit.com/data/v4"
DAYS = 31
STEAM64 = 76561197960265728


class FaceitError(Exception):
    pass


def key():
    return (config.settings().get("faceit_api_key") or "").strip()


def _get(path, tries=3):
    k = key()
    if not k:
        raise FaceitError("no FACEIT API key")
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + k, "Accept": "application/json",
                                                      "User-Agent": "Wily (cs2 coach)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 401:
                raise FaceitError("the FACEIT API key is refused")
            if e.code == 429 and i < tries - 1:   # too many questions: wait and ask again
                time.sleep(5 * (i + 1))
                continue
            raise FaceitError(f"FACEIT answered {e.code}")
        except urllib.error.URLError as e:
            if i == tries - 1:
                raise FaceitError(f"FACEIT unreachable ({e.reason})")
            time.sleep(2)
    return None


def player(sid):
    """{"player_id", "nickname"} of the FACEIT account of a SteamID64, or None (no FACEIT account)."""
    j = _get(f"/players?game=cs2&game_player_id={int(sid)}")
    return {"player_id": j["player_id"], "nickname": j.get("nickname")} if j and j.get("player_id") else None


def history(pid, days=DAYS):
    """The CS2 match ids of the last `days` days, newest first."""
    since = int(time.time()) - days * 86400
    out, off = [], 0
    while off < 400:
        j = _get(f"/players/{pid}/history?game=cs2&from={since}&offset={off}&limit=100") or {}
        items = j.get("items") or []
        out += [i["match_id"] for i in items if i.get("match_id") and i.get("status", "FINISHED").upper() == "FINISHED"]
        if len(items) < 100:
            break
        off += 100
    return out


def _entry(mid, sid):
    """One match as an entry of the match list (no demo), or None when it is not complete."""
    m = _get(f"/matches/{mid}")
    if not m or str(m.get("status", "")).upper() != "FINISHED":
        return None
    teams = m.get("teams") or {}
    accs, order = [], []
    for f in ("faction1", "faction2"):
        for p in (teams.get(f) or {}).get("roster") or []:
            g = str(p.get("game_player_id") or "")
            if g.isdigit():
                accs.append(int(g) - STEAM64)
                order.append(g)
    sc = (m.get("results") or {}).get("score") or {}
    score = [sc.get("faction1"), sc.get("faction2")]
    st = _get(f"/matches/{mid}/stats") or {}
    rnd = (st.get("rounds") or [{}])[0]
    by = {}
    for t in rnd.get("teams") or []:
        for p in t.get("players") or []:
            s = p.get("player_stats") or {}
            by[str(p.get("player_id"))] = s
    pid_of = {}
    for f in ("faction1", "faction2"):
        for p in (teams.get(f) or {}).get("roster") or []:
            pid_of[str(p.get("game_player_id"))] = str(p.get("player_id"))

    def num(s, k):
        try:
            return int(float(s.get(k)))
        except (TypeError, ValueError):
            return None
    stats = [{"k": num(by.get(pid_of.get(g), {}), "Kills"), "a": num(by.get(pid_of.get(g), {}), "Assists"),
              "d": num(by.get(pid_of.get(g), {}), "Deaths"), "hs": num(by.get(pid_of.get(g), {}), "Headshots"),
              "mvp": num(by.get(pid_of.get(g), {}), "MVPs")} for g in order]
    rs = (rnd.get("round_stats") or {})
    # the rounds won (results.score is the maps won: 1 / 0): each team's "Final Score", matched to its faction by id
    fin = {str(t.get("team_id")): (t.get("team_stats") or {}).get("Final Score") for t in rnd.get("teams") or []}
    try:
        score = [int(fin[str((teams.get(f) or {}).get("faction_id"))]) for f in ("faction1", "faction2")]
    except (KeyError, TypeError, ValueError):
        score = None
    t = m.get("finished_at") or m.get("started_at")
    if not t or len(accs) < 2:
        return None
    me = None
    if str(sid) in order:
        i = order.index(str(sid))
        me = {"kills": stats[i]["k"], "assists": stats[i]["a"], "deaths": stats[i]["d"], "team_index": 0 if i < len(order) // 2 else 1}
    pick = ((((m.get("voting") or {}).get("map") or {}).get("pick")) or [None])[0] or rs.get("Map")
    return {"match_id": f"faceit_{mid}", "time": dt.datetime.fromtimestamp(int(t)).strftime("%Y-%m-%dT%H:%M"),
            "players": len(accs), "team_scores": score, "rounds": sum(score) if score else None,
            "duration_s": (int(m["finished_at"]) - int(m["started_at"])) if m.get("finished_at") and m.get("started_at") else None,
            "accounts": accs, "stats": stats, "map_name": pick, "from": "faceit", "faceit_id": mid,
            "faceit_demo": (m.get("demo_url") or [None])[0], **({"me_faceit": me} if me else {})}


def add_matches(sid, days=DAYS, log=print):
    """A SteamID's FACEIT matches of the last month into the match list. -> the new entries' ids."""
    from wily.app import pipeline
    p = player(sid)
    if not p:
        log("FACEIT: no FACEIT account for this Steam account")
        return []
    ids = history(p["player_id"], days)
    reg = pipeline.registry()
    new = []
    for mid in ids:
        k = f"faceit_{mid}"
        if k in reg:
            continue
        try:
            e = _entry(mid, sid)
        except FaceitError as ex:
            log(f"FACEIT: {ex}")
            break
        if e:
            reg[k] = e
            new.append(k)
    if new:
        pipeline.save_registry(reg)
    log(f"FACEIT ({p.get('nickname')}): {len(ids)} match(es) in the last {days} days, {len(new)} new")
    return new
