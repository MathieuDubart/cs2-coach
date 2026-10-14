"""Build the CoachReplay plugin and put it in the training server's plugins folder (CounterStrikeSharp loads it at the
next map, or now with css_plugins load). Needs the .NET 10 SDK (tools/dotnet, or one on the PATH)."""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wily.training import replay  # noqa: E402

DOTNET = next((d for d in (os.path.join(os.path.dirname(os.path.dirname(HERE)), "..", "tools", "dotnet", "dotnet.exe"),
                           r"E:\dev\tools\dotnet\dotnet.exe") if os.path.exists(d)), "dotnet")


def main():
    proj = os.path.join(HERE, "CoachReplay")
    api = os.path.join(replay.CSGO, "addons", "counterstrikesharp", "api", "CounterStrikeSharp.API.dll")
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    r = subprocess.run([DOTNET, "build", "-c", "Release", "-o", os.path.join(proj, "bin", "out"), f"-p:CssApi={api}"],
                       cwd=proj, env=env, capture_output=True, text=True, creationflags=replay.NO_WINDOW)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-2000:])
        sys.exit(1)
    dst = os.path.join(replay.CSGO, "addons", "counterstrikesharp", "plugins", "CoachReplay")
    os.makedirs(dst, exist_ok=True)
    for f in ("CoachReplay.dll", "CoachReplay.pdb"):
        shutil.copy2(os.path.join(proj, "bin", "out", f), dst)
    print("deployed to", dst)


if __name__ == "__main__":
    main()
