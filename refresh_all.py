"""Everything the app shows, computed again from the base as it is now (Settings: "Update the app with the base",
04/10): first what every page reads from the base (the lineups and their groups, Leetify's bands, the sites, routes
and mid-round references, the T side's lanes, plays and tendencies, the weapons, the map facts, the pro lineup
catalog, the training's sites, held spots and real attacks), then the profiles: yours first, then your team's, then
every other analyzed player (their analysis against the base, plan and pages).

At the lowest priority (Windows' background mode: processor, disk and memory); it waits while a map is loaded in CS2,
a recording or a transcription runs, the app analyzes, the base loop is on a match, or the PC is short of memory. Its
progress in out/refresh.json; out/refresh_ctl.json {"stop": true} stops it between two steps.
Usage: python refresh_all.py [--mine] [--now] [--resume] [--since=EPOCH] [--workers=N]
  --mine     the base's references, your profile and your team's only
  --now      also during a match or a transcription (asked on 04/10, playing): only the memory, an analysis of the app
             and the base loop stop it; in Windows' background mode while a map is loaded, at full speed otherwise
  --resume   the base's references are kept (a run that stopped in its profiles goes on)
  --since    the profiles whose page was written after this moment are kept
  --workers  N profiles at once, each in its own process (05/10: 281 profiles took 2 min each, one by one)"""
import glob
import json
import os
import sys
import time
import traceback

import config

STATE = os.path.join(config.OUT, "refresh.json")
CTL = os.path.join(config.OUT, "refresh_ctl.json")
PORT = int(os.environ.get("COACH_PORT", 8765))
ST = {}
NOW = "--now" in sys.argv
IDS = os.path.join(config.OUT, "refresh_ids.json")   # the profiles the workers share out


def arg(name, default=None):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{name}=")), default)


PART = arg("part")   # "i/N": a worker of a run with --workers, its progress in out/refresh_part<i>.json
if PART:
    STATE = os.path.join(config.OUT, f"refresh_part{PART.split('/')[0]}.json")
MIN_FREE = 1.5 * 2 ** 30   # bytes of free memory under which it waits (CS2 froze at 21:32 on 04/10 with 3 GB left)


def save(**kw):
    ST.update(kw, updated=time.time())
    config.write_json(STATE, ST)


def log(msg):
    print(msg, flush=True)
    ST.setdefault("log", []).append(f"{time.strftime('%H:%M:%S')} {msg}")
    ST["log"] = ST["log"][-12:]
    save()


def stopped():
    return bool((config.read_json(CTL, {}) or {}).get("stop"))


def busy():
    """Why it waits now (None: it can go)."""
    import grow
    try:
        import psutil
        if psutil.virtual_memory().available < MIN_FREE:
            return "the PC is short of memory"
    except Exception:
        pass
    s = grow._api("/api/gsi/state") or {}
    config.background(bool(s.get("map")))   # a match: the game first (processor, disk and memory)
    if s.get("map") and not NOW:
        return "a map is loaded in CS2"
    j = grow._api("/api/job")
    if j and j.get("running"):
        return "the app is analyzing"
    v = grow._api("/api/voice/status")
    if v and (v.get("recording") or v.get("transcribing")) and not NOW:
        return "a recording or a transcription"
    g = config.read_json(grow.STATE, {}) or {}
    if g.get("step") and time.time() - g["step"] < 600:
        return "the base loop is on a match"
    return None


def wait():
    """False when asked to stop."""
    while True:
        if stopped():
            return False
        why = busy()
        if not why:
            if ST.get("paused"):
                save(paused=None)
            return True
        if ST.get("paused") != why:
            save(paused=why)
        time.sleep(30)


def _stale(path):
    """A cache whose freshness stamp is erased: its module computes it again on the next read."""
    try:
        c = config.read_json(path, None)
        if isinstance(c, dict):
            c["_stamp"] = "stale"
            config.write_json(path, c)
    except Exception:
        pass


