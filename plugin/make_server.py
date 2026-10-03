"""A separate CS2 dedicated server for the coach's replays, next to the game, without touching it.

The game's files are hard-linked (no copy, no space; read-only for the server), except the ones a server could write:
the cfg folder and gameinfo.gi are real copies, console.log, logs and replays are left out. Metamod:Source and
CounterStrikeSharp go into the copy only (addons), and the copy's gameinfo.gi loads Metamod. The game itself never sees
any of it. Run again after a CS2 update: new files are linked, the rest stays. Then plugin/build.py puts the coach's
replay plugin in it."""
import os
import re
import shutil
import sys
import zipfile

SRC = os.environ.get("COACH_CS2", r"E:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive")
DST = os.environ.get("COACH_CS2SERVER", r"E:\CS2Server")
HERE = os.environ.get("COACH_SERVER_ZIPS", r"E:\dev	ools")   # mmsource.zip (Metamod:Source 2.0) and css-runtime.zip (CounterStrikeSharp with runtime)
SKIP_DIRS = {os.path.normcase(os.path.join("game", "csgo", d)) for d in ("replays", "logs", "addons", "demoheaders")}
COPY_DIRS = {os.path.normcase(os.path.join("game", "csgo", "cfg"))}
COPY_FILES = {os.path.normcase(os.path.join("game", "csgo", "gameinfo.gi"))}
SKIP_FILES = {os.path.normcase(os.path.join("game", "csgo", "console.log"))}


def main():
    linked = copied = 0
    for root, dirs, files in os.walk(SRC):
        rel = os.path.relpath(root, SRC)
        nrel = os.path.normcase(rel)
        if any(nrel == d or nrel.startswith(d + os.sep) for d in SKIP_DIRS):
            dirs[:] = []
            continue
        os.makedirs(os.path.join(DST, rel), exist_ok=True)
        copy_here = any(nrel == d or nrel.startswith(d + os.sep) for d in COPY_DIRS)
        for f in files:
            r = os.path.normcase(os.path.join(rel, f))
            if r in SKIP_FILES or f.lower().endswith((".log", ".dmp", ".mdmp")):
                continue
            s, d = os.path.join(root, f), os.path.join(DST, rel, f)
            if os.path.exists(d):
                continue
            if copy_here or r in COPY_FILES:
                shutil.copy2(s, d)
                copied += 1
            else:
                os.link(s, d)
                linked += 1
    csgo = os.path.join(DST, "game", "csgo")
    for z in ("mmsource.zip", "css-runtime.zip"):
        zipfile.ZipFile(os.path.join(HERE, z)).extractall(csgo)
    gi = os.path.join(csgo, "gameinfo.gi")
    t = open(gi, encoding="utf-8").read()
    if "csgo/addons/metamod" not in t:
        t = re.sub(r"(\n(\s*)Game\s+csgo\s*\n)", r"\n\2Game\tcsgo/addons/metamod\1", t, count=1)
        open(gi, "w", encoding="utf-8").write(t)
    print(f"linked {linked}, copied {copied}; metamod in gameinfo: {'csgo/addons/metamod' in open(gi, encoding='utf-8').read()}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
