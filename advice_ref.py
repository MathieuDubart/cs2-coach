"""Enrich rule-based advice with reference-population benchmarks, drills and sources."""
LEET = ("Leetify, statistics glossary", "https://leetify.com/blog/leetify-stats-glossary/")
SOURCES = {
    "trade": [("CSGO-Guides, trading and refragging", "https://csgo-guides.com/gameplay/trading"),
              ("scope.gg, what is a trade kill", "https://blog.scope.gg/trade-kills-en/"),
              ("Boosteria, angles and crossfires", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires")],
    "nades": [LEET, ("CSNADES.gg, lineups per map", "https://csnades.gg/maps"), ("lineups.gg", "https://lineups.gg/")],
    "flash": [LEET, ("CSNADES.gg, popflashes per map", "https://csnades.gg/maps")],
    "flashmates": [LEET, ("CSNADES.gg, popflashes per map", "https://csnades.gg/maps")],
    "pistol": [("Steam guide, why and how to counter-strafe", "https://steamcommunity.com/sharedfiles/filedetails/?id=3099945585"), LEET],
    "spray": [LEET, ("Steam guide, counter-strafing and accuracy", "https://steamcommunity.com/sharedfiles/filedetails/?id=3099945585")],
    "hold": [("Boosteria, angles and crossfires", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
             ("CS2Hype, the rifler role", "https://cs2hype.com/roles/rifler")],
    "range": [("Boosteria, angles and crossfires", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires")],
    "hp": [("CSGO-Guides, trading and refragging", "https://csgo-guides.com/gameplay/trading")],
    "eco": [("CSGO-Guides, money management", "https://csgo-guides.com/gameplay/money-management"),
            ("Hard2Kill, economy guide", "https://hard2kill.gg/guides/cs2-economy-guide")],
    "xhair": [LEET],
    "early": [("CS2Hype, the entry fragger role", "https://cs2hype.com/roles/entry-fragger"), ("CSGO-Guides, trading and refragging", "https://csgo-guides.com/gameplay/trading")],
    "lastalive": [("Boosteria, angles and crossfires", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
                  ("CSGO-Guides, trading and refragging", "https://csgo-guides.com/gameplay/trading")],
    "open": [("CS2Hype, the entry fragger role", "https://cs2hype.com/roles/entry-fragger"), LEET],
}
DRILLS = {
    "trade": ["In matches, for 3 games: before every duel, say out loud who can trade you. If nobody, fall back.",
              "Team Deathmatch, 10 min: always stay within sight of a teammate."],
    "nades": ["40-second rule: at 1:15 on the clock on attack, all your grenades must be gone.",
              "Practice mode, 10 min per map: learn 1 smoke, 2 flashes and 1 molotov for your favorite position."],
    "flash": ["Practice mode (sv_cheats 1; sv_infinite_ammo 1): 20 popflashes on your 2 most played angles, the flash must pop above the wall."],
    "flashmates": ["Call every flash ('flash B') and throw it over or behind the wall, never in front of a teammate."],
    "pistol": ["Aim Botz, 5 min with the Glock or the USP: A-D strafe, stop, a single shot per target.",
               "Pistol-only Deathmatch, 5 min: no shots while moving."],
    "spray": ["Recoil Master, 5 min: the first 10 bullets of the AK and the M4, on a wall then on a bot.",
              "Deathmatch, 10 min: bursts of 3 to 5 bullets, strafe between each."],
    "hold": ["Pick 2 held angles per site on your maps, and play them waiting for info instead of going to get it.",
             "Jiggle-peek (fast A-D) to get info without committing."],
    "range": ["Prefer positions at the back of the site or on long angles. Avoid corners where the enemy arrives 3 m away."],
    "hp": ["Under 50 HP: call your HP, fall back one angle and leave the next duel to a healthy teammate."],
    "eco": ["During buy time: Tab, check the other 4 players' money, and call 'full', 'force' or 'eco' before buying.",
            "Drop a weapon as soon as you have more than $5,000 and a teammate has less than $2,500."],
    "xhair": ["Yprac Prefire (workshop), 10 min on your map: crosshair at head height on every angle.",
              "In matches: when you move, your crosshair follows the edge of the wall at head height."],
    "early": ["The first 20 seconds: take info and keep your position. No duel without a flash or a trade."],
    "lastalive": ["As soon as 2 teammates are dead, move closer to the nearest survivor instead of staying on your spot.",
                  "Alone against 3 or more with no urgent objective: save your weapon rather than going for the clutch."],
    "open": ["Leave the opening to your entry, or take it with a teammate's flash."],
}
# rule id -> metrics shown as benchmarks (first = main)
RULE_METRICS = {"trade": ["traded_pct", "last_alive_pct"], "nades": ["nades_unused_24", "flash_eff"],
                "hold": ["peek_win", "hold_win"], "flash": ["flash_duels_pct"], "hp": ["lowhp_win"],
                "range": ["close_win", "far_win"], "pistol": ["pistol_moving"], "spray": ["b9_hit", "b1_hit"],
                "eco": [], "early": ["early_death_pct"], "xhair": ["xhair"], "open": ["open_win"], "flashmates": ["flash_mates_rate"], "lastalive": ["last_alive_pct"]}
EXTRA = {  # rules only triggered by the reference population (bottom third)
    "xhair": ("Your crosshair is far from the head when the duel starts", "Crosshair at head height",
              ["Median offset between your crosshair and the enemy's head, 125 ms before your first shot."]),
    "open": ("You lose your opening duels", "No opening without a flash", ["Opening kills of the round, won or lost."]),
    "flashmates": ("Your flashes blind your team", "Flash for your team, not on it", ["Teammates blinded for more than a second per flash thrown."]),
    "early": ("Too many deaths early in the round", "No free duel before 20 s", ["Share of your deaths before 20 s into the round."]),
    "lastalive": ("You often end up alone against several enemies", "Regroup when your team falls",
                  ["Share of your deaths where you were the last one alive on your team."]),
}


def fmt(v, unit):
    if v is None:
        return "—"
    s = f"{v:.1f}" if abs(v) < 10 and unit != "%" else f"{v:.0f}"
    return s + ("%" if unit == "%" else unit)


def enrich(rules, bench):
    """Attach benchmarks / drills / sources; add population-only rules; re-score by percentile."""
    have = {r["id"] for r in rules}
    M = (bench or {}).get("metrics", {})
    for rid, (title, short, why) in EXTRA.items():
        m = RULE_METRICS[rid][0]
        b = M.get(m)
        if rid not in have and b and b["you"] is not None and b["percentile"] is not None and b["percentile"] <= 30:
            rules.append({"id": rid, "score": 12, "title": title, "short": short, "why": list(why), "do": []})
    for r in rules:
        rid = r["id"]
        r["sources"] = [{"label": a, "url": u} for a, u in SOURCES.get(rid, [])]
        r["drills"] = DRILLS.get(rid, [])
        bl = []
        for m in RULE_METRICS.get(rid, []):
            b = M.get(m)
            if not b or b["you"] is None:
                continue
            bl.append({"metric": m, "label": b["label"], "you": b["you"], "percentile": b["percentile"], "median": b["median"],
                       "good": b["good"], "same": b["same_rank_median"], "higher": b["higher_rank_median"], "unit": b["unit"],
                       "higher_better": b["higher_better"], "n": b["n"]})
        r["bench"] = bl
        if bl and bl[0]["percentile"] is not None:
            p = bl[0]["percentile"]
            r["score"] = round(r["score"] * 0.6 + (60 - p) * 0.5, 1)
            b0 = bl[0]
            target = b0["higher"] if b0["higher"] is not None else b0["good"]
            r["target"] = f"Target: {fmt(target, b0['unit'])} ({'level of higher-ranked players' if b0['higher'] is not None else 'top quarter of the base'})"
            r["standing"] = f"You {fmt(b0['you'], b0['unit'])} · median {fmt(b0['median'], b0['unit'])} · better than {p:.0f}% of players"
    return sorted(rules, key=lambda r: -r["score"])


def strengths_from_bench(bench, limit=4):
    out = []
    for m, b in (bench or {}).get("metrics", {}).items():
        if b["you"] is not None and b["percentile"] is not None and b["percentile"] >= 75:
            out.append((b["percentile"], f"{b['label'][0].upper() + b['label'][1:]}: {fmt(b['you'], b['unit'])} (better than {b['percentile']:.0f}% of players)"))
    return [t for _, t in sorted(out, reverse=True)[:limit]]
