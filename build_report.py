"""Build the multi-match coaching page from out/matches/*/ and out/notes.json.

Usage: python build_report.py [output.html]
"""
import base64
import io
import json
import os
import sys

from PIL import Image

import mapdata
from map_analysis import humanize

HERE = os.path.dirname(os.path.abspath(__file__))
MATCHES = os.path.join(HERE, "out", "matches")
TEMPLATE = os.path.join(HERE, "report_template.html")
NOTES = os.path.join(HERE, "out", "notes.json")


def radar_uri(path):
    im = Image.open(path).convert("RGBA")
    if im.size[0] != 1024:
        im = im.resize((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def _names(mp):
    """Re-derive display names from raw callout keys (older runs used a cruder formatter)."""
    if mp.get("zone_mode") == "callouts":
        for z in mp["zones"]:
            z["name"] = humanize(z["key"])
    return True


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def summary(st):
    """Key per-match metrics for the trend table."""
    o, aim, ut = st["overview"], st["aim"], st["utility"]
    rifles = [w for w in aim["by_weapon"].values() if w["class"] == "rifle"]
    pistols = [w for w in aim["by_weapon"].values() if w["class"] == "pistol"]

    def wavg(ws, key):
        tot = sum(w["shots"] for w in ws if w.get(key) is not None)
        return round(sum(w[key] * w["shots"] for w in ws if w.get(key) is not None) / tot, 1) if tot else None

    sp = aim["spray_rifles"].get("bullet_1", {})
    xh = aim.get("crosshair_placement") or {}
    tr = o["trades"]
    return {
        "kd": o["kd"], "adr": o["adr"], "hs": o["hs_kill_pct"], "kast": o["kast_pct"],
        "kills": o["kills"], "deaths": o["deaths"], "assists": o["assists"],
        "traded_pct": pct(tr["my_deaths_traded"], tr["my_deaths"]),
        "open_won": o["opening_duels"]["won"], "open_lost": o["opening_duels"]["lost"],
        "nades_unused": ut["grenades_unused_at_death"], "flash_enemies": ut["enemies_flashed_1s+"],
        "flash_mates": ut["teammates_flashed_1s+"], "util_dmg": ut["utility_damage"],
        "first_bullet": sp.get("hit_pct"), "rifle_moving": wavg(rifles, "shots_while_moving_pct"),
        "pistol_moving": wavg(pistols, "shots_while_moving_pct"),
        "xhair": xh.get("median_error_deg"),
        "buy_mismatch": sum(1 for f in st["economy_flags"] if f["issue"] == "buy_mismatch"),
        "clutches": len(o["clutches"]), "clutches_won": sum(1 for c in o["clutches"] if c["won"]),
        "last_alive_deaths": sum(1 for d in st["deaths"] if d["mates_alive_before"] == 0),
        "early_deaths": st["death_timing"]["deaths_first_20s"],
    }


def main(out_path):
    notes = json.load(open(NOTES, encoding="utf-8")) if os.path.exists(NOTES) else {}
    matches, radars, viewboxes = [], {}, {}
    for mid in os.listdir(MATCHES):
        f = os.path.join(MATCHES, mid)
        if not os.path.exists(os.path.join(f, "stats.json")):
            continue
        st = json.load(open(os.path.join(f, "stats.json"), encoding="utf-8"))
        mp = json.load(open(os.path.join(f, "map.json"), encoding="utf-8"))
        if st.get("error"):
            continue
        cfg = mapdata.get(st["map"])
        boxes = [Image.open(lv["image_path"]).convert("RGBA").resize((1024, 1024)).getbbox() for lv in cfg["levels"]
                 if lv.get("image_path") and os.path.exists(lv["image_path"])]
        if boxes:
            x0, y0 = min(b[0] for b in boxes) - 16, min(b[1] for b in boxes) - 16
            x1, y1 = max(b[2] for b in boxes) + 16, max(b[3] for b in boxes) + 16
            viewboxes[st["map"]] = [max(x0, 0), max(y0, 0), min(x1, 1024) - max(x0, 0), min(y1, 1024) - max(y0, 0)]
        for lv in cfg["levels"]:
            key = f"{st['map']}:{lv['key']}"
            if key not in radars and lv.get("image_path") and os.path.exists(lv["image_path"]):
                radars[key] = radar_uri(lv["image_path"])
        hostage = st["map"].startswith("cs_")
        matches.append({
            "id": mid, "time": st["match"]["time"], "map": st["map"], "mode": st["mode"],
            "hostage": hostage, "score": st["final_score"], "result": st["result"],
            "rounds": st["rounds"], "sum": summary(st),
            "per_round": [{k: r[k] for k in ("round", "side", "won", "kills", "deaths", "my_buy", "team_buy")} for r in st["per_round"]],
            "map_data": _names(mp) and {k: mp[k] for k in ("zones", "general", "me", "my_deaths", "my_kills", "heat", "levels", "zone_mode")}
                        | {"openings": [k for k in mp["all_kills"] if k["opening"]]},
            "notes": notes.get("matches", {}).get(mid),
        })
    matches.sort(key=lambda m: m["time"], reverse=True)
    data = {"matches": matches, "radars": radars, "viewboxes": viewboxes, "overall": notes.get("overall"),
            "player": "Patro ✌"}
    html = open(TEMPLATE, encoding="utf-8").read().replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    open(out_path, "w", encoding="utf-8").write(html)
    print(out_path, len(html) // 1024, "KB,", len(matches), "matchs")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "coach.html"))
