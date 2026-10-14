"""Pro demos for the pro base: the latest top-tier matches on HLTV (its results, 2 stars and more by default) that the
base does not have yet, downloaded and analyzed by pro.py like your matches, kept apart from the pub base (out/deep_pro;
their match, teams and event in out/pro/matches.json), each archive deleted once analyzed. Politely: pauses between
HLTV pages, two downloads at a time. It waits while CS2 is open or the app analyzes, records or transcribes, and stops
when the disk has 150 GB left (the base's own rules, grow.py); then the pro references are computed again (the
mid-round numbers of the pros, the lineups found in their throws).

Usage: python -m wily.base.fetch_demos [matches=20] [--stars 2]     the latest top-tier matches
       python -m wily.base.fetch_demos --teams [--per-team 4]        the latest matches of the current top teams
       python -m wily.base.fetch_demos --import [folder or file]     demos you downloaded yourself from HLTV (default: Downloads)
       python -m wily.base.fetch_demos --matchlist                    the demos of your cached match list (its first job)

04/10: Antigravity's version tried HLTV demo numbers one by one down from 88000, up to 5,000 demos (about 2 TB from
HLTV), and put them in the pub base (out/deep) among the players of your rank; its 36 folders (matches of February
2025) are kept apart in out/deep_hltv_antigravity."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from wily.core import config

WAIT = 60   # seconds between two checks while CS2 is open or the app is busy


def _go():
    """Before each download: wait while CS2 is open or the app is busy; False when the disk is too full to go on."""
    from wily.base import grow
    while True:
        if grow.free_gb() < grow.MIN_FREE_GB:
            print(f"stopped: {grow.free_gb():.0f} GB left on the disk (the base keeps {grow.MIN_FREE_GB} GB)", flush=True)
            return False
        why = grow.busy()
        if not why:
            return True
        print(f"waiting: {why}", flush=True)
        time.sleep(WAIT)


def _pro():
    """The pro demos' downloader: a local module of this PC, not in the repository (10/10)."""
    try:
        from wily.base import pro
        return pro
    except ImportError:
        raise SystemExit("the pro demo tools (pro.py) are a local module, absent from this copy")


def pro_demos(n=20, stars=2, teams=False, per_team=4):
    pro = _pro()
    if not _go():
        return
    before = sum(len(v.get("demos") or []) for v in _registry().values())
    if teams:
        from wily.base import pro_directory
        pro.main(teams=list(pro_directory.CURRENT), per_team=per_team, workers=2, wait=_go)
    else:
        pro.main(n, stars, workers=2, wait=_go)
    added = sum(len(v.get("demos") or []) for v in _registry().values()) - before
    print(f"{added} pro map(s) added", flush=True)
    if added:
        _refresh()


def _refresh():
    """The pros' references again: their mid-round numbers, the catalog's lineups found in their throws."""
    from wily.insights import midround
    from wily.insights import nades_catalog
    midround.run_all(workers=1, log=print)
    nades_catalog.run_all(log=print)


