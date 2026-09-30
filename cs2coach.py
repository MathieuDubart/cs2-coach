"""CS2 coach: fetch matches, analyze them for one or more players, build the app.

Examples
  python cs2coach.py                         # your own account (detected from Steam), last matches
  python cs2coach.py --steamid 7656119...    # any player: uses every cached demo they appear in
  python cs2coach.py --steamid 7656119... --sharecode CSGO-xxxxx-...   # add specific matches
  python cs2coach.py --steamid 7656119... --authcode XXXX-XXXXX-XXXX --knowncode CSGO-...  # full history
                                             # (needs "steam_api_key" in out/settings.json)
  python cs2coach.py --build-only            # just rebuild out/app.html
Steam must be running (and CS2 closed) to fetch match info from Valve.
"""
import argparse
import json
import os
import sys
import traceback

import config
import matchlist
from coach import decompress, download, game_mode

REGISTRY = os.path.join(config.CACHE, "matches.json")


LOG_HOOK = None  # set by the local server to stream progress to the page


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    if LOG_HOOK:
        LOG_HOOK(msg)


def registry():
    return json.load(open(REGISTRY)) if os.path.exists(REGISTRY) else {}


def save_registry(r):
    json.dump(r, open(REGISTRY, "w"), indent=1)


def collect(args, own_id):
    reg = registry()
    new = []
    if not args.no_fetch and (args.steamid in (None, own_id) or args.own):
        try:
            for m in matchlist.fetch():
                new.append(m)
        except Exception as e:
            log("Valve match list unavailable (Steam closed or CS2 open?):", e)
    codes = list(args.sharecode or [])
    if args.steamid and args.steamid != own_id and not args.no_fetch:
        codes += leetify_codes(args.steamid)
    s = config.settings()
    if args.authcode and args.knowncode:
        key = s.get("steam_api_key")
        if not key:
            log("steam_api_key is missing from out/settings.json to browse the history.")
        else:
            codes += [args.knowncode] + matchlist.history_codes(key, args.steamid, args.authcode, args.knowncode)
            s.setdefault("players", {}).setdefault(str(args.steamid), {}).update(
                {"authcode": args.authcode, "last_code": codes[-1]})
            config.save_settings(s)
    for c in codes:
        try:
            mid, oc, tok = matchlist.decode_sharecode(c)
            if str(mid) in reg and reg[str(mid)].get("url"):
                continue
            new += matchlist.fetch_one(mid, oc, tok)
        except Exception as e:
            log(f"Code {c}: failed ({e})")
    for m in new:
        if m.get("url"):
            reg.setdefault(m["match_id"], {}).update(m)
    save_registry(reg)
    return reg


def leetify_codes(steamid, days=35, limit=15):
    """Share codes of the player's recent matchmaking games, from Leetify (demos older than ~1 month are gone)."""
    import datetime as dt
    import leetify
    ms = leetify.matches(steamid)
    json.dump(ms, open(os.path.join(config.CACHE, f"leetify_{steamid}.json"), "w", encoding="utf-8"))
    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    recent = sorted((m for m in ms if str(m.get("data_source_match_id", "")).startswith("CSGO-")
                     and dt.datetime.fromisoformat(m["finished_at"][:19]) >= since), key=lambda m: m["finished_at"], reverse=True)
    codes = [m["data_source_match_id"] for m in recent[:limit]]
    fc = sum(1 for m in ms if m.get("data_source") == "faceit")
    log(f"Leetify: {len(ms)} recent matches, {len(codes)} matchmaking ones from the last {days} days, {fc} FACEIT")
    return codes


def _fetch_demo(mid, url):
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    arc = dem + ".bz2"
    if os.path.exists(arc) and not os.path.exists(arc + ".part"):  # left by an earlier, cut download: resume it
        os.replace(arc, arc + ".part")
    download(url, arc)
    try:
        decompress(arc, dem)
    except Exception:
        os.remove(arc)  # complete but damaged: download it again next time
        raise
    os.remove(arc)


DEMO_DAYS = 28  # Valve keeps matchmaking demos about a month


def _recent(m, days=DEMO_DAYS):
    import datetime as dt
    try:
        return dt.datetime.now() - dt.datetime.fromisoformat(str(m.get("time"))[:16]) < dt.timedelta(days=days)
    except ValueError:
        return False


def pending_demos(reg):
    """Your own matches known to Valve whose demo is not here yet: it goes online a few minutes after the match,
    so a download tried too early is tried again at the next analysis."""
    return {mid for mid, m in reg.items() if m.get("url") and m.get("me") and (not m.get("expired") or _recent(m))
            and not os.path.exists(os.path.join(config.CACHE, f"{mid}.dem"))}


