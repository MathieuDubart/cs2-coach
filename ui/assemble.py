"""The app's page (app_template.html) is built from these parts: edit them, never the built page.
python ui/assemble.py writes app_template_next.html and runs the In game check on every map; when it is right:
copy it over app_template.html (the server reads it on each request, no restart).
- p0_head.html: the fonts; p0_base.css, p1_extra.css: the styles (the colors are tokens in :root, dark and light);
- p2_shell.html: the bar and the views' containers; p3..p8: the scripts, in that order (core, plan and settings,
  nav, in game, live panel, visual panel, economy, review, search and routing)."""
import os
import subprocess
import sys

UI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(UI)
PARTS_JS = ("p3_core.js", "p4_plan.js", "p5_nav.js", "p6_ingame.js", "p6b_live.js", "p6c_visual.js", "p6d_econ.js", "p7_review.js", "p8_tail.js")


def read(f):
    with open(os.path.join(UI, f), encoding="utf-8") as fh:
        return fh.read()


def build():
    head, css, extra, shell = read("p0_head.html"), read("p0_base.css"), read("p1_extra.css"), read("p2_shell.html")
    js = "".join(read(f) for f in PARTS_JS)
    return f"<title>CS2 Coach</title>\n{head}<style>{css}{extra}</style>\n\n{shell}\n<script>\n{js}</script>\n", js


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out, js = build()
    dest = os.path.join(ROOT, "app_template_next.html")
    with open(dest, "w", encoding="utf-8") as fh:   # Windows line ends, as the page always had
        fh.write(out)
    print("written", len(out), "chars")
    # the regression check of the In game page on every map (checks/check_maps.js): a failure is printed, never hidden
    r = subprocess.run(["node", os.path.join(ROOT, "checks", "check_maps.js"), dest], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    lines = (r.stdout or r.stderr or "check: no output").strip().splitlines()
    print(lines[0])
    for line in lines[1:]:
        if "FAIL" in line:
            print(line)
