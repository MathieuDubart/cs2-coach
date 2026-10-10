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
from coach import DemoGone, decompress, download, game_mode

REGISTRY = os.path.join(config.CACHE, "matches.json")


LOG_HOOK = None  # set by the local server to stream progress to the page


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    if LOG_HOOK:
        LOG_HOOK(msg)


def registry():
    if not os.path.exists(REGISTRY):
        return {}
    with open(REGISTRY) as f:
        return json.load(f)


def save_registry(r):
    """Merged into the file as it is now, then replaced in one go: the base-growing loop (grow.py, its own process)
    writes it too, and a reader never gets half a file."""
    import time
    cur = registry()
    cur.update(r)
    tmp = f"{REGISTRY}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(cur, f, indent=1)
    for _ in range(50):
        try:
            os.replace(tmp, REGISTRY)
            return
        except PermissionError:   # the other process is reading it this very moment
            time.sleep(0.1)
    os.replace(tmp, REGISTRY)


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
            log("steam_api_key is missing from out/settings.json to browse the history from the command line.")
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
    by_url = {r["url"]: k for k, r in reg.items() if r.get("url")}
    for m in new:
        if m.get("url"):
            # a match read from Steam's history page (steamhist.py) is kept under its demo's number: the same match
            # given here by its match id joins that entry (its demo is already under that name)
            k = by_url.get(m["url"], m["match_id"])
            reg.setdefault(k, {}).update({**m, "match_id": k})
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


def _fetch_demo(mid, url, gone_tries=None):
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    arc = dem + ".bz2"
    if os.path.exists(arc) and not os.path.exists(arc + ".part"):  # left by an earlier, cut download: resume it
        os.replace(arc, arc + ".part")
    download(url, arc, gone_tries=gone_tries)
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
        config.wait_for_match_end(log, "demo downloads")
        log(f"Downloading {len(todo)} demo(s) from Valve…")
    with ThreadPoolExecutor(workers) as ex:
        # an old match (past Valve's month): 2 tries before calling it gone; a recent one: patience (network hiccups)
        futs = {ex.submit(lambda a, b, g: (config.wait_for_match_end(), _fetch_demo(a, b, g))[1], mid, url,
                          None if _recent(reg[mid]) else 2): mid for mid, url in todo.items()}
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
                elif isinstance(e, DemoGone):
                    reg[mid]["expired"] = True
                    log(f"  [{mid}] demo unavailable ({e}): Valve only keeps it for about a month")
                else:   # cut in the middle: not gone, tried again at the next analysis
                    log(f"  [{mid}] download failed ({e}): tried again at the next analysis")
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


def _extract(src, out):
    """deep.extract in a worker: the demo parser's panics (not an Exception) come back as a plain error."""
    import deep
    try:
        deep.extract(src, out)
    except BaseException as e:   # pyo3 PanicException derives from BaseException
        raise RuntimeError(f"{type(e).__name__}: {str(e)[:200]}") from None