def ensure_demos(reg, workers=2, only=None):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    os.makedirs(config.CACHE, exist_ok=True)
    todo = {mid: m["url"] for mid, m in reg.items()
            if (only is None or mid in only) and m.get("url") and (not m.get("expired") or _recent(m))
            and not os.path.exists(os.path.join(config.CACHE, f"{mid}.dem"))}
    if todo:
        log(f"Downloading {len(todo)} demo(s) from Valve…")
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(_fetch_demo, mid, url): mid for mid, url in todo.items()}
        for i, f in enumerate(as_completed(futs), 1):
            mid = futs[f]
            try:
                f.result()
                reg[mid].pop("expired", None)
                log(f"  demo {i}/{len(todo)} ready")
            except Exception as e:
                if _recent(reg[mid]):  # not online yet (a few minutes after the match), or a network hiccup
                    reg[mid].pop("expired", None)
                    log(f"  [{mid}] demo not available from Valve yet ({e}): it arrives a few minutes after the match ends. Trying again at the next analysis.")
                else:
                    reg[mid]["expired"] = True
                    log(f"  [{mid}] demo unavailable ({e}): Valve only keeps it for about a month")
    save_registry(reg)


def ensure_deep():
    import deep
    import rounds
    import midround
    _ensure_deep(deep)
    rounds.run_all(config.CACHE, config.DEEP, log=log)
    midround.run_all(log=log)
    import buys
    buys.run_all(log=log)
    import tside
    tside.run_all(log=log)


def _ensure_deep(deep):
    for f in os.listdir(config.CACHE):
        if not f.endswith(".dem"):
            continue
        mid = f[:-4]
        out = os.path.join(config.DEEP, mid)
        if os.path.exists(os.path.join(out, "meta.json")):
            continue
        log(f"[{mid}] detailed extraction")
        try:
            deep.extract(os.path.join(config.CACHE, f), out)
        except Exception as e:
            log(f"[{mid}] extraction ERROR: {e}")
            traceback.print_exc()


def player_matches(steamid):
    """Match ids of cached demos where this player appears."""
    import pandas as pd
    ids = []
    for mid in os.listdir(config.DEEP):
        p = os.path.join(config.DEEP, mid, "samples.parquet")
        if os.path.exists(p) and steamid in set(pd.read_parquet(p, columns=["steamid"]).steamid):
            ids.append(mid)
    return ids