def _training():
    import train
    sid = str(config.settings().get("own_steamid") or "")
    mine = list(train.maps(sid)) if sid.isdigit() else []
    for f in (train.SITES_F, train.SPOTS_F):   # the sites' held spots and where each side stands
        c = config.read_json(f, {}) or {}
        for mp in mine:
            c.pop(mp, None)
        config.write_json(f, c)
    for mp in mine:
        if not wait():
            return
        train.site_data(mp)
        train._spots(mp)
        try:   # the real attacks on each site, from the base's latest demos
            os.remove(os.path.join(train.ENTRY_D, f"{mp}.json"))
        except OSError:
            pass
        train.entries(mp)
        log(f"training: {mp}")


def _tside():
    import lanes
    import tside
    lanes.geo(rebuild=True)
    _stale(tside.SUMMARY)
    tside.tendencies([])   # computed again for every map of the base (and the lanes and plays with it)


def base_steps():
    import leetify
    import midround
    import nades
    import nades_catalog
    import team
    import weapons
    return [
        ("The lineups thrown in the base and their groups", lambda: (nades.load_all(rebuild=True), nades.summary(rebuild=True))),
        ("Leetify's bands of the base's players", lambda: leetify.reference(rebuild=True)),
        ("The sites, routes and mid-round references", lambda: (midround.site_centers(rebuild=True), midround.route_refs(rebuild=True),
                                                                 midround.run_all(workers=1, log=log))),
        ("The T side: how sites are entered, the plays, the tendencies", _tside),
        ("The weapons: the base's numbers and zones", lambda: (weapons.population_weapons(rebuild=True), weapons.weapon_zones(rebuild=True))),
        ("The map facts", lambda: team.map_meta(rebuild=True)),
        ("The pro lineup catalog found in the base's throws", lambda: nades_catalog.run_all(only=nades_catalog.maps(), log=log)),
        ("The training: sites, held spots and real attacks of your maps", _training),
    ]


def profiles(mine_only=False):
    """Yours first, then your team's, then every other analyzed player (the most recently analyzed first)."""
    pdir = os.path.join(config.OUT, "players")
    all_ = [p for p in os.listdir(pdir) if p.isdigit() and os.path.exists(os.path.join(pdir, p, "advice.json"))] if os.path.exists(pdir) else []
    own = str(config.settings().get("own_steamid") or "")
    team = []
    for f in glob.glob(os.path.join(config.OUT, "teams", "*.json")):
        t = config.read_json(f, {}) or {}
        for m in t.get("members") or []:
            s = str(m.get("steamid") if isinstance(m, dict) else m)
            if s in all_ and s not in team and s != own:
                team.append(s)
    first = ([own] if own in all_ else []) + team
    if mine_only:
        return first
    rest = sorted((p for p in all_ if p not in first), key=lambda p: -os.path.getmtime(os.path.join(pdir, p, "advice.json")))
    return first + rest


def below_normal():
    """Below normal, not idle: Windows 11 hardly runs an idle-priority process next to busier ones (05/10: a profile of
    10 s took 17 min beside two transcriptions); during a match, busy() puts it in background mode for the game."""
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        config.low_priority()


def rebuild(sid, name):
    """One profile against the base as it is now: its analysis (light profiles: nothing to redo), plan and page.
    -> its index entry."""
    import build_app
    import cs2coach
    t = time.time()
    try:
        cs2coach.rebuild_advice(sid)
        cs2coach.attach_plan(sid)
        e = build_app.write_player(sid)
        log(f"{name}: {round(time.time() - t)} s")
        return e
    except Exception as e:
        ST["errors"] = (ST.get("errors") or [])[-4:] + [f"{name}: {type(e).__name__}: {str(e)[:160]}"]
        log(f"{name}: failed ({e})")
        traceback.print_exc()
        return None


def _names():
    import build_app
    return {e["steamid"]: e for e in config.read_json(os.path.join(build_app.SITE, "index.json"), []) or [] if isinstance(e, dict) and e.get("steamid")}


def worker():
    """A share of the profiles (--part=i/N); its entries for the index go to its state file, the main run writes it."""
    i, n = (int(x) for x in PART.split("/"))
    ids = (config.read_json(IDS, []) or [])[i::n]
    below_normal()
    index = _names()
    ST.clear()
    save(pid=os.getpid(), running=True, total=len(ids), done=0, current=None, paused=None, errors=[], entries={})
    try:
        for k, sid in enumerate(ids):
            if not wait():
                break
            name = (index.get(sid) or {}).get("name") or sid
            save(current=name)
            e = rebuild(sid, name)
            if e:
                ST["entries"][sid] = e
            save(done=k + 1)
    finally:
        save(running=False, current=None, paused=None)


