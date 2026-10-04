"""What a pro analyst points at in one match, as raw counts with their base (saved in each match's stats.json; the
review adds them up over your session and says what stands out):
- repeek: the rounds where you died within 8 s of your first kill (of the rounds where you got a kill): after a
  kill the advantage is your team's, falling back to a trade spot keeps it;
- untraded: your deaths with no trade within 5 s and no damage of yours in the 3 s before (of your deaths);
- flash: the enemies your flashes blinded over 1.5 s that your team damaged while they were blind (of the enemies
  blinded that long; your teammates blinded don't count);
- spots: where you died, by place (the place you keep dying at is a habit the enemies can read).
Rewritten 04/10 from a first version (another tool, 03/10): it counted team flashes, called 10% of flashes used
"excellent" and a single round "predictable"; in French while the app is in English."""
from collections import Counter

DIE_AFTER_KILL_S = 8   # died this soon after your first kill
TRADE_S = 5            # a teammate kills your killer this soon: traded
IMPACT_S = 3           # your damage this long before your death: not without impact
BLIND_S = 1.5          # a flash that blinds longer than this is a real flash


def pro_insights(me, per_round, deaths, hurt, blind, foes_of, tickrate):
    """me: your SteamID64; per_round: the analysis' rounds ({"round": n, ...}); deaths, hurt, blind: the demo's
    events (steamids as ints, "round" set on deaths and hurt); foes_of: round -> the enemies' SteamIDs."""
    T = tickrate
    out = {"rounds": len(per_round)}
    kill_rounds, repeek = 0, []
    my_deaths, untraded = 0, []
    spots = Counter()
    for r in per_round:
        n = r["round"]
        foes = foes_of.get(n, set())
        rd = deaths[deaths["round"] == n].sort_values("tick")
        kills = rd[(rd.attacker_steamid == me) & (rd.user_steamid.isin(foes))]
        mine = rd[rd.user_steamid == me]
        if len(kills):
            kill_rounds += 1
            if len(mine) and 0 < mine.tick.iloc[0] - kills.tick.iloc[0] < DIE_AFTER_KILL_S * T:
                repeek.append(n)
        if not len(mine):
            continue
        d = mine.iloc[0]
        my_deaths += 1
        place = d.get("user_last_place_name")
        if isinstance(place, str) and place:
            spots[place] += 1
        killer = d.attacker_steamid
        traded = len(rd[(rd.user_steamid == killer) & (rd.tick > d.tick) & (rd.tick <= d.tick + TRADE_S * T)
                        & (rd.attacker_steamid != me) & ~rd.attacker_steamid.isin(foes)])
        impact = len(hurt[(hurt.attacker_steamid == me) & (hurt.tick <= d.tick) & (hurt.tick >= d.tick - IMPACT_S * T)
                          & (hurt.user_steamid.isin(foes))])
        if not traded and not impact:
            untraded.append(n)
    out["repeek"] = {"value": len(repeek), "of": kill_rounds, "rounds": repeek}
    out["untraded"] = {"value": len(untraded), "of": my_deaths, "rounds": untraded}
    out["spots"] = dict(spots.most_common())
    # flashes: the enemies blinded over 1.5 s, and the ones your team hurt while blind
    blinded, used = 0, 0
    if len(blind) and "round" in hurt:
        mb = blind[(blind.attacker_steamid == me) & (blind.blind_duration > BLIND_S)]
        for _, b in mb.iterrows():
            n = b.get("round")
            foes = foes_of.get(n, set()) if n == n else set()
            if b.user_steamid not in foes:
                continue   # a teammate, or yourself
            blinded += 1
            end = b.tick + b.blind_duration * T
            hit = hurt[(hurt.user_steamid == b.user_steamid) & (hurt.tick >= b.tick) & (hurt.tick <= end)
                       & ~hurt.attacker_steamid.isin(foes)]
            if len(hit):
                used += 1
    out["flash"] = {"value": used, "of": blinded}
    out["v"] = 2
    return out