def _analyze_match(steamid, mid, m):
    """One match for one player (runs in a worker process)."""
    import analyze
    import map_analysis
    folder = os.path.join(config.player_dir(steamid), "matches", mid)
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    try:
        st = analyze.analyze(dem, steamid)
        if st.get("error"):
            return f"[{mid}] player not found"
        os.makedirs(folder, exist_ok=True)
        st["match"] = {"match_id": mid, "time": m.get("time"), "team_scores": m.get("team_scores"), "duration_s": m.get("duration_s")}
        st["mode"] = game_mode(dem, m.get("players", 10))
        mp = map_analysis.analyze(dem, steamid)
        enc = lambda o: o.item() if hasattr(o, "item") else str(o)
        json.dump(mp, open(os.path.join(folder, "map.json"), "w", encoding="utf-8"), ensure_ascii=False, default=enc)
        json.dump(st, open(os.path.join(folder, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, default=enc)
        return f"[{mid}] {st['map']} {st['final_score']['me']}-{st['final_score']['them']}"
    except Exception as e:
        return f"[{mid}] ERROR: {e}"


def analyze_player(steamid, reg):
    import analyze
    import map_analysis
    import cross
    import advice
    pdir = config.player_dir(steamid)
    ids = player_matches(steamid)
    log(f"Player {steamid}: {len(ids)} match(es) in cache")
    name = None
    todo = [mid for mid in ids if not os.path.exists(os.path.join(pdir, "matches", mid, "stats.json"))
            and os.path.exists(os.path.join(config.CACHE, f"{mid}.dem"))]
    if todo:
        import multiprocessing
        log(f"Analyzing {len(todo)} match(es)…")
        if multiprocessing.current_process().name == "MainProcess" and len(todo) > 1:
            from concurrent.futures import ProcessPoolExecutor, as_completed
            with ProcessPoolExecutor(min(8, len(todo))) as ex:
                futs = [ex.submit(_analyze_match, steamid, mid, reg.get(mid, {})) for mid in todo]
                for f in as_completed(futs):
                    log("  " + f.result())
        else:  # already inside a worker (batch profiling): stay sequential
            for mid in todo:
                log("  " + _analyze_match(steamid, mid, reg.get(mid, {})))
    import leetify
    prof = leetify.profile(steamid)
    if not ids:
        if not prof:
            log("No demo and no public Leetify profile: nothing to analyze.")
            return None
        os.makedirs(pdir, exist_ok=True)
        lm = leetify.matches(steamid)
        adv = leetify.light_advice(prof, lm, steamid)
        adv["light"] = True
        json.dump(adv, open(os.path.join(pdir, "advice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"No demo available: light profile built from Leetify ({prof.get('total_matches')} matches)")
        return pdir
    res = cross.run(steamid, set(ids))
    enc = lambda o: o.item() if hasattr(o, "item") else str(o)
    json.dump(res, open(os.path.join(pdir, "cross.json"), "w", encoding="utf-8"), ensure_ascii=False, default=enc)
    adv = advice.build(pdir)
    if prof:
        adv["leetify"] = leetify.light_advice(prof, leetify.matches(steamid), steamid)["leetify"]
    json.dump(adv, open(os.path.join(pdir, "advice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return pdir


def attach_plan(sid):
    """Coaching plan (routine, mid-round, weapons, context, experiments) from the saved analysis of a player."""
    import plan
    pdir = config.player_dir(sid)
    p = os.path.join(pdir, "advice.json")
    if not os.path.exists(p):
        return
    adv = json.load(open(p, encoding="utf-8"))
    load = lambda n: json.load(open(os.path.join(pdir, n), encoding="utf-8")) if os.path.exists(os.path.join(pdir, n)) else None
    try:
        adv["plan"] = plan.build(sid, adv, load("cross.json"), load("deepdive.json"), light=bool(adv.get("light")))
    except Exception as e:
        log(f"Progress plan unavailable: {e}")
        traceback.print_exc()
        return
    json.dump(adv, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    try:  # coach notes per map and side (zones to change or keep, grenades), from the cross-match analysis
        import coach_notes
        coach_notes.write(sid, load("cross.json"), adv.get("plan"))
    except Exception as e:
        log(f"Map notes unavailable: {e}")


PARTIAL_HOOK = None  # called with the SteamID once a first profile can be displayed


def quick_profile(sid):
    """Show something within seconds: Leetify stats while demos download (only if no full profile exists yet)."""
    import leetify
    pdir = config.player_dir(sid)
    adv_p = os.path.join(pdir, "advice.json")
    if os.path.exists(adv_p) and not json.load(open(adv_p, encoding="utf-8")).get("light"):
        if PARTIAL_HOOK:
            PARTIAL_HOOK(sid)
        return
    prof = leetify.profile(sid)
    if not prof:
        log("No public Leetify profile: the analysis relies on demos only.")
        return
    os.makedirs(pdir, exist_ok=True)
    adv = leetify.light_advice(prof, leetify.matches(sid), sid)
    adv["light"] = True
    json.dump(adv, open(adv_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"Leetify profile shown ({prof.get('total_matches')} matches tracked): analyzing demos…")
    if PARTIAL_HOOK:
        PARTIAL_HOOK(sid)


SHARECODE_RE = r"CSGO(?:-[A-Za-z0-9]{5}){5}"


def extras(sid):
    """Public info available for anyone: Steam profile + csstats.gg header (Premier / Competitive ranks)."""
    import csstats
    out = {}
    try:
        out["steam"] = csstats.steam_profile(sid)
    except Exception:
        pass
    try:
        cs = csstats.fetch(sid)
        if cs:
            out["csstats"] = cs
    except Exception:
        pass
    return out


def attach_extras(sid, ex=None):
    p = os.path.join(config.player_dir(sid), "advice.json")
    if not os.path.exists(p):
        return
    adv = json.load(open(p, encoding="utf-8"))
    adv.update(ex if ex is not None else extras(sid))
    json.dump(adv, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def minimal_profile(sid, ex):
    """No demo, no Leetify: what public sources still tell (ranks per map, Premier history)."""
    cs = ex.get("csstats") or {}
    rules = []
    maps = sorted((m for m in cs.get("maps", []) if m["rank"] > 0), key=lambda m: -m["rank"])  # rank 0 = unranked
    if len(maps) >= 2 and maps[0]["rank"] - maps[-1]["rank"] >= 2:
        b, w = maps[0], maps[-1]
        rules.append({"id": "maps", "score": 20, "short": f"Play {b['map'].split('_')[-1].capitalize()} first",
                      "title": f"Your best Competitive map: {b['map'].split('_')[-1].capitalize()} ({b['rank_name']}), your weakest: {w['map'].split('_')[-1].capitalize()} ({w['rank_name']})",
                      "why": [f"Competitive ranks per map (csstats.gg): " + ", ".join(f"{m['map'].split('_')[-1].capitalize()} {m['rank_name']}" for m in maps[:6]) + "."],
                      "do": ["Pick your best map when you want to win, work on the weakest in Deathmatch and practice mode."]})
    prem = [x for x in cs.get("premier", []) if x.get("current")]
    if len(prem) >= 2:
        cur, prev = prem[0], prem[1]
        delta = cur["current"] - prev["current"]
        rules.append({"id": "premier", "score": 15, "short": "Premier: " + ("improving" if delta > 0 else "dropping"),
                      "title": f"Premier {cur['season']}: {cur['current']:,} (best {cur['best']:,}), vs {prev['current']:,} in {prev['season']}".replace(",", " "),
                      "why": [f"{cur['wins']} wins this season."], "do": []})
    rules.append({"id": "unlock", "score": 1, "short": "Unlock the full analysis",
                  "title": "No demo and no Leetify profile: analysis limited to public rankings",
                  "why": ["Valve doesn't give a player's history from their SteamID alone."],
                  "do": ["Paste a match share code (CS2 → Watch → Your Matches → share, CSGO-… format) in the search bar, with or without the profile link.",
                         "Or create a free account on leetify.com with this Steam account: its next matches will become analyzable automatically."]})
    adv = {"rules": rules, "strengths": [], "maps": {}, "match_notes": {}, "light": True, "minimal": True, **ex}
    os.makedirs(config.player_dir(sid), exist_ok=True)
    json.dump(adv, open(os.path.join(config.player_dir(sid), "advice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run_for(query, fetch=True):
    """Full pipeline for a search: a SteamID64 / profile URL / vanity name, and/or match share codes.
    Returns a SteamID64, or {"match_players": [...]} when only share codes were given."""
    import re as _re
    from types import SimpleNamespace
    import leetify
    own_id, own_name = config.logged_in_account()
    codes = _re.findall(SHARECODE_RE, str(query))
    rest = _re.sub(SHARECODE_RE, " ", str(query)).replace(",", " ").strip()
    sid = name = None
    if rest:
        sid, name = leetify.resolve_steamid(rest.split()[0])
        if not sid:
            raise ValueError(f"Steam profile not found: {rest}")
    if not sid and not codes:
        raise ValueError("Paste a Steam profile link, a SteamID64, a custom URL name or a CSGO-… share code")
    s = config.settings()
    s.setdefault("own_steamid", own_id)
    if sid:
        log(f"Profile: {name or '?'} ({sid})")
        p = s.setdefault("players", {}).setdefault(str(sid), {})
        if name:
            p["name"] = name
        van = _re.search(r"/id/([^/?#]+)", rest)
        if van:
            p["vanity"] = van.group(1)
    config.save_settings(s)
    ex = {}
    if sid:
        quick_profile(sid)
        ex = extras(sid)
        attach_extras(sid, ex)
    if codes:
        log(f"{len(codes)} share code(s): fetching the matches from Valve…")
    args = SimpleNamespace(steamid=sid, sharecode=codes, authcode=None, knowncode=None, no_fetch=not fetch, own=False)
    before = set(registry())
    reg = collect(args, own_id)
    new = set(reg) - before
    code_ids = {str(matchlist.decode_sharecode(c)[0]) for c in codes}
    own = bool(sid) and int(sid) == int(own_id or 0)
    ensure_demos(reg, only=new | code_ids | (pending_demos(reg) if own else set()))  # only this search (+ your demos still missing)
    ensure_deep()
    import population
    import style
    population.run_all()
    style.run_all(workers=4)
    if sid:
        if not analyze_player(sid, reg):
            if not ex.get("steam") and not ex.get("csstats"):
                raise ValueError("Nothing public about this player: no demo, no Leetify, no csstats.gg. Try with a share code from one of their matches.")
            minimal_profile(sid, ex)
            log("No demo and no Leetify profile: minimal profile (public csstats.gg rankings and Steam profile).")
        else:
            attach_extras(sid, ex)
        attach_plan(sid)
        log("Analysis done")
        return sid
    # share codes only: profile every player of those matches
    import pandas as pd
    players = {}
    for mid in code_ids:
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if os.path.exists(f):
            for p_id, nm in pd.read_parquet(f, columns=["steamid", "name"]).drop_duplicates("steamid").itertuples(index=False):
                if p_id:
                    players[int(p_id)] = nm
    if not players:
        raise ValueError("No match fetched with this code: the demo may have expired at Valve (about 1 month).")
    log(f"{len(players)} players in this/these match(es): building their profiles…")
    s = config.settings()
    for p_id, nm in players.items():
        s.setdefault("players", {}).setdefault(str(p_id), {})["name"] = nm
    config.save_settings(s)
    for i, (p_id, nm) in enumerate(players.items(), 1):
        if analyze_player(p_id, reg):
            attach_plan(p_id)
        log(f"  profile {i}/{len(players)}: {nm}")
    log("Analysis done")
    return {"match_players": [{"steamid": str(k), "name": v} for k, v in players.items()]}


def sync_steam(sid=None):
    """Your account: new matches from your Steam history (API key + authentication code) and Valve's last 8,
    then the full analysis. Nothing is recomputed when there is nothing new. Returns the SteamID64."""
    from types import SimpleNamespace
    import steamlink
    own_id, _ = config.logged_in_account()
    s = config.settings()
    sid = int(sid or s.get("own_steamid") or own_id)
    try:
        codes = steamlink.new_codes(sid, log=log)
    except steamlink.SteamError as e:
        log(f"Steam history unavailable: {e}")
        codes = []
    key = s.get("steam_api_key")
    if key:
        try:
            steamlink.friends(key, sid, refresh=True)
            pt = steamlink.owned_cs2(key, sid)
            if pt:
                s = config.settings()
                s.setdefault("players", {}).setdefault(str(sid), {})["playtime"] = pt
                config.save_settings(s)
        except steamlink.SteamError as e:
            log(f"Steam: {e}")
    before = registry()
    args = SimpleNamespace(steamid=sid, sharecode=codes, authcode=None, knowncode=None, no_fetch=False, own=(sid == own_id))
    reg = collect(args, own_id)
    got = [c for c in codes if str(matchlist.decode_sharecode(c)[0]) in reg]
    if got:
        steamlink.done_codes(sid, got)
    new = {mid for mid in reg if mid not in before or (reg[mid].get("accounts") and not before[mid].get("accounts"))}
    if len(got) < len(codes):
        log(f"{len(codes) - len(got)} match(es) not fetched yet: Steam must be open and CS2 closed. Trying again at the next sync.")
    fresh = [mid for mid in new if mid not in before]
    pend = pending_demos(reg) if sid == own_id else set()
    log(f"{len(fresh)} new match(es)" + (f", {len(pend)} demo(s) still to fetch" if pend - set(fresh) else ""))
    if not fresh and not pend and os.path.exists(os.path.join(config.player_dir(sid), "advice.json")):
        attach_plan(sid)  # history-only updates (sessions, friends, playtime) still change the plan
        return sid
    ensure_demos(reg, only=set(fresh) | pend)
    ensure_deep()
    import population
    import style
    population.run_all()
    style.run_all(workers=4)
    if analyze_player(sid, reg):
        attach_extras(sid)
        attach_plan(sid)
    log("Sync done")
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steamid", help="SteamID64, Steam profile link or custom URL name")
    ap.add_argument("--sharecode", action="append")
    ap.add_argument("--authcode")
    ap.add_argument("--knowncode")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--own", action="store_true", help="also fetch your own recent matches")
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    own_id, own_name = config.logged_in_account()
    target_name = None
    if args.steamid:
        import leetify
        sid, target_name = leetify.resolve_steamid(args.steamid)
        if not sid:
            log(f"Profile not found: {args.steamid}")
            return
        log(f"Profile: {target_name or '?'} ({sid})")
        args.steamid = sid
    s = config.settings()
    s.setdefault("own_steamid", own_id)
    s.setdefault("players", {}).setdefault(str(own_id), {"name": own_name})
    if args.steamid:
        s["players"].setdefault(str(args.steamid), {})
        if target_name:
            s["players"][str(args.steamid)]["name"] = target_name
    config.save_settings(s)
    if not args.build_only:
        reg = collect(args, own_id)
        ensure_demos(reg)
        ensure_deep()
        import population
        import style
        population.run_all()
        style.run_all(workers=4)
        targets = [args.steamid] if args.steamid else [own_id]
        for sid in targets:
            if analyze_player(sid, reg):
                attach_extras(sid)
                attach_plan(sid)
    import build_app
    build_app.main()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
