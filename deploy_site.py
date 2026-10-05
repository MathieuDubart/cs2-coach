"""Publishes dist/site_wily on https://wily.valentingassend.com (Infomaniak web hosting, 05/10) over FTPS: FTP with
TLS for the login and the files (Python's standard library, nothing to install).

The FTP account is the coach's own, made in Infomaniak's Manager (Web hosting > FTP / SSH accounts). Its password is
typed at the prompt (or in the COACH_FTP_PASSWORD variable of this window only) and never written anywhere.

    python deploy_site.py                       the pages, the API and the latest release
    python deploy_site.py --host <ftp host> --user <account> --dir <the site's folder>
                                                the first time (kept in out/settings.json "deploy", without password)
    options: --dry-run (lists what would go), --prune (removes the releases no longer in latest.json)

Order: the release files first, latest.json and its signature last, so an app never reads a manifest whose files
are not there yet. A file goes up under a temporary name, then is renamed."""
import ftplib
import getpass
import json
import os
import sys

import config

SRC = os.path.join(config.HERE, "dist", "site_wily")


def arg(k):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None


def files():
    """(local path, remote relative path) in upload order: the releases' zips, the rest, latest.json(.sig) last."""
    out = []
    for root, _, fs in os.walk(SRC):
        for f in fs:
            p = os.path.join(root, f)
            out.append((p, os.path.relpath(p, SRC).replace(os.sep, "/")))
    last = {"releases/latest.json", "releases/latest.json.sig"}
    return sorted([x for x in out if x[1] not in last], key=lambda x: (not x[1].endswith(".zip"), x[1])) + \
        sorted([x for x in out if x[1] in last], key=lambda x: x[1].endswith(".sig"))


def ensure_dir(ftp, path, made):
    parts = path.split("/")[:-1]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p
        if cur in made:
            continue
        try:
            ftp.mkd(cur)
        except ftplib.error_perm:
            pass   # already there
        made.add(cur)


def remote_size(ftp, path):
    try:
        return ftp.size(path)
    except ftplib.all_errors:
        return None


LOG_F = os.path.join(config.OUT, "deploy.log")
STATE_F = os.path.join(config.OUT, "deploy_state.json")   # the sha256 of each file as last sent, per site


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def unchanged(state, r, p, ftp):
    """Already on the site as it is here: its sha256 as last sent; for a zip whose name carries its content (a
    runtime's key, a base's version) never sent from this record, the same size on the site. A code or full-install
    zip keeps its name across builds of one version (05/10): only its sha256 tells."""
    if state.get(r) == sha256(p):
        return remote_size(ftp, r) == os.path.getsize(p) if r.endswith(".zip") else True
    b = r.rsplit("/", 1)[-1]
    return r not in state and b.startswith(("runtime-", "base-")) and remote_size(ftp, r) == os.path.getsize(p)


def log(msg):
    """On screen and in out/deploy.log (followed from elsewhere while it runs)."""
    import time
    print(msg, flush=True)
    with open(LOG_F, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def site_dir(ftp, rdir):
    """The site's folder: the one given, else found from where the account starts (an account can start in it)."""
    for d in (rdir, rdir.lstrip("/"), "."):
        try:
            ftp.cwd(d)
        except ftplib.error_perm:
            continue
        here = ftp.pwd()
        names = {n.rsplit("/", 1)[-1] for n in ftp.nlst()}
        if d == "." and not ({"index.html", "releases", "api"} & names):
            break
        return here
    raise SystemExit(f"the site's folder {rdir} is not reachable with this account (it starts in {ftp.pwd()}): "
                     f"python deploy_site.py --dir <folder>")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.isdir(SRC):
        raise SystemExit("nothing to publish: python make_beta.py --release <version> (or python site_wily.py)")
    if not os.path.exists(os.path.join(SRC, "api", "config.php")):
        print("note: api/config.php is missing (python contributions.py init): sharing will answer 'storage' errors until then")
    s = config.settings()
    d = s.get("deploy") or {}
    host, user, rdir = arg("--host") or d.get("host"), arg("--user") or d.get("user"), arg("--dir") or d.get("dir")
    if not (host and user and rdir):
        raise SystemExit("the first time: python deploy_site.py --host <ftp host> --user <account> --dir <the site's folder>")
    todo = files()
    if "--dry-run" in sys.argv:
        for p, r in todo:
            print(f"{os.path.getsize(p) / 2 ** 20:9.2f} MB  {r}")
        return
    total = sum(os.path.getsize(p) for p, _ in todo)
    print(f"Publishing {len(todo)} files ({total / 2 ** 20:.0f} MB) to {user}@{host}:{rdir}")
    pw = os.environ.get("COACH_FTP_PASSWORD") or getpass.getpass(f"FTP password of {user} (typed here, never stored): ")
    ftp = ftplib.FTP_TLS(host, timeout=120)
    try:
        ftp.login(user, pw)
    except ftplib.error_perm as e:
        log(f"login refused: {e}")
        raise SystemExit("login refused: check the account and its password in Infomaniak's Manager (FTP / SSH)")
    del pw
    ftp.prot_p()   # the files encrypted too, not only the login
    where = site_dir(ftp, rdir)
    log(f"connected over TLS, the site's folder: {where}")
    if (s.get("deploy") or {}) != {"host": host, "user": user, "dir": rdir}:
        s["deploy"] = {"host": host, "user": user, "dir": rdir}
        config.save_settings(s)
    made, sent, kept, done = set(), 0, 0, 0
    allstate = config.read_json(STATE_F, {}) or {}
    state = allstate.setdefault(f"{host}:{rdir}", {})
    for p, r in todo:
        size = os.path.getsize(p)
        if unchanged(state, r, p, ftp):
            kept += 1
            done += size
            continue
        ensure_dir(ftp, r, made)
        tmp = r + ".uploading"
        step = {"n": 0, "next": 0.1}

        def progress(block):
            step["n"] += len(block)
            if size > 20 * 2 ** 20 and step["n"] / size >= step["next"]:
                log(f"  {r}: {int(100 * step['n'] / size)} %")
                step["next"] += 0.1
        with open(p, "rb") as fh:
            ftp.storbinary(f"STOR {tmp}", fh, blocksize=1 << 20, callback=progress)
        try:
            ftp.delete(r)
        except ftplib.error_perm:
            pass
        ftp.rename(tmp, r)
        state[r] = sha256(p)
        config.write_json(STATE_F, allstate)
        sent += 1
        done += size
        log(f"  {r} ({size / 2 ** 20:.1f} MB) · {100 * done / total:.0f} % of the whole")
    if "--prune" in sys.argv:
        man = json.load(open(os.path.join(SRC, "releases", "latest.json"), encoding="utf-8"))
        keep = {v["file"] for v in man.values() if isinstance(v, dict) and v.get("file")}
        for name in ftp.nlst("releases"):
            b = name.rsplit("/", 1)[-1]
            if b.endswith(".zip") and b not in keep:
                ftp.delete(f"releases/{b}")
                log(f"  removed releases/{b}")
    ftp.quit()
    log(f"published: {sent} file(s) sent, {kept} file(s) already there as they are · https://wily.valentingassend.com")


if __name__ == "__main__":
    main()
