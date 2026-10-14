"""Enrich rule-based advice with reference-population benchmarks, drills and sources."""
from wily.core.i18n import N_, tr

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
    "trade": [N_("In matches, for 3 games: before every duel, say out loud who can trade you. If nobody, fall back."),
              N_("Team Deathmatch, 10 min: always stay within sight of a teammate.")],
    "nades": [N_("40-second rule: at 1:15 on the clock on attack, all your grenades must be gone."),
              N_("Practice mode, 10 min per map: learn 1 smoke, 2 flashes and 1 molotov for your favorite position.")],
    "flash": [N_("Practice mode (sv_cheats 1; sv_infinite_ammo 1): 20 popflashes on your 2 most played angles, the flash must pop above the wall.")],
    "flashmates": [N_("Call every flash ('flash B') and throw it over or behind the wall, never in front of a teammate.")],
    "pistol": [N_("Aim Botz, 5 min with the Glock or the USP: A-D strafe, stop, a single shot per target."),
               N_("Pistol-only Deathmatch, 5 min: no shots while moving.")],
    "spray": [N_("Recoil Master, 5 min: the first 10 bullets of the AK and the M4, on a wall then on a bot."),
              N_("Deathmatch, 10 min: bursts of 3 to 5 bullets, strafe between each.")],
    "hold": [N_("Pick 2 held angles per site on your maps, and play them waiting for info instead of going to get it."),
             N_("Jiggle-peek (fast A-D) to get info without committing.")],
    "range": [N_("Prefer positions at the back of the site or on long angles. Avoid corners where the enemy arrives 3 m away.")],
    "hp": [N_("Under 50 HP: call your HP, fall back one angle and leave the next duel to a healthy teammate.")],
    "eco": [N_("During buy time: Tab, check the other 4 players' money, and call 'full', 'force' or 'eco' before buying."),
            N_("Drop a weapon as soon as you have more than $5,000 and a teammate has less than $2,500.")],
    "xhair": [N_("Yprac Prefire (workshop), 10 min on your map: crosshair at head height on every angle."),
              N_("In matches: when you move, your crosshair follows the edge of the wall at head height.")],
    "early": [N_("The first 20 seconds: take info and keep your position. No duel without a flash or a trade.")],
    "lastalive": [N_("As soon as 2 teammates are dead, move closer to the nearest survivor instead of staying on your spot."),
                  N_("Alone against 3 or more with no urgent objective: save your weapon rather than going for the clutch.")],
    "open": [N_("Leave the opening to your entry, or take it with a teammate's flash.")],
}
# rule id -> metrics shown as benchmarks (first = main)
RULE_METRICS = {"trade": ["traded_pct", "last_alive_pct"], "nades": ["nades_unused_24", "flash_eff"],
                "hold": ["peek_win"], "flash": ["flash_duels_pct"], "hp": ["lowhp_win"],
                "range": ["close_win", "far_win"], "pistol": ["pistol_moving"], "spray": ["b9_hit", "b1_hit"],
                "eco": [], "early": ["early_death_pct"], "xhair": ["xhair"], "open": ["open_win"], "flashmates": ["flash_mates_rate"], "lastalive": ["last_alive_pct"]}
EXTRA = {  # rules only triggered by the reference population (bottom third)
    "xhair": (N_("Your crosshair is far from the head when the duel starts"), N_("Crosshair at head height"),
              [N_("Median offset between your crosshair and the enemy's head, 125 ms before your first shot.")]),
    "open": (N_("You lose your opening duels"), N_("No opening without a flash"), [N_("Opening kills of the round, won or lost.")]),
    "flashmates": (N_("Your flashes blind your team"), N_("Flash for your team, not on it"), [N_("Teammates blinded for more than a second per flash thrown.")]),
    "early": (N_("Too many deaths early in the round"), N_("No free duel before 20 s"), [N_("Share of your deaths before 20 s into the round.")]),
    "lastalive": (N_("You often end up alone against several enemies"), N_("Regroup when your team falls"),
                  [N_("Share of your deaths where you were the last one alive on your team.")]),
}


def fmt(v, unit):
    if v is None:
        return "—"
    s = f"{v:.1f}" if abs(v) < 10 and unit != "%" else f"{v:.0f}"
    return s + ("%" if unit == "%" else unit)


def _lever(b):
    """A rule is a problem when the player is clearly below the base, or when higher-ranked players do clearly
    better (a lever to rank up). At the base's level and level with the ranks above: not a problem, whatever the
    absolute number says (everyone at this level dies with grenades)."""
    p = b["percentile"]
    if p is None or p < 45:
        return True
    hi, you = b.get("higher"), b["you"]
    if hi is None or you is None:
        return False
    gap = (hi - you) if b["higher_better"] else (you - hi)
    return gap >= 0.10 * max(abs(hi), 1e-9)


def enrich(rules, bench):
    """Attach benchmarks / drills / sources; add population-only rules; re-score by percentile; drop the rules
    where the player is not behind (see _lever)."""
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
        if bl and not _lever(bl[0]):
            r["drop"] = True
            continue
        if bl and bl[0]["percentile"] is not None:
            p = bl[0]["percentile"]
            r["score"] = round(r["score"] * 0.6 + (60 - p) * 0.5, 1)
            b0 = bl[0]
            target = b0["higher"] if b0["higher"] is not None else b0["good"]
            r["target"] = (tr("Target: {v} (level of higher-ranked players)", v=fmt(target, b0['unit'])) if b0['higher'] is not None
                           else tr("Target: {v} (top quarter of the base)", v=fmt(target, b0['unit'])))
            r["standing"] = tr("You {v} · median {m} · better than {p}% of players", v=fmt(b0['you'], b0['unit']), m=fmt(b0['median'], b0['unit']), p=f"{p:.0f}")
    return sorted([r for r in rules if not r.pop("drop", False)], key=lambda r: -r["score"])


def strengths_from_bench(bench, limit=4):
    out = []
    for m, b in (bench or {}).get("metrics", {}).items():
        if b["you"] is not None and b["percentile"] is not None and b["percentile"] >= 75:
            lab = tr(b["label"])   # reference.py's labels are N_() sentences
            out.append((b["percentile"], tr("{what}: {v} (better than {p}% of players)", what=lab[0].upper() + lab[1:], v=fmt(b['you'], b['unit']), p=f"{b['percentile']:.0f}")))
    return [t for _, t in sorted(out, reverse=True)[:limit]]