def _gather(n, index):
    """The workers' progress into the run's state, their profiles into the index."""
    import build_app
    parts = [config.read_json(os.path.join(config.OUT, f"refresh_part{i}.json"), {}) or {} for i in range(n)]
    new = {sid: e for p in parts for sid, e in (p.get("entries") or {}).items() if e and index.get(sid) != e}
    if new:
        index.update(new)
        config.write_json(os.path.join(build_app.SITE, "index.json"), list(index.values()))
    logs = sorted(x for p in parts for x in (p.get("log") or []))
    paused = {p.get("paused") for p in parts if p.get("running")}
    save(profiles_done=sum(p.get("done") or 0 for p in parts), current=", ".join(p["current"] for p in parts if p.get("current")) or None,
         errors=[x for p in parts for x in (p.get("errors") or [])][-5:], log=logs[-12:],
         paused=paused.pop() if len(paused) == 1 and None not in paused else None)


def main():
    if PART:
        return worker()
    mine_only = "--mine" in sys.argv
    workers = max(1, int(arg("workers", 1)))
    since = float(arg("since", 0) or 0)
    below_normal()
    cur = config.read_json(STATE, {}) or {}
    if cur.get("running") and cur.get("pid") and cur["pid"] != os.getpid():
        try:
            import psutil
            if psutil.pid_exists(cur["pid"]) and any("refresh_all.py" in a for a in psutil.Process(cur["pid"]).cmdline()):
                print("already running", flush=True)
                return
        except Exception:
            pass
    config.write_json(CTL, {"stop": False})
    steps = [] if "--resume" in sys.argv else base_steps()
    ids = profiles(mine_only)
    if since:   # pages written since then are already built on the base as it is
        import build_app
        page = lambda sid: os.path.join(build_app.SITE, "players", f"{sid}.json")
        ids = [sid for sid in ids if not (os.path.exists(page(sid)) and os.path.getmtime(page(sid)) > since)]
    ST.clear()
    save(pid=os.getpid(), running=True, started=time.time(), mine_only=mine_only, phase="base", steps_total=len(steps), steps_done=0,
         profiles_total=len(ids), profiles_done=0, current=None, paused=None, errors=[], finished=None, workers=workers)
    try:
        for i, (label, fn) in enumerate(steps):
            if not wait():
                break
            save(current=label)
            t = time.time()
            try:
                fn()
                log(f"{label}: {round(time.time() - t)} s")
            except Exception as e:
                ST["errors"] = (ST.get("errors") or [])[-4:] + [f"{label}: {type(e).__name__}: {str(e)[:160]}"]
                log(f"{label}: failed ({e})")
                traceback.print_exc()
            save(steps_done=i + 1)
        save(phase="profiles")
        index = _names()
        if workers > 1 and len(ids) > 1 and not stopped():
            import subprocess
            config.write_json(IDS, ids)
            for i in range(workers):
                config.write_json(os.path.join(config.OUT, f"refresh_part{i}.json"), {})
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), f"--part={i}/{workers}"] + (["--now"] if NOW else []),
                                      cwd=config.HERE, creationflags=flags) for i in range(workers)]
            while any(p.poll() is None for p in procs):
                time.sleep(10)
                _gather(workers, index)
            _gather(workers, index)
        else:
            import build_app
            for k, sid in enumerate(ids):
                if not wait():
                    break
                name = (index.get(sid) or {}).get("name") or sid
                save(current=name)
                e = rebuild(sid, name)
                if e:
                    index[sid] = e
                    config.write_json(os.path.join(build_app.SITE, "index.json"), list(index.values()))
                save(profiles_done=k + 1)
    finally:
        save(running=False, current=None, paused=None, finished=time.time(), stopped=stopped())


if __name__ == "__main__":
    if sys.stdout is None:   # started by the app without a console (pythonw): its output to out/refresh.log
        sys.stdout = sys.stderr = open(os.path.join(config.OUT, "refresh.log"), "a", encoding="utf-8", buffering=1)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    main()
