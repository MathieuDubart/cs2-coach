"""Messages to the players' apps (14/10, the user: "garde un moyen de diffuser un message à l'intérieur des versions
clientes, sur les futures versions antérieures, pour ce genre de choses": an old version that should update, a match
upload held, anything the coach must say to players he does not know). Published next to the releases
(releases/notices.json) and signed with the release key like latest.json: a player's app fetches it with its update
check (at start-up then every 6 hours), shows only what the coach's key signed, under the top bar, until the player
closes it or it expires. Every version from 0.0.1-alpha's build of 14/10 on reads it; the ones before can't.

    python tools/notices.py list
    python tools/notices.py add ID --en "text" [--fr "texte"] [--de ...] [--level warn] [--link https://...]
                          [--before-build YYYYMMDD-HHMM] [--platform windows|linux] [--days 30]
    python tools/notices.py remove ID

--before-build: only the apps whose build is older (an app that should update); --days: gone after that many days.
The texts: one per language the app speaks (en at least; an app in another language shows the English one). Then
publish the site (python website/deploy.py): the file goes with it."""
import argparse
import base64
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # run as a script: the root, for wily

from wily.core import config
from wily.core import i18n

DIR = os.environ.get("COACH_NOTICES_DIR") or os.path.join(config.HERE, "dist", "site_wily", "releases")
F = os.path.join(DIR, "notices.json")
LEVELS = ("info", "warn")


def load():
    try:
        return json.load(open(F, encoding="utf-8")).get("notices") or []
    except (OSError, ValueError):
        return []


def publish(notices):
    """notices.json and its signature, written next to the releases (the site's deploy sends them)."""
    from tools.make_beta import release_key
    os.makedirs(DIR, exist_ok=True)
    raw = json.dumps({"v": 1, "at": int(time.time()), "notices": notices}, ensure_ascii=False, indent=1).encode()
    open(F, "wb").write(raw)
    open(F + ".sig", "w").write(base64.b64encode(release_key().sign(raw)).decode())
    return F


def add(nid, texts, level="info", link=None, before_build=None, platform=None, days=30):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", nid):
        raise ValueError("an id: lowercase letters, digits and dashes, 40 at most")
    texts = {k: v.strip() for k, v in texts.items() if v and v.strip()}
    if "en" not in texts:
        raise ValueError("an English text at least (--en): an app in a language without its text shows that one")
    bad = [k for k in texts if k not in i18n.LANGS]
    if bad or any(len(v) > 600 for v in texts.values()):
        raise ValueError(f"languages the app speaks ({', '.join(i18n.LANGS)}), 600 characters at most each")
    if level not in LEVELS:
        raise ValueError(f"level: {' or '.join(LEVELS)}")
    if link and not re.fullmatch(r"https://[^\s\"'<>]{4,300}", link):
        raise ValueError("a link: https only")
    if before_build and not re.fullmatch(r"\d{8}-\d{4}", before_build):
        raise ValueError("--before-build: YYYYMMDD-HHMM, like the builds")
    if platform not in (None, "windows", "linux"):
        raise ValueError("--platform: windows or linux")
    n = {"id": nid, "level": level, "text": texts, "at": int(time.time()), "until": int(time.time() + float(days) * 86400)}
    if link:
        n["link"] = link
    if before_build:
        n["before_build"] = before_build
    if platform:
        n["platform"] = platform
    notices = [x for x in load() if x.get("id") != nid] + [n]
    publish(notices)
    return n


def remove(nid):
    notices = load()
    left = [x for x in notices if x.get("id") != nid]
    if len(left) == len(notices):
        raise ValueError(f"no message {nid}")
    publish(left)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Messages to the players' apps (signed, published with the site).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a = sub.add_parser("add")
    a.add_argument("id")
    for lang in i18n.LANGS:
        a.add_argument(f"--{lang}")
    a.add_argument("--level", default="info", choices=LEVELS)
    a.add_argument("--link")
    a.add_argument("--before-build")
    a.add_argument("--platform", choices=("windows", "linux"))
    a.add_argument("--days", type=float, default=30)
    r = sub.add_parser("remove")
    r.add_argument("id")
    o = ap.parse_args()
    try:
        if o.cmd == "add":
            n = add(o.id, {lang: getattr(o, lang) for lang in i18n.LANGS}, o.level, o.link, o.before_build, o.platform, o.days)
            print(f"message {n['id']} published in {F}: deploy the site to send it (python website/deploy.py)")
        elif o.cmd == "remove":
            remove(o.id)
            print(f"message {o.id} removed: deploy the site to take it back")
        for x in load():
            left = (x["until"] - time.time()) / 86400
            print(f"- {x['id']} [{x['level']}] {left:.0f} d left"
                  + (f" · builds before {x['before_build']}" if x.get("before_build") else "")
                  + (f" · {x['platform']}" if x.get("platform") else "") + f" · {x['text']['en'][:80]}")
    except ValueError as e:
        sys.exit(f"notices: {e}")
