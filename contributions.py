"""The matches players share, into the base (05/10): pulled from wily.valentingassend.com (api/pull.php, with the
coach's token), checked again here before anything joins the base, kept once (anon.fingerprint: the same match shared
by two players, or already in the base), then processed like a match of the base loop (grow.follow_ups).

    python contributions.py init     the coach's token: raw in out/settings.json ("contrib_token"), its hash in
                                     web/api/config.php (published with the site; the token never leaves this PC)
    python contributions.py pull     downloads the waiting zips into out/contrib_in, then deletes them on the site
    python contributions.py ingest   checks them and adds their matches to the base
    python contributions.py          both (the base loop does it every hour while it runs)

A match is refused when: its id is not a shared one (8 + 18 digits), a file is not one of the app's tables, a table
has a column the app does not write, a real SteamID or a name is left in it, its map is unknown, or its numbers are not
those of a match (rounds, players, positions)."""
import io
import json
import os
import secrets
import shutil
import sys
import time
import urllib.request
import zipfile

import pyarrow.parquet as pq

import anon
import config

API = os.environ.get("COACH_CONTRIB_API") or "https://wily.valentingassend.com/api/"
INBOX = os.path.join(config.OUT, "contrib_in")
SEEN_F = os.path.join(config.OUT, "contrib_seen.json")
CONFIG_PHP = os.path.join(config.HERE, "web", "api", "config.php")
TABLES = {"duels", "grenades", "samples", "rounds", "loadout", "deaths_w", "steps", "sounds"}
NEEDED = {"meta.json", "rounds.parquet", "samples.parquet", "duels.parquet", "loadout.parquet"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def init():
    """A new token: the old one stops working once the site has the new config.php."""
    tok = secrets.token_urlsafe(32)
    s = config.settings()
    s["contrib_token"] = tok
    config.save_settings(s)
    import hashlib
    os.makedirs(os.path.dirname(CONFIG_PHP), exist_ok=True)
    open(CONFIG_PHP, "w", encoding="utf-8", newline="\n").write(
        "<?php\n// written by `python contributions.py init` on the coach's PC: the hash of its token, never the token\n"
        f"return ['token_sha256' => '{hashlib.sha256(tok.encode()).hexdigest()}', 'max_bytes' => 25 * 1024 * 1024, "
        "'per_day' => 40, 'per_ip_day' => 80];\n")
    log(f"token written in out/settings.json, its hash in {CONFIG_PHP}: publish the site (deploy_site.py) for it to work")


def _req(action, f=None, post=False):
    tok = config.settings().get("contrib_token")
    if not tok:
        raise SystemExit("no token yet: python contributions.py init, then publish the site")
    url = API + "pull.php?action=" + action + (f"&f={f}" if f else "")
    req = urllib.request.Request(url, data=b"" if post else None, method="POST" if post else "GET",
                                 headers={"X-Coach-Token": tok, "User-Agent": "CoachCS2-coach"})
    return urllib.request.urlopen(req, timeout=120)


def pull():
    """The waiting zips: downloaded, their sha256 checked, then deleted on the site. -> how many."""
    os.makedirs(INBOX, exist_ok=True)
    files = json.loads(_req("list").read()).get("files") or []
    n = 0
    for x in files:
        dst = os.path.join(INBOX, x["f"])
        data = _req("get", x["f"]).read()
        import hashlib
        if hashlib.sha256(data).hexdigest() != x.get("sha256"):
            log(f"{x['f']}: damaged on the way, left on the site")
            continue
        open(dst, "wb").write(data)
        config.write_json(dst[:-4] + ".json", x.get("meta") or {})
        _req("delete", x["f"], post=True)
        n += 1
    if files:
        log(f"pulled {n} of {len(files)} shared upload(s)")
    return n


def _expected():
    """The columns each table has in the app's own extractions (the newest matches of the base)."""
    cols = {}
    for mid in sorted(os.listdir(config.DEEP), reverse=True)[:30] if os.path.isdir(config.DEEP) else []:
        for f in os.listdir(os.path.join(config.DEEP, mid)):
            if f.endswith(".parquet") and f[:-8] in TABLES:
                try:
                    cols.setdefault(f[:-8], set()).update(pq.read_schema(os.path.join(config.DEEP, mid, f)).names)
                except Exception:
                    pass
    return cols


def _maps():
    return {f[:-5] for f in os.listdir(os.path.join(config.HERE, "maps")) if f.endswith(".json")}


def check_match(files, expected, maps):
    """One shared match ({file: bytes}): [] when it can join the base, else what is wrong."""
    bad = []
    names = set(files)
    if not NEEDED <= names:
        bad.append(f"missing {sorted(NEEDED - names)}")
    for f in names - {"meta.json"}:
        if not (f.endswith(".parquet") and f[:-8] in TABLES):
            bad.append(f"unexpected {f}")
    try:
        meta = json.loads(files.get("meta.json") or b"{}")
    except ValueError:
        return ["meta.json unreadable"]
    if meta.get("map") not in maps:
        bad.append(f"unknown map {meta.get('map')!r}")
    if anon.SID_RE.search((files.get("meta.json") or b"").decode("utf-8", "replace")):
        bad.append("a SteamID in meta.json")
    for f, b in files.items():
        if not f.endswith(".parquet") or f[:-8] not in TABLES:
            continue
        try:
            tb = pq.read_table(io.BytesIO(b))
        except Exception:
            bad.append(f"{f} unreadable")
            continue
        extra = set(tb.column_names) - expected.get(f[:-8], set(tb.column_names))
        if extra:
            bad.append(f"{f}: columns the app does not write {sorted(extra)[:5]}")
        left = anon.leftovers(tb)
        if left:
            bad.append(f"{f}: {left}")
        if f == "rounds.parquet" and not 1 <= tb.num_rows <= 60:
            bad.append(f"{tb.num_rows} rounds")
        if f == "samples.parquet":
            if not 100 <= tb.num_rows <= 400000:
                bad.append(f"{tb.num_rows} positions")
            elif "steamid" in tb.column_names and len(set(tb.column("steamid").to_pylist())) > 14:
                bad.append("more than 14 players")
    return bad


def _seen():
    """The fingerprints of the base's matches (computed once, then kept) and of the shared ones."""
    s = config.read_json(SEEN_F, {}) or {}
    fps = s.setdefault("fingerprints", {})
    known = set(fps.values())
    for mid in os.listdir(config.DEEP) if os.path.isdir(config.DEEP) else []:
        if mid not in known:
            fp = anon.fingerprint(os.path.join(config.DEEP, mid))
            if fp:
                fps.setdefault(fp, mid)
    config.write_json(SEEN_F, s)
    return s


def ingest(dest=None, follow=True):
    """The pulled zips: every match checked, the new ones into out/deep (or dest), then the base's per-match tables.
    -> how many matches joined."""
    dest = dest or config.DEEP
    zips = sorted(f for f in os.listdir(INBOX) if f.endswith(".zip")) if os.path.isdir(INBOX) else []
    if not zips:
        return 0
    expected, maps, s = _expected(), _maps(), _seen()
    fps, added = s["fingerprints"], 0
    stats = s.setdefault("stats", {"joined": 0, "duplicates": 0, "refused": 0})
    for zf in zips:
        p = os.path.join(INBOX, zf)
        try:
            z = zipfile.ZipFile(p)
            groups = {}
            for m in z.infolist():
                name = m.filename
                if name == "manifest.json" or name.endswith("/"):
                    continue
                mid, _, f = name.partition("/")
                if not (len(mid) == 19 and mid.startswith("8") and mid.isdigit() and f and "/" not in f) or m.file_size > 300 * 2 ** 20:
                    raise ValueError(f"unexpected {name}")
                groups.setdefault(mid, {})[f] = z.read(m)
        except Exception as e:
            log(f"{zf}: refused ({e})")
            stats["refused"] += 1
            shutil.move(p, p + ".refused")
            continue
        for mid, files in groups.items():
            bad = check_match(files, expected, maps)
            if bad:
                log(f"{zf} {mid}: refused ({'; '.join(bad)[:200]})")
                stats["refused"] += 1
                continue
            tmp = os.path.join(dest, f".{mid}.tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp)
            for f, b in files.items():
                open(os.path.join(tmp, f), "wb").write(b)
            fp = anon.fingerprint(tmp)
            if not fp or fp in fps or os.path.exists(os.path.join(dest, mid)):
                shutil.rmtree(tmp, ignore_errors=True)
                stats["duplicates"] += 1
                continue
            os.replace(tmp, os.path.join(dest, mid))
            fps[fp] = mid
            stats["joined"] += 1
            added += 1
        z.close()
        os.makedirs(os.path.join(INBOX, "done"), exist_ok=True)
        shutil.move(p, os.path.join(INBOX, "done", zf))
        if os.path.exists(p[:-4] + ".json"):
            shutil.move(p[:-4] + ".json", os.path.join(INBOX, "done", zf[:-4] + ".json"))
    s["last"] = time.time()
    config.write_json(SEEN_F, s)
    log(f"shared matches: {added} joined the base ({stats['joined']} in all, {stats['duplicates']} already there, {stats['refused']} refused)")
    if added and follow and dest == config.DEEP:
        import grow
        grow.follow_ups()   # midround, buys, T side, population, style: each skips what is done
    return added


def status():
    s = config.read_json(SEEN_F, {}) or {}
    waiting = len([f for f in os.listdir(INBOX) if f.endswith(".zip")]) if os.path.isdir(INBOX) else 0
    return {"token": bool(config.settings().get("contrib_token")), "stats": s.get("stats") or {}, "last": s.get("last"), "waiting": waiting}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "init" in sys.argv:
        init()
    else:
        if "ingest" not in sys.argv:
            pull()
        if "pull" not in sys.argv:
            ingest()