def import_demos(path):
    """Pro demos you downloaded yourself (the GOTV demo button of a match page on HLTV): every .rar, .zip or .dem of
    that folder (or that file) goes to the pro base like a fetched one. Your files stay where they are; their teams are
    read from the demos, the date is the file's."""
    import re
    import shutil
    import subprocess
    from wily.demos import deep
    from wily.demos import style
    pro = _pro()
    files = [path] if os.path.isfile(path) else sorted(os.path.join(path, f) for f in os.listdir(path)
                                                       if f.lower().endswith((".rar", ".zip", ".dem")))
    reg = _registry()
    added = 0
    for f in files:
        stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(f))[0].lower()).strip("-")[:60]
        key = f"dl:{stem}"
        if key in reg and reg[key].get("demos"):
            print(f"{os.path.basename(f)}: already in the pro base", flush=True)
            continue
        if not _go():
            break
        tmp = os.path.join(pro.RAW, f"import_{stem}")
        if f.lower().endswith(".dem"):
            dems = [f]
        else:
            r = subprocess.run([pro.SEVENZIP, "e", "-y", f"-o{tmp}", f, "*.dem", "-r"], capture_output=True, timeout=1800,
                               creationflags=config.NO_WINDOW)
            dems = sorted(os.path.join(tmp, x) for x in os.listdir(tmp) if x.endswith(".dem")) if r.returncode == 0 and os.path.exists(tmp) else []
            if not dems:
                print(f"{os.path.basename(f)}: no demo inside (or 7-Zip could not open it)", flush=True)
        done = []
        for i, dem in enumerate(dems):
            pid = f"pro_dl_{stem}_{i}"
            try:
                if not os.path.exists(os.path.join(pro.DEEP_PRO, pid, "meta.json")):
                    deep.extract(dem, os.path.join(pro.DEEP_PRO, pid))
                style.extract(pid, deep_dir=pro.DEEP_PRO, out_dir=pro.STYLE_PRO)
                done.append({"id": pid, "file": os.path.basename(dem), "teams": pro.clan_names(dem)})
            except Exception as e:
                print(f"  {os.path.basename(dem)}: {e}", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
        if done:
            names = [t for d in done for t in d["teams"].values()]
            maps = []
            for d in done:
                try:
                    with open(os.path.join(pro.DEEP_PRO, d["id"], "meta.json"), encoding="utf-8") as fh:
                        maps.append(json.load(fh)["map"])
                except (OSError, ValueError, KeyError):
                    pass
            reg[key] = {"match_id": key, "slug": stem, "demo_id": None, "teams": sorted(set(names), key=names.count, reverse=True)[:2],
                        "event": None, "date": time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(f))), "maps": maps,
                        "demos": done, "source": "downloaded"}
            with open(os.path.join(pro.PRO, "matches.json"), "w", encoding="utf-8") as fh:
                json.dump(reg, fh, ensure_ascii=False, indent=1)
            added += len(done)
            print(f"{os.path.basename(f)}: {' vs '.join(reg[key]['teams']) or 'teams not in the demo'}, {len(done)} map(s)", flush=True)
    print(f"{added} pro map(s) added", flush=True)
    if added:
        _refresh()


def _registry():
    try:
        with open(os.path.join(config.OUT, "pro", "matches.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def matchlist():
    """The demos of the cached match list (coach.py), 3 at a time, kept."""
    from wily.matches.coach import CACHE, decompress, download

    def get(m):
        dem = os.path.join(CACHE, f"{m['match_id']}.dem")
        if os.path.exists(dem):
            return f"{m['match_id']} already there"
        bz = dem + ".bz2"
        download(m["url"], bz)
        decompress(bz, dem)
        os.remove(bz)
        return f"{m['match_id']} OK"

    ms = [m for m in json.load(open(os.path.join(CACHE, "matchlist.json"))) if m.get("url")]
    with ThreadPoolExecutor(3) as ex:
        for f in [ex.submit(get, m) for m in ms]:
            try:
                print(f.result(), flush=True)
            except Exception as e:
                print("ERROR", e, flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a and a.index(k) + 1 < len(a) else d
    # the number of matches: a number that is not an option's value ("--stars 1" is not 1 match)
    n = next((int(x) for i, x in enumerate(a) if x.isdigit() and (i == 0 or a[i - 1] not in ("--stars", "--per-team"))), 20)
    if "--matchlist" in a:
        matchlist()
    elif "--import" in a:
        i = a.index("--import")
        import_demos(a[i + 1] if i + 1 < len(a) else os.path.join(os.path.expanduser("~"), "Downloads"))
    else:
        pro_demos(n=n, stars=opt("--stars", 2), teams="--teams" in a, per_team=opt("--per-team", 4))
    print("DONE", flush=True)
