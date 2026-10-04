"""Sourced coaching knowledge: routines (before / during / after the round and the game, outside the game),
mid-round playbook (if this, then that), party size, level, role, weapons and the current state of the game.

Every entry cites where it comes from (guides, pro videos, studies, patch notes). The coach engine (plan.py)
picks what applies to a player from his own numbers. Researched in September 2026.
"""
UPDATED = "2026-09-30"

SRC = {
    # guides
    "boosteria_ct": ("Boosteria, holding a site as CT: setups and rotations (2026)", "https://boosteria.org/guides/hold-sites-ct-cs2-setups-rotations-2026"),
    "cs2hype_rot": ("CS2Hype, rotations: when and how to rotate", "https://cs2hype.com/guides/dynamic-map-rotations-when-and-how-to-rotate-in-cs2"),
    "boosteria_retake": ("Boosteria, retake guide (2026)", "https://boosteria.org/guides/cs2-retake-guide-2026-site-retake-strategy-teamplay"),
    "refrag_retake": ("Refrag, 5 tips for retakes", "https://refrag.gg/blog/reclaim-control-5-tips-to-improve-your-retakes-in-cs2/"),
    "scope_adv": ("scope.gg, converting a man advantage", "https://blog.scope.gg/realizing-the-advantage-en/"),
    "t_fund": ("Boosteria, fondamentaux T (2026)", "https://boosteria.org/guides/cs2-t-side-fundamentals-guide-2026-takes-fakes-executes"),
    "positioning": ("Boosteria, positioning: angles and crossfires", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
    "refrag_roles": ("Refrag, roles in CS2", "https://refrag.gg/blog/cs2-team-roles-explained/"),
    "lurk_blast": ("BLAST.tv, playing lurker", "https://blast.tv/article/cs2-lurker-guide"),
    "lurk_bo3": ("bo3.gg, the lurker guide", "https://bo3.gg/articles/lurker-position-guide-in-cs2"),
    "csgonews_solo": ("CSGO-News, winning in Premier solo queue", "https://csgo-news.com/en/guides/how-to-play-solo-queue-in-premier-and-win/"),
    "steam_solo": ("Steam guide, getting out of solo queue hell", "https://steamcommunity.com/sharedfiles/filedetails/?id=3664156230"),
    "rank_tiers": ("CS2 Central, ranking up in Premier (2026)", "https://cs2central.gg/blog/cs2-premier-rank-up-guide/"),
    "sw_economy": ("Switchblade Gaming, 2026 economy: thresholds and loss bonus", "https://www.switchbladegaming.com/cs2/economy-guide/"),
    "h2k_economy": ("Hard2Kill, economy guide", "https://hard2kill.gg/guides/cs2-economy-guide"),
    "demo_review": ("CS2Hype, reviewing your demos step by step", "https://cs2hype.com/guides/how-to-analyze-and-learn-from-your-cs2-demos-a-step-by-step-guide"),
    "boosteria_demo": ("Boosteria, what pros look at in demos", "https://boosteria.org/guides/cs2-demo-review-guide-pros-look-improve-fast"),
    "workshop_maps": ("CS2.eu, workshop warm-up maps (2026)", "https://cs2.eu/news/cs2-warm-up-maps-the-best-workshop-maps-for-practice-in-2026"),
    "sound": ("bo3.gg, sound in CS2", "https://bo3.gg/articles/sound-mechanics-in-cs2-footsteps-utility-and-audio-cues"),
    "boosteria_audio": ("Boosteria, guide audio (2026)", "https://boosteria.org/guides/cs2-audio-awareness-guide-2026-sound-cues-win-rounds"),
    "smg": ("CS.MONEY, playing the MP9", "https://cs.money/blog/games/weapons-guide-mp9/"),
    "leetify_glossary": ("Leetify, statistics glossary", "https://leetify.com/blog/leetify-stats-glossary/"),
    "clutch_prosettings": ("ProSettings, 10 clutch tips: create as many 1v1s as you can (2025)", "https://prosettings.net/blog/cs2-clutch-tips/"),
    "refrag_clutch": ("Refrag, 5 ways to improve your clutch play", "https://refrag.gg/blog/5-ways-to-improve-your-clutch-play-in-cs2"),
    "refrag_repeek": ("Refrag, AWP tips: re-peeking the same angle", "https://refrag.gg/blog/cs2-awp-tips"),
    "scope_trade": ("scope.gg, trade kills and spacing", "https://blog.scope.gg/trade-kills-en/"),
    "bo3_popflash": ("bo3.gg, pop flash setups: the flash timed with the peek", "https://bo3.gg/news/cs2-pop-flash-setups-strategies-for-self-blind-executes"),
    # patch notes and state of the game
    "rush_hour": ("Dust2.us, September 22, 2026 update (Rush Hour)", "https://www.dust2.us/news/78121/breaking-cs2-september-22nd-update-brings-silent-reloads-new-gamemode-changes-to-premier-in-rush-hour-patch"),
    "reload_update": ("CS2 Central, magazine-based reloads (March 2026)", "https://cs2central.gg/blog/cs2-reload-update-explained/"),
    "april_update": ("Swap.gg, April 2026 update", "https://swap.gg/blog/cs2-april-2026-update"),
    "map_pool": ("ProSettings, CS2 map pool (July 2026)", "https://prosettings.net/blog/cs2-maps/"),
    "party4": ("Esports Kingdom, groups of 4 in Premier", "https://esportskingdom.gg/counter-strike/cs2s-latest-update-allows-groups-of-four-to-play-premier-mode/"),
    # studies
    "sleep_cs": ("Study: sleep of 27 Counter-Strike players and performance (Frontiers, 2021)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8794592/"),
    "caffeine": ("Study: caffeine and FPS shooting, 24 players (Frontiers, 2024)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11270538/"),
    "mood_games": ("Study: mood and fatigue over 3 consecutive games (PMC, 2023)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10728599/"),
    "streaks": ("Study: win and loss streaks over 597,680 matches (CHI PLAY, 2024)", "https://dl.acm.org/doi/abs/10.1145/3665463.3678787"),
    "breathing": ("Study: 5 min of cyclic sighing per day (Cell Reports Medicine, 2023)", "https://www.cell.com/cell-reports-medecine/fulltext/S2666-3791(22)00474-8"),
    "attention": ("Review: circadian rhythms of attention (PMC, 2019)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6430172/"),
    "exercise": ("Study: 8 weeks of exercise in esports players (Frontiers, 2024)", "https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1504205/full"),
    "bef_health": ("British Esports, staying fit", "https://britishesports.org/the-hub/health-and-wellbeing/staying-healthy-in-esports/"),
    "aoa_eyes": ("American Optometric Association, video games and eye strain", "https://www.aoa.org/healthy-eyes/caring-for-your-eyes/gaming-and-digital-eye-strain"),
    "rating": ("flashed.gg, HLTV 2.0 rating rebuilt", "https://flashed.gg/posts/reverse-engineering-hltv-rating/"),
    # videos
    "yt_ropz_lurk": ("Video: Be like ropz, lurk like a pro", "https://www.youtube.com/watch?v=OslKO06LpwI"),
    "yt_hunter_lurk": ("Video: How To Lurk In CS2 ft. G2 huNter", "https://www.youtube.com/watch?v=SrnhpgR0UtI"),
    "yt_tyloo_lurk": ("Video: lurking on Inferno (TYLOO Academy)", "https://www.youtube.com/watch?v=tRxzBc-JySg"),
    "yt_ct_setups": ("Video: Best CT Setups on Every Map", "https://www.youtube.com/watch?v=bCbg3hjSr80"),
    "yt_nuke_outside": ("Video: Nuke Outside as CT with dev1ce (Astralis Academy)", "https://www.youtube.com/watch?v=0Q4nVKtXmRM"),
    "yt_anubis_awp": ("Video: the AWP on Anubis as CT", "https://www.youtube.com/watch?v=vPTHUtkDuuo"),
    "yt_anubis_ct": ("Video: every CT position on Anubis", "https://www.youtube.com/watch?v=_HzOy7MBagk"),
    "yt_mirage_ct": ("Video: every CT position on Mirage", "https://www.youtube.com/watch?v=b65hyOMbi0g"),
    "yt_cache_ct": ("Video: winning the CT side of Cache", "https://www.youtube.com/watch?v=yZBtbDSBQkM"),
    "yt_nuke_high": ("Video: How to Play Nuke at a High Level", "https://www.youtube.com/watch?v=TqaOW5as6q4"),
    "yt_solo": ("Video: How to Solo Queue Correctly in CS2", "https://www.youtube.com/watch?v=mbnEq-QStug"),
    "yt_solo_concepts": ("Video: 4 Solo Queue Concepts You Don't Know", "https://www.youtube.com/watch?v=D8mU4mipv1A"),
    "yt_no5stack": ("Video: You Don't Need a 5 Stack to Rank Up", "https://www.youtube.com/watch?v=c4HqtNTmWkc"),
    "yt_warmup_ropz": ("Video: ropz's warm-up", "https://www.youtube.com/watch?v=TmEwsVodlhc"),
    "yt_warmup_pros": ("Video: How the PROS warmup (2026)", "https://www.youtube.com/watch?v=VTuokRukVoc"),
    "yt_awp": ("Video: How to AWP, passive or aggressive", "https://m.youtube.com/watch?v=lannGAJbszI"),
    "yt_positioning": ("Video: The GREATEST CS2 Positioning Guide (2026)", "https://www.youtube.com/watch?v=RrGFGUIzCt0"),
    "yt_workshop": ("Video: BEST Workshop Maps to FIX Your Aim (2026)", "https://www.youtube.com/watch?v=8aC976zFzIM"),
    "yt_t_advantage": ("Video: using a man advantage as T", "https://www.youtube.com/watch?v=6b1MfRjStLQ"),
}


def src(*keys):
    return [{"label": SRC[k][0], "url": SRC[k][1]} for k in keys if k in SRC]


# ---------- state of the game (September 2026) ----------
META = [
    {"date": "Sep 22, 2026", "title": "Silent reload and silent unscope",
     "text": "Holding R reloads without noise, but more slowly. Unscoping a sniper no longer makes noise.",
     "impact": "Lurking and clutching: reload by holding R when an enemy is within earshot. AWP: you can leave an angle without giving yourself away.",
     "src": ["rush_hour"]},
    {"date": "Sep 22, 2026", "title": "Premier: new map selection",
     "text": "No more bans: team 1 picks one map, team 2 picks two, team 1 a last one, then one of the four is drawn at random.",
     "impact": "You need to be ready on 4 maps. Pick your best maps and prepare at least a CT sheet and a T sheet for each.",
     "src": ["rush_hour"]},
    {"date": "Sep 22, 2026", "title": "New 3v3 Rush mode",
     "text": "Fast 3v3 mode on random arenas, with a tower to control.",
     "impact": "A good warm-up mode for duels and 2-3 player play. It does not replace working on your map pool.",
     "src": ["rush_hour"]},
    {"date": "Summer 2026", "title": "Cache is back, Overpass leaves the pool",
     "text": "Active Duty and Premier pool: Ancient, Anubis, Cache, Dust2, Inferno, Mirage, Nuke.",
     "impact": "If you play Premier, Cache is now a map to prepare.",
     "src": ["map_pool", "yt_cache_ct"]},
    {"date": "April 2026", "title": "M4A1-S stronger at range, cheaper SMGs",
     "text": "The M4A1-S deals more damage at range. MP9 at $1,150 and MAC-10 at $950.",
     "impact": "SMG force buys are cheaper: compare with your force-buy numbers.",
     "src": ["april_update"]},
    {"date": "Mar 18, 2026", "title": "Magazine-based reload: remaining bullets are lost",
     "text": "Reloading throws away the current magazine. AWP: 15 bullets per round (5 + 2 magazines). M4A4: 150 bullets, M4A1-S: 80, Galil: 175, AK: 120.",
     "impact": "Stop reloading by reflex after 3 bullets: reload when almost empty, behind cover, or pick up a weapon. With the AWP, every shot counts.",
     "src": ["reload_update"]},
]

# ---------- routine by phase ----------
PHASES = [
    {"key": "hors_jeu", "title": "Outside the game", "items": [
        {"id": "sleep", "title": "Regular sleep hours",
         "text": "Among 27 Counter-Strike players followed for 56 days, the best ones slept longer and had more deep sleep. Sleep efficiency was low for almost all of them (67.7% on average).",
         "do": ["Go to bed and get up at fixed times, weekends included.", "Fill in the pre-session journal: the coach measures how your nights affect your games."],
         "src": ["sleep_cs"], "tags": ["all"]},
        {"id": "caffeine", "title": "Caffeine: small dose, 1 h before",
         "text": "A study of 24 FPS players: 1 to 3 mg per kg, taken 60 min before, improve shooting and reaction time (about 17 ms). 1 mg/kg (one espresso for 70 kg) does almost as well as 3 mg/kg.",
         "do": ["If you take some: one coffee about 1 h before the session, not a liter of energy drink.", "No caffeine after your last session of the day."],
         "src": ["caffeine"], "tags": ["all"]},
        {"id": "sport", "title": "Exercise for well-being",
         "text": "8 weeks of exercise improved coordination, grip strength and well-being in esports players, with no direct short-term gain on in-game tests.",
         "do": ["2 to 3 sessions of 40 min per week. Expect energy and mood from it, not extra headshots."],
         "src": ["exercise", "bef_health"], "tags": ["all"]},
        {"id": "eyes", "title": "Eyes and posture",
         "text": "In game, you blink much less. 20-20-20 rule: every 20 min, look 20 feet (6 m) away for 20 s. Stand up and stretch at least once an hour.",
         "do": ["Screen at eye level, feet flat, arms relaxed.", "A glass of water at every break between two games."],
         "src": ["aoa_eyes", "bef_health"], "tags": ["all"]},
        {"id": "weekly_review", "title": "One demo session per week",
         "text": "Watch a match at 2x from your view, note the rounds where you die first, then rewatch them at normal speed. Keep 2-3 mistakes for the week.",
         "do": ["Use the 2D replay in the Matches tab for your isolated deaths.", "Turn every recurring mistake into an experiment in the Progress tab."],
         "src": ["demo_review", "boosteria_demo"], "tags": ["all"]},
    ]},
    {"key": "avant_session", "title": "Before the session", "items": [
        {"id": "checkin", "title": "20-second journal",
         "text": "Hours of sleep, energy, mood, warm-up. After a few weeks, the coach tells you which days you play well and why.",
         "do": ["Fill in the form at the top of this tab before your first game."], "src": ["sleep_cs"], "tags": ["all"]},
        {"id": "warmup", "title": "15-minute warm-up",
         "text": "Pros warm up with workshop maps: Aim Botz for precision, Aim Rush for reflexes, Recoil Master for spraying, a prefire map for crosshair placement.",
         "do": ["Your personal routine is in the Progress tab.", "Finish with 5 min of Deathmatch with your role's weapon."],
         "src": ["workshop_maps", "yt_warmup_ropz", "yt_warmup_pros", "yt_workshop"], "tags": ["all"]},
        {"id": "one_goal", "title": "One single goal for the session",
         "text": "Go into each match with one task you can keep even if the game starts badly, instead of trying to carry the lobby.",
         "do": ["Take rule 1 of 'Always, on every map' and play the whole session with it."],
         "src": ["csgonews_solo", "yt_solo_concepts"], "tags": ["all"]},
        {"id": "maps4", "title": "Prepare your 4 Premier maps",
         "text": "Since September 22, 4 maps are picked and then one is drawn at random: you need a plan on each.",
         "do": ["Pick the maps where your record is best (In game tab).", "Reread the sheet of the drawn map while it loads."],
         "src": ["rush_hour"], "tags": ["premier"]},
    ]},
    {"key": "avant_round", "title": "Before each round (buy time)", "items": [
        {"id": "buy_team", "title": "We buy together",
         "text": "A full buy (rifle, kevlar, helmet) costs $3,700 as T and $3,900 as CT, plus your grenades. Loss bonus: $1,400, $1,900, $2,400, $2,900 then $3,400. A win moves the counter back down one step.",
         "do": ["Tab: check the other 4 players' money before buying.", "Force only if your money, minus the buy, plus the loss bonus, still pays a full buy next round ($3,700 as T, $3,900 as CT).", "Drop a weapon as soon as you have more than $5,000 and a teammate cannot buy."],
         "src": ["sw_economy", "h2k_economy"], "tags": ["all"]},
        {"id": "one_job", "title": "A precise role for the round",
         "text": "Who takes info, who trades, who throws which grenade. One grenade = one job (delay, take control, stop the plant).",
         "do": ["Call your position and your first grenade in one sentence."],
         "src": ["boosteria_ct", "t_fund"], "tags": ["all"]},
    ]},
    {"key": "pendant_round", "title": "During the round", "items": [
        {"id": "trade_spacing", "title": "Trade distance",
         "text": "Close enough to trade, far enough not to die to the same spray. Two players on the same line give a double kill.",
         "do": ["Before every duel: who can avenge me within 2 seconds?", "Complementary angles: one takes the contact, the other punishes whoever killed them."],
         "src": ["positioning", "boosteria_retake"], "tags": ["all"]},
        {"id": "info_calls", "title": "One call = where, how many, what kind of pressure",
         "text": "'Two B, one lurking, utility coming, not full yet' beats 'they're all B!' after you die.",
         "do": ["Call before you die, not after.", "Dead: still give the useful info, without ordering the living around."],
         "src": ["boosteria_ct", "csgonews_solo", "steam_solo"], "tags": ["all"]},
        {"id": "reload", "title": "Reloading in 2026",
         "text": "Reloading throws away the current magazine. Reload with few bullets left, behind cover. Pick up a dead teammate's weapon. Near an enemy, hold R to reload silently.",
         "do": ["Never reload by reflex after a kill in the middle of an open area."],
         "src": ["reload_update", "rush_hour"], "tags": ["all"]},
        {"id": "sound_disc", "title": "Sound discipline",
         "text": "Running can be heard at about 1,100 units (≈ 28 m). Walking (Shift) is silent. A jump can be heard from far away.",
         "do": ["Shift as soon as you are alone near enemies, when lurking and in clutches.", "Listen before you move: sound tells you who stays and who leaves."],
         "src": ["sound", "boosteria_audio"], "tags": ["all"]},
    ]},
    {"key": "apres_round", "title": "After each round", "items": [
        {"id": "why_died", "title": "5-second review",
         "text": "Why did I die? Could I be traded? If you die 3 times to the same angle, it's no longer aim: change position or ask for a flash.",
         "do": ["One sentence in your head, then on to the next round."],
         "src": ["csgonews_solo"], "tags": ["all"]},
        {"id": "breath", "title": "Reset breathing",
         "text": "Cyclic sighing (double inhale, long exhale) reduced stress better than meditation in a 2023 study.",
         "do": ["While the round loads: 2 cycles, long exhale.", "After a big mistake: one breath, then one useful piece of info for your team."],
         "src": ["breathing"], "tags": ["all"]},
    ]},
    {"key": "apres_game", "title": "After the game", "items": [
        {"id": "break_after_loss", "title": "Take a break after a loss",
         "text": "Across 597,680 matches of top-3% Korean players (League of Legends), loss streaks came with lower performance, and players who took a longer break after a loss did better. Fatigue builds up after every game, win or loss.",
         "do": ["10 to 15 min of break after a loss, 30 min after two.", "Your own numbers (Routine tab, context) tell you from which game you start dropping."],
         "src": ["streaks", "mood_games"], "tags": ["all"]},
        {"id": "one_lesson", "title": "One lesson, not ten",
         "text": "After a loss, find the main reason instead of changing everything. After a win, note what worked.",
         "do": ["Write it in the journal. If it comes back 3 times: start an experiment."],
         "src": ["csgonews_solo"], "tags": ["all"]},
    ]},
]

# ---------- mid-round playbook ----------
# the pro analyst's reads (each match, the review, Full analysis): what is measured, the fix, the sources (04/10)
READS = [
    {"id": "repeek", "title": "Re-peek after a kill", "what": "rounds with a kill where you die within 8 s of it",
     "fix": "After a kill the numbers are on your side: fall back to a spot a teammate can trade from, or come back from another angle.",
     "src": ["scope_adv", "refrag_repeek"]},
    {"id": "untraded", "title": "Deaths without impact", "what": "deaths not traded within 5 s, with no damage of yours in the 3 s before",
     "fix": "Take your duels where a teammate can trade you (one step behind or beside you), or after utility.",
     "src": ["scope_trade", "positioning"]},
    {"id": "flash", "title": "Flashes your team uses", "what": "enemies you blind over 1.5 s that your team hits while they are blind",
     "fix": "Call it before throwing (\"flashing B\") so a teammate swings as it pops, or flash for your own peek.",
     "src": ["bo3_popflash"], "higher_better": True},
    {"id": "fake", "title": "Pulled by a fake", "what": "hits on your site after you had left it for the other side",
     "fix": "One noise or one grenade on the other site is how a fake works: wait for a second piece of info (a body, the bomb, 3 players) before leaving, or only go halfway.",
     "src": ["boosteria_ct", "cs2hype_rot", "t_fund"]},
    {"id": "clutch", "title": "Several enemies at once in clutches", "what": "1v2+ clutches where 2 enemies or more see you as you are hit",
     "fix": "Make it a series of 1v1s: play an angle only one enemy can see, let them split, take them one by one.",
     "src": ["clutch_prosettings", "refrag_clutch"]},
]


def reads_meta():
    return {r["id"]: {**{k: v for k, v in r.items() if k != "src"}, "src": src(*r["src"])} for r in READS}


PLAYBOOK = [
    # CT
    {"side": "CT", "if": "A single noise, a single smoke or a molotov on the other site", "then": "Don't rotate. Lean toward the connector ('leaning A') and wait for real info.",
     "why": "Ts fake with a single piece of utility to make you rotate.", "src": ["boosteria_ct", "cs2hype_rot"], "tags": ["rotation"]},
    {"side": "CT", "if": "Bomb seen, 3 players called, or 2 flashes + molotov + rifle sounds", "then": "Full rotation right away, through the route that keeps you covered, calling 'rotating'.",
     "why": "These are the signs of a real execute.", "src": ["boosteria_ct"], "tags": ["rotation"]},
    {"side": "CT", "if": "You rotate and your teammates already died on the site", "then": "Don't go in alone: stop at the entrance, wait for the others and set up a grouped retake.",
     "why": "The worst rotation mistake: arriving alone and too late.", "src": ["boosteria_ct", "boosteria_retake"], "tags": ["rotation", "retake"]},
    {"side": "CT", "if": "You are the anchor and it's coming at you", "then": "Priority: survive 10 seconds and call how many they are and which utility they throw. Fall back one angle rather than die first.",
     "why": "The anchor wins the round by holding until the rotations arrive.", "src": ["refrag_roles", "boosteria_ct"], "tags": ["anchor"]},
    {"side": "CT", "if": "During a rotation, a lurker may be behind you", "then": "One player stays on the flank route (anti-lurk). Check before leaving your site.",
     "why": "Rotations without an anti-lurk get cut from behind.", "src": ["boosteria_ct"], "tags": ["rotation"]},
    {"side": "CT", "if": "Bomb planted, 3 CTs or more, with utility", "then": "Retake: two entries, a synced flash, one player taps the bomb right away to force the Ts to show themselves.",
     "why": "A grouped retake beats a trickle retake.", "src": ["boosteria_retake", "refrag_retake"], "tags": ["retake"]},
    {"side": "CT", "if": "Bomb planted, alone against 3 or more, under 20 s or no kit", "then": "Save your weapon.",
     "why": "In MR12, keeping your weapon for the next round pays more than a retake lost in advance.", "src": ["refrag_retake", "boosteria_retake"], "tags": ["save"]},
    {"side": "CT", "if": "Your team is down 4v5", "then": "Play passive: one kill then fall back, regroup on a site or prepare the retake. No hero peek.",
     "why": "Losing the site AND another player is the worst scenario.", "src": ["scope_adv"], "tags": ["advantage"]},
    {"side": "CT", "if": "Your team is up 5v4", "then": "No more solo duels: crossfires, let the Ts come to you, the clock plays for you.",
     "why": "In matchmaking, only 60% of 5v4s are converted, against more than 75% among pros.", "src": ["scope_adv"], "tags": ["advantage"]},
    # T
    {"side": "T", "if": "You win the first duel (5v4)", "then": "Regroup and hit the weakened site with clean trades. No need for a fancy fake.",
     "why": "An advantage is converted through structure, not speed.", "src": ["t_fund", "yt_t_advantage", "scope_adv"], "tags": ["advantage"]},
    {"side": "T", "if": "You lose the first duel (4v5)", "then": "Slow down: take map control, look for a pick in pairs, hit late with utility.",
     "why": "Rushing 4v5 without info gives the round away.", "src": ["t_fund", "scope_adv"], "tags": ["advantage"]},
    {"side": "T", "if": "You are lurking while the team executes", "then": "Walk (Shift), listen to who rotates, and strike when the CTs leave your side: cut the rotation.",
     "why": "A lurk works when it lands at the moment the CTs commit elsewhere.", "src": ["lurk_blast", "lurk_bo3", "yt_ropz_lurk", "yt_hunter_lurk"], "tags": ["lurk"]},
    {"side": "T", "if": "You are lurking and nothing happens by 0:45", "then": "Join the execute or go to the empty site: a lurker who waits too long plays a 1v4 at the end.",
     "why": "A lurk without impact looks like baiting or a save.", "src": ["refrag_roles", "yt_tyloo_lurk"], "tags": ["lurk"]},
    {"side": "T", "if": "Bomb planted", "then": "Crossfires, play the clock and utility (molotov or smoke on the bomb). Don't look for the duel: make them come.",
     "why": "Time is your weapon after the plant.", "src": ["boosteria_retake"], "tags": ["postplant"]},
    {"side": "T", "if": "Under 20 s, no plant, alone against several", "then": "Save your weapon.",
     "why": "A saved rifle is worth more than an exit kill.", "src": ["h2k_economy"], "tags": ["save"]},
    # both
    {"side": "both", "if": "You just got a kill in a clutch", "then": "Don't re-peek the same angle right away: reposition, listen, isolate the next duel.",
     "why": "The kill gives you away: the enemy is waiting for that re-peek.", "src": ["csgonews_solo"], "tags": ["clutch"]},
    {"side": "both", "if": "You are hurt (under 50 HP)", "then": "Call your HP, fall back one angle and leave the next duel to a healthy teammate.",
     "why": "A duel taken hurt is lost more often than won.", "src": ["positioning"], "tags": ["duel"]},
    {"side": "both", "if": "You have the AWP and just fired", "then": "Change angle: unscoping is now silent. Keep your 15 bullets for real duels.",
     "why": "An AWPer who re-peeks the same angle gets punished.", "src": ["yt_awp", "rush_hour", "reload_update"], "tags": ["awp"]},
    {"side": "both", "if": "You are playing an SMG or a shotgun", "then": "Take short angles where the enemy shows up within 15 m. At range, your weapon loses its point.",
     "why": "SMG damage drops with distance, but a kill pays $600.", "src": ["smg"], "tags": ["smg"]},
]

# ---------- party size ----------
PARTY = {
    "solo": {"title": "Solo", "items": [
        "Be the player who never gives a free round: info, trade, save, grenades at the right time.",
        "Take a role that needs no coordination: anchor as CT, second player as T, and give info.",
        "Short, factual calls, never emotional. After you die, only the useful info.",
        "Expect to lose about 1 game out of 2: even very good players plateau around 55% solo.",
    ], "src": ["csgonews_solo", "steam_solo", "yt_solo", "yt_no5stack"]},
    "duo": {"title": "Duo", "items": [
        "Play as a trade pair: one takes the contact, the other punishes. Always on complementary angles.",
        "Synced utility: your flash for their entry, their smoke for your rotation.",
        "In Premier, agree on your maps before the pick phase.",
        "Watch one lost round together per session.",
    ], "src": ["positioning", "rush_hour"]},
    "trio": {"title": "Trio", "items": [
        "You form the core of the execute: entry, second, support. Give the other two a simple role (anchor, lurk).",
        "Speak first: solo players follow whoever gives a clear plan.",
    ], "src": ["refrag_roles", "steam_solo"]},
    "quatuor": {"title": "Four-stack", "items": [
        "The 5th player is immune to vote-kicks: include them instead of ignoring them.",
        "Give them a clear job from round 1 (B anchor, lurk…).",
    ], "src": ["party4"]},
    "five": {"title": "Five-stack", "items": [
        "Fixed roles: IGL, entry, support, lurker, AWPer. One default per map and one execute per site.",
        "As a five-stack in Premier, you mostly face other groups: matches are more structured.",
        "Review your team demos: the IGL looks for timing and spacing mistakes.",
    ], "src": ["refrag_roles", "steam_solo"]},
}

# ---------- level ----------
LEVELS = [
    {"key": "debut", "max": 10000, "name": "Under 10,000", "comp": (1, 10), "focus": [
        "Crosshair at head height on every angle.", "Counter-strafe: full stop before shooting.",
        "One single map, learned in depth.", "Economy: buy with the team."]},
    {"key": "inter", "max": 15000, "name": "10,000 to 15,000", "comp": (11, 13), "focus": [
        "Crosshair and trades above all.", "Map control and basic utility (1 smoke, 2 flashes per site).",
        "Play in pairs rather than alone."]},
    {"key": "confirme", "max": 20000, "name": "15,000 to 20,000", "comp": (14, 16), "focus": [
        "Master 2-3 maps: callouts, timings and lineups.", "Pistol rounds and conversion rounds: no impulse buys.",
        "Mid-round decisions: rotations, retakes, man advantage."]},
    {"key": "avance", "max": 25000, "name": "20,000 to 25,000", "comp": (17, 17), "focus": [
        "The 3 levers that unlock progress: utility, economy, spacing.", "One signature map mastered in depth."]},
    {"key": "elite", "max": 99999, "name": "25,000 and up", "comp": (18, 18), "focus": [
        "Stop after 2-3 losses in a row: the most profitable habit for your rating.", "Calls and coordination: players who communicate win more."]},
]
LEVEL_SRC = ["rank_tiers"]

# ---------- roles ----------
ROLE_TIPS = {
    "lurker": {"items": [
        "Your job: hold the space the team left, cut the rotation, be the last one alive with the info.",
        "Sound discipline: Shift when you are alone, silent reload near enemies.",
        "Strike when the CTs rotate, not before. Nothing by 0:45: join or take the empty site.",
        "Avoid dying alone before the execute: a lurker dead early is a free 4v5."],
        "src": ["lurk_blast", "lurk_bo3", "refrag_roles", "yt_ropz_lurk", "yt_hunter_lurk", "yt_tyloo_lurk"]},
    "entry": {"items": [
        "Your goal: take space on the site, not necessarily kills.", "Go in behind a flash, with a second player within trade distance.",
        "After you die: precise info for the second player."], "src": ["refrag_roles", "csgonews_solo"]},
    "trader": {"items": [
        "Stay within trade distance of your entry, never on the same line.", "Punish right away whoever just killed your teammate."],
        "src": ["refrag_roles", "positioning"]},
    "support": {"items": [
        "You throw most of the grenades: know the smokes of every execute.", "Flash for the others, never on them.",
        "Second into the fight: trade to lock in control."], "src": ["refrag_roles"]},
    "anchor": {"items": [
        "Survive 10 seconds: that's what wins rounds.", "Every angle, timing and hiding spot of your site should be a reflex.",
        "Accept giving up the site to prepare the retake."], "src": ["refrag_roles", "boosteria_ct"]},
    "closer": {"items": [
        "End of round: isolate duels, check the time and the bomb, walk.", "Don't re-peek after a kill: reposition.",
        "Save when the round is lost: your weapon is worth more than an exit kill."], "src": ["csgonews_solo", "h2k_economy"]},
    "awper": {"items": [
        "Passive or aggressive depending on the round, but never the same angle twice.", "15 bullets per round since March 2026: no spam shots.",
        "Silent unscope since September 22: leave an angle without giving yourself away."], "src": ["yt_awp", "reload_update", "rush_hour", "yt_anubis_awp"]},
}

# ---------- map video guides ----------
MAP_VIDEOS = {
    "de_anubis": ["yt_anubis_ct", "yt_anubis_awp"],
    "de_mirage": ["yt_mirage_ct"],
    "de_cache": ["yt_cache_ct"],
    "de_nuke": ["yt_nuke_outside", "yt_nuke_high"],
    "de_inferno": ["yt_tyloo_lurk"],
}

# ---------- training (workshop maps and drills) by weakness ----------
DRILLS = {
    "xhair": {"map": "Prefire map (workshop) of the day's map", "min": 5, "text": "Crosshair at head height on every angle, without shooting the floor.", "src": ["workshop_maps"]},
    "reaction": {"map": "Aim Rush", "min": 5, "text": "Reactive targets: the closest thing to a real duel for reaction time.", "src": ["workshop_maps", "yt_workshop"]},
    "pistol": {"map": "Aim Botz (pistol)", "min": 5, "text": "A-D, full stop, one shot: never while moving.", "src": ["workshop_maps"]},
    "spray": {"map": "Recoil Master", "min": 5, "text": "The first 10 bullets of the AK and the M4, then bursts of 3-5.", "src": ["workshop_maps"]},
    "precision": {"map": "Aim Botz", "min": 5, "text": "Still bots then strafing bots: first-shot accuracy.", "src": ["workshop_maps"]},
    "dm": {"map": "Deathmatch", "min": 5, "text": "With your role's weapon, aiming only at the head.", "src": ["csgonews_solo"]},
    "nades": {"map": "Practice mode (sv_cheats 1)", "min": 5, "text": "The key utility of your favorite position on the day's map (In game tab).", "src": ["csgonews_solo"]},
}