def _in_workers(fn, jobs, workers, done, batch=0, wait=None):
    """fn(*args) for each (key, args) of jobs, in `workers` processes at the lowest priority: done(key, result, error)
    as each one ends; with batch, `batch` jobs at a time and wait() before each batch. A worker that dies (memory
    exhausted, a crash inside the demo parser) breaks the whole pool and every job still in it fails with it: those
    run again one at a time in their own process, then the rest goes on in a new pool. A job that stops its process
    even alone fails; the others go on."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from concurrent.futures.process import BrokenProcessPool
    jobs = list(jobs)
    while jobs:
        lost = []
        with ProcessPoolExecutor(workers, initializer=config.low_priority) as ex:
            while jobs and not lost:
                if wait:
                    wait()
                n = batch or len(jobs)
                part, jobs = jobs[:n], jobs[n:]
                futs = {}
                for key, args in part:
                    try:
                        futs[ex.submit(fn, *args)] = (key, args)
                    except BrokenProcessPool:
                        lost.append((key, args))
                for fu in as_completed(futs):
                    try:
                        done(futs[fu][0], fu.result(), None)
                    except BrokenProcessPool:
                        lost.append(futs[fu])
                    except Exception as e:
                        done(futs[fu][0], None, e)
        for key, args in lost:
            log(f"[{key}] its process stopped abruptly (out of memory?): again, alone")
            if wait:
                wait()
            with ProcessPoolExecutor(1, initializer=config.low_priority) as ex:
                try:
                    done(key, ex.submit(fn, *args).result(), None)
                except BrokenProcessPool:
                    done(key, None, RuntimeError("its process stops abruptly even alone (memory, or a demo the parser "
                                                 "cannot read): skipped"))
                except Exception as e:
                    done(key, None, e)


def _ensure_deep(deep):
    """Detailed extraction of the new demos: in separate processes at the lowest priority (the game and the
    app's page keep the CPU), two at a time, waiting for the end of a match between demos."""
    import multiprocessing
    todo = [f[:-4] for f in sorted(os.listdir(config.CACHE)) if f.endswith(".dem")
            and not os.path.exists(os.path.join(config.DEEP, f[:-4], "meta.json"))]
    if not todo:
        return

    if multiprocessing.current_process().name != "MainProcess":   # already a worker: stay in it
        for mid in todo:
            config.wait_for_match_end(log, "demo extraction")
            log(f"[{mid}] detailed extraction")
            try:
                _extract(os.path.join(config.CACHE, f"{mid}.dem"), os.path.join(config.DEEP, mid))
            except Exception as e:
                log(f"[{mid}] extraction ERROR: {e}")
        return
    _in_workers(_extract, [(mid, (os.path.join(config.CACHE, f"{mid}.dem"), os.path.join(config.DEEP, mid))) for mid in todo],
                2, lambda mid, _, err: log(f"[{mid}] extraction ERROR: {err}" if err else f"[{mid}] detailed extraction"),
                batch=2, wait=lambda: config.wait_for_match_end(log, "demo extraction"))


_PM = {"key": None, "index": {}}


def _match_index():
    """steamid -> match ids of the cached demos, read once per process while the demo folder keeps its matches
    (05/10: each profile read the positions file of every match, 2,000 files per profile)."""
    import pandas as pd
    try:
        es = [e for e in os.scandir(config.DEEP) if e.is_dir()]
    except OSError:
        return {}
    key = (len(es), max((e.stat().st_mtime for e in es), default=0))
    if _PM["key"] != key:
        idx = {}
        for e in es:
            p = os.path.join(e.path, "samples.parquet")
            if not os.path.exists(p):
                continue
            try:
                ids = set(pd.read_parquet(p, columns=["steamid"]).steamid)
            except Exception:   # a file the base loop is writing (it failed a profile's plan, 05/10): left out this time
                continue
            for s in ids:
                try:
                    idx.setdefault(int(s), []).append(e.name)
                except (TypeError, ValueError):
                    pass
        _PM.update(key=key, index=idx)
    return _PM["index"]


def player_matches(steamid):
    """Match ids of cached demos where this player appears."""
    try:
        return list(_match_index().get(int(steamid), []))
    except (TypeError, ValueError):
        return []


def _analyze_match(steamid, mid, m):
    """One match for one player (runs in a worker process)."""
    import analyze
    import map_analysis
    config.wait_for_match_end()   # a match started meanwhile: this worker waits for its end
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
            config.wait_for_match_end(log, "match analysis")
            _in_workers(_analyze_match, [(mid, (steamid, mid, reg.get(mid, {}))) for mid in todo], min(8, len(todo)),
                        lambda mid, res, err: log("  " + (f"[{mid}] ERROR: {err}" if err else res)))
        else:  # already inside a worker (batch profiling): stay sequential
            for mid in todo:
                config.wait_for_match_end(log, "match analysis")
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


def rebuild_advice(steamid):
    """The advice again from the analyses already done (after a change in how rules are picked): no demo is
    read again. What doesn't come from the demos (Steam, csstats.gg, Leetify) is kept."""
    import advice
    pdir = config.player_dir(steamid)
    p = os.path.join(pdir, "advice.json")
    if not os.path.exists(os.path.join(pdir, "cross.json")) or not os.path.exists(p):
        return False   # light profile (no demo): nothing to recompute
    old = json.load(open(p, encoding="utf-8"))
    new = advice.build(pdir)
    new.update({k: v for k, v in old.items() if k not in new and k != "plan"})
    config.write_json(p, new, indent=1)
    return True


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def reanalyze_match(steamid, mid):
    """One match again, from its demo: everything extracted from it (positions, duels, grenades, round context,
    mid-round, buys, T side, reference population, style), then the player's analysis of the match, profile,
    plan and page. For a match analyzed with an older version or interrupted (app closed during the analysis)."""
    import shutil
    sid, mid = int(steamid), str(int(mid))
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    reg = registry()
    if not os.path.exists(dem):
        if not (reg.get(mid) or {}).get("url"):
            raise ValueError("The demo of this match is no longer on this PC, and Valve no longer has it.")
        log("The demo is no longer on this PC: downloading it again…")
        ensure_demos(reg, only={mid})
        if not os.path.exists(dem):
            raise ValueError("Valve no longer has this demo (demos are kept about a month).")
    log(f"[{mid}] clearing the previous analysis of this match")
    shutil.rmtree(os.path.join(config.DEEP, mid), ignore_errors=True)
    for sub in ("midround", "routes", "buys", "tside"):
        _rm(os.path.join(config.OUT, "population", sub, f"{mid}.parquet"))
    _rm(os.path.join(config.OUT, "population", f"{mid}.parquet"))
    _rm(os.path.join(config.OUT, "style", f"{mid}.parquet"))
    pdir = config.player_dir(sid)
    shutil.rmtree(os.path.join(pdir, "matches", mid), ignore_errors=True)
    ensure_deep()
    if not os.path.exists(os.path.join(config.DEEP, mid, "meta.json")):
        raise ValueError("The demo could not be read again: it may be damaged. Delete it from the cache folder and sync again.")
    import population
    import style
    log(f"[{mid}] reference population and style")
    population.run_all()
    style.run_all(workers=2)
    p = os.path.join(pdir, "advice.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    log("Updating your profile with this match…")
    if not analyze_player(sid, reg):
        raise ValueError("You are not in this demo.")
    new = json.load(open(p, encoding="utf-8"))
    kept = {k: v for k, v in old.items() if k not in new and k != "plan"}   # Steam, csstats.gg...: not from the demos
    if kept:
        new.update(kept)
        json.dump(new, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    attach_plan(sid)
    log(f"[{mid}] re-analysis done")
    return sid


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
        adv.pop("plan_error", None)
    except Exception as e:
        log(f"Progress plan unavailable: {e}")
        traceback.print_exc()
        adv["plan_error"] = f"{type(e).__name__}: {e}"[:200]   # the previous plan stays; the page says it is not up to date
        config.write_json(p, adv, indent=1, default=str)
        return
    try:   # the focus of the week: the first axis, kept 7 days (Live, Prepare and Review show it)
        import focus
        adv["plan"]["focus"] = focus.weekly(sid, adv.get("rules"))
    except Exception as e:
        log(f"Focus of the week unavailable: {e}")
    try:   # your frequent teammates' usual CT spots: dead, the one you watch tells where the fight is
        import team
        adv["plan"]["mates"] = team.mates_regions(sid)
    except Exception as e:
        log(f"Teammates' spots unavailable: {e}")
    try:   # what the In game page showed in your matches, against their demos (and the calibration it gives)
        import livecheck
        adv["plan"]["livecheck"] = livecheck.run(sid)
    except Exception as e:
        log(f"Live check unavailable: {e}")
    try:  # coach notes per map and side (zones to change or keep, grenades), from the cross-match analysis
        import coach_notes
        coach_notes.write(sid, load("cross.json"), adv.get("plan"))
    except Exception as e:
        log(f"Map notes unavailable: {e}")
        adv["plan"].setdefault("unavailable", []).append("map notes")
    config.write_json(p, adv, indent=1, default=str)


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
    """Public info available for anyone: the Steam profile, and the ranks of a local source module when this PC has
    one (csstats, not versioned: 10/10, kept out of the public repository)."""
    import steamprofile
    out = {}
    try:
        out["steam"] = steamprofile.steam_profile(sid)
    except Exception:
        pass
    try:
        import csstats
        cs = csstats.fetch(sid)
        if cs:
            out["csstats"] = cs
    except Exception:   # ImportError: no such module here
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
                      "title": f"Premier {cur['season']}: {cur['current']:,} (best {cur['best']:,}), vs {prev['current']:,} in {prev['season']}",
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
    if sid and not own and not (s.get("players", {}).get(str(sid)) or {}).get("authcode"):
        log("Only the matches already on this PC (played with you, or added by a share code) can be analyzed for this player. "
            "For a match they played without you: paste its share code (CSGO-…) here, or add their history code in their Analysis tab.")
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
    # share codes only. Full profiles for you, the players you follow and your teammates in those matches, plus an
    # update of the players already profiled; the others (opponents, strangers) only feed the base: a search builds
    # their profile on demand. A batch of 14 matches used to build ~110 profiles of strangers (hours of CPU).
    import pandas as pd
    players, keep, met = {}, set(), set()
    ps = config.settings().get("players", {})
    anchors = {int(own_id or 0)} | {int(k) for k, v in ps.items() if k.isdigit() and v.get("authcode")}
    profiled = {int(k) for k in (os.listdir(config.PLAYERS) if os.path.exists(config.PLAYERS) else [])
                if k.isdigit() and os.path.exists(os.path.join(config.player_dir(k), "cross.json"))}
    for mid in code_ids:
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if not os.path.exists(f):
            continue
        S = pd.read_parquet(f, columns=["steamid", "name", "side", "round"])
        side = dict(S[S["round"] == S["round"].min()].drop_duplicates("steamid")[["steamid", "side"]].itertuples(index=False))
        for p_id, nm in S.drop_duplicates("steamid")[["steamid", "name"]].itertuples(index=False):
            if p_id:
                players[int(p_id)] = nm
        ours = {side[a] for a in anchors if a in side}
        met |= {int(p) for p in side if p and int(p) in anchors}
        keep |= {int(p) for p, sd in side.items() if p and (sd in ours or int(p) in profiled)}
    if not players:
        raise ValueError("No match fetched with this code: the demo may have expired at Valve (about 1 month).")
    if not met:   # matches without you or anyone you follow (another team's matches): everyone, as asked
        keep = set(players)
    s = config.settings()
    for p_id, nm in players.items():
        s.setdefault("players", {}).setdefault(str(p_id), {})["name"] = nm
    config.save_settings(s)
    others = len(players) - len(keep)
    log(f"{len(players)} players in this/these match(es): building {len(keep)} profile(s)"
        + (f" (you, your teammates and players already profiled; the {others} others feed the base, search one to see their profile)…" if others else "…"))
    players = {p: nm for p, nm in players.items() if p in keep}
    for i, (p_id, nm) in enumerate(players.items(), 1):
        config.wait_for_match_end(log, "profile building")
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
    try:
        steamlink.friends(key, sid, refresh=True)   # no key of your own: through Wily's site (08/10)
        pt = steamlink.owned_cs2(key, sid) if key else None   # without a key: this PC's Steam says the playtime
        if pt:
            s = config.settings()
            s.setdefault("players", {}).setdefault(str(sid), {})["playtime"] = pt
            config.save_settings(s)
    except steamlink.SteamError as e:
        log(f"Steam: {e}")
    before = registry()
    args = SimpleNamespace(steamid=sid, sharecode=codes, authcode=None, knowncode=None, no_fetch=False, own=(sid == own_id))
    reg = collect(args, own_id)
    try:   # the FACEIT matches of the last month (10/10), when the FACEIT key is set: no demo, the rest counts
        import faceit
        if faceit.key() and faceit.add_matches(sid, log=log):
            reg = registry()
    except Exception as e:
        log(f"FACEIT: {e}")
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
