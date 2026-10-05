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
    pw = os.environ.get("COACH_FTP_PASSWORD") or getpass.getpass(f"FTP password of {user}@{host} (not stored): ")
    ftp = ftplib.FTP_TLS(host, timeout=60)
    ftp.login(user, pw)
    ftp.prot_p()   # the files encrypted too, not only the login
    ftp.cwd(rdir)
    if (s.get("deploy") or {}) != {"host": host, "user": user, "dir": rdir}:
        s["deploy"] = {"host": host, "user": user, "dir": rdir}
        config.save_settings(s)
    made, sent, kept = set(), 0, 0
    for p, r in todo:
        size = os.path.getsize(p)
        if r.startswith("releases/") and r.endswith(".zip") and remote_size(ftp, r) == size:
            kept += 1   # a published release never changes
            continue
        ensure_dir(ftp, r, made)
        tmp = r + ".uploading"
        with open(p, "rb") as fh:
            ftp.storbinary(f"STOR {tmp}", fh, blocksize=1 << 20)
        try:
            ftp.delete(r)
        except ftplib.error_perm:
            pass
        ftp.rename(tmp, r)
        sent += 1
        print(f"  {r} ({size / 2 ** 20:.1f} MB)", flush=True)
    if "--prune" in sys.argv:
        man = json.load(open(os.path.join(SRC, "releases", "latest.json"), encoding="utf-8"))
        keep = {v["file"] for v in man.values() if isinstance(v, dict) and v.get("file")}
        for name in ftp.nlst("releases"):
            b = name.rsplit("/", 1)[-1]
            if b.endswith(".zip") and b not in keep:
                ftp.delete(f"releases/{b}")
                print(f"  removed releases/{b}")
    ftp.quit()
    print(f"published: {sent} file(s) sent, {kept} release file(s) already there · https://wily.valentingassend.com")


if __name__ == "__main__":
    main()
