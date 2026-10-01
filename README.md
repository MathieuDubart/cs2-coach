# CS2 Coach

Personal coach for Counter-Strike 2: it fetches your matchmaking demos automatically (no manual download), analyzes them in depth and builds a local app with precise, sourced advice you can apply right away.

## Two main uses

- **In game** (2nd screen): during a live match, the radar fills the screen ("Normal view" to go back, "Full screen" for the browser's full screen), the buy advice pops up over it as a notification during the freeze time, and the T read and grenades sit in a side panel. The sheet of the map you're playing, which follows your match on its own through CS2's Game State Integration (map, side, round, money, grenades in hand, round clock). A "Now" panel changes with the phase of the round:
  - **freeze time**: what to buy with your money and the kind of round (weapon, armor, grenades in order, where to play), and what that leaves you for the next round;
  - **during the round**: as CT, the **T read**: the odds of an A or B attack for this round, from the kind of round (pistol, round 2, eco, force, full), what this team did in the half (one click after each round: A, B or not clear), and what you see in the round: the clock running with no site taken yet, where the first contact happened and whether it was one T alone or several (a lone T is often a lurker: the others tend to be on the other side), the site where you saw them, and, without any click, what happens at your own spot (where you stood 15 s in, then a fight there or nothing yet by 20, 30, 40 s: a quiet B tilts toward A, measured on every CT of the base and checked on 340 of your CT rounds). A practice or custom server (more than $16,000, or a round longer than any real one) is recognized: no buy advice, no T read, no automatic recording there. The odds of a rush follow the shape of this team's last rounds (rush, execute, late hit: read from the plant time, or one click), since a team that rushes keeps rushing, above all after a rush that worked. Plus where to throw the grenades you hold, marked "now" at the right moment, and where each side dies at this moment of the round;
  - **bomb planted**: the plant spots of the site on the radar, the retake odds by players alive on each side, the retake or post-plant grenades.
  - **the live radar**: as CT, the odds of each entrance of the Ts (the main of each site, the way through mid) and of each play (rush, split, one entrance) for this round, updated by the clock and what you see; your spots (strong or weak, and the rounds with 2+ kills you got from each); the grenades worth throwing *now* from where you play: anti-rush only while a rush is still possible, blocking when the Ts usually push that entrance in the next seconds, only the ones you hold; after the plant, the rotation from where you are (your position, when CS2 sends it) with the time it takes and how often players die on the way, the retake grenades and the plant spots. Each layer can be hidden.
  Below, tabs: game plan (your strengths, what to avoid, reflexes, rotations), buys by round, grenades, T habits. "2nd screen mode" hides the top bar and enlarges the text.
- **Review** (cold, after the session or the next day): what changed against your previous matches and by how much, the possible reasons (times, session length, maps, group, experiments), your focus areas, what you're testing and what you could test. The full analysis (matches, maps, mid-round, progress, routine) is one click away.
- Also: **Team** (game plan for 2 to 5 players), **Explore** (any player, pros), **⚙ Settings** (Steam connection, game detection, microphone). On first launch, the home page offers to analyze your own profile.

**Your calls** (optional, Settings): the app records your microphone during your matches (only your voice; with a headset, your teammates' voices aren't picked up), transcribes it on this PC with Whisper (low priority, paused when a match starts), lines your calls up with the rounds and measures: info given before dying, "where + how many", grenades called, talking during a teammate's clutch, frustration. Results in the Review; files in `out/voice` (not versioned). Only record other people with their consent (in France, article 226-1 of the Code pénal).

Game detection is turned on in Settings: the app writes `gamestate_integration_coachcs2.cfg` in CS2's `cfg` folder (Valve's official feature, used by HUDs and RGB keyboards; during a match, CS2 only sends your own info). Restart CS2 after turning it on.

## What it analyzes

- **Economy**: buys, force-buys, saves, wasted money.
- **Utility**: grenades thrown, HE/molotov damage, effective flashes, lineups used from your positions.
- **Positioning**: strong and weak zones per map (callouts), duels won and lost per zone, positions to play more or to avoid.
- **Movement and aim**: reaction time, pre-aim, accuracy, counter-strafing, trades, re-peeks.
- **Archetype**: Entry, Lurker, AWPer, Support, Closer… from your weapons, movement, game sense and reactions, with **reference pros** who play the same spots or share your style.
- **Each match, round by round** (from the demo; a *Re-analyze this match* button extracts it again from its demo and updates the profile, plan and in-game sheet, for a match analyzed by an older version or interrupted): the play of the Ts (Split A: Long A + Short...), where they went and how fast, who died where and when (a T killed alone is flagged), the plant and the result, with a summary of how the Ts you faced played.
- **Coach notes per map and side**: what to change or keep in each zone, the grenade to throw before pushing, the position to try.
- **Where to play and what to buy by round** (pistol, eco, force, full, anti-eco), per map and side: your own rounds first, then players of your profile (same role), then the whole base, adjusted by your duels in each zone and with each weapon.
- **Grenades** from your positions, per map and side: where to throw each smoke, flash, HE and molotov (from which zone to which, how, position to copy for practice), when they work best and what they do in the base (enemies flashed, kills that follow, damage, rounds won).
- **T habits** per map: the plays (rush, split, one entrance) and the entrances of each site, learned from where the Ts of every push came from, the site hit by kind of round, the shape of the attacks (rush, fast push by 1-2 Ts, execute, late hit, a T lost alone before the attack), entries (through where, when), the first duel (one T alone or several), where the next attack goes after a won or lost one, what a team does after each kind of attack, how quiet rounds tilt the odds, plant spots, retakes by players alive, and where each side dies by moment of the round. An attack stopped before the site counts for the site it was going to (zones learned from the rounds where the Ts got in).
- **Mid-round**: rotations (time to leave, travel, route, deaths on the way), site holding, lurks, post-plant, retakes, man advantages thrown, saves, noise near enemies, compared with the base and pros; safest rotation routes and positions by weapon, per map; "if… then…" reflexes.
- **Routine**: before, during and after the round and the game, and outside the game (sleep, caffeine, breaks), by group (solo, duo, trio, 4-stack, 5-stack), with the latest game changes. Measured habits: times, game number in the session, loss streaks, partners, and the pre-session journal (sleep, energy, warm-up).
- **Progress**: priorities by level and experience, role tips, targeted warm-up, stats per weapon, match-by-match tracking, and **experiments** (a weapon, a position, a habit…) evaluated automatically over the next matches.
- **Team**: you + 1 to 4 analyzed teammates; extra players (random teammates) get the positions and roles left, numbered on the radar. The coach crosses their data (roles, their own strong spots and multi-kill rounds, known lineups, weapons, mid-round, matches played together) with the base and pros, per map (bomb maps only):
  - **CT setup**: where the Ts of the base attack from (each site's entrances with their share of the attacks and of rushes, red arrows on the radar), five positions each facing an entrance, the most attacked first. Each member takes the position that fits their profile and their own record on that site (their spot replaces the base's when it's clearly theirs), with the grenades that close that entrance (anti-rush early, blocking later) and the rotation once the bomb is down;
  - **T plays**: the base's best execute, split and rush on the map (T rounds won, with the map average), and only a split or a rush that pays. Who goes through which entrance (the lurker shows himself on the other site, or watches the flank of a rush) and who throws which grenade (with the `setpos` command);
  - **every play of the base** with the team's own record: the plays you ran as T, and the ones you faced as CT;
  - plus suggested IGL, maps to pick in Premier, shared vocabulary (FACEIT and pro callouts, grouped by area), calls, economy (AWP, drop order, everyone's force-buy weapon: cheap weapons only, 8 rounds minimum), synergies (who avenges whom), team goals and individual work.
- Zone names are the callouts used by pros and on FACEIT (Short, Upper Tunnels, Apps, Window, Donut, Popdog...), not the game's default place names (`callouts.py`, with its sources).
- Every piece of advice cites its sources: guides, pro videos, scientific studies, patch notes (see `knowledge.py`).
- Comparison with a reference population (random players + HLTV pro demos).

Any player can be analyzed on the fly from the search bar (Steam link, SteamID64, custom URL or share code). Share codes: every player of those matches feeds the base, and full profiles are built for you, the players you follow and your teammates (plus an update of players already profiled); search anyone else to build theirs. A demo Valve no longer has (after about a month) is given up after 2 tries.

## Requirements

- Windows, Python 3.11+
- Steam running and signed in, **CS2 closed** (to fetch the match list through the Game Coordinator)
- Optional: [7-Zip](https://www.7-zip.org/) (HLTV pro demos) and [Git for Windows](https://gitforwindows.org/) (its `curl` is used for csstats.gg)

```bash
pip install -r requirements.txt
```

`boiler-writter` and the map radars are downloaded automatically on first launch.

## Usage

| Command | What it does |
|---|---|
| `Coach CS2.bat` | Starts the local app (http://localhost:8765) |
| `python cs2coach.py` | Fetches and analyzes your latest matches (signed-in Steam account) |
| `python cs2coach.py --steamid <id>` | Analyzes another player |
| `python cs2coach.py --sharecode CSGO-...` | Analyzes one match |
| `python cs2coach.py --authcode XXXX-XXXXX-XXXX --knowncode CSGO-...` | The whole history (needs `steam_api_key` in `out/settings.json`) |
| `python crawl.py` / `python profile_all.py` | Grows the reference population (players met in matches) |
| `python pro.py --teams` | Downloads and analyzes pro demos (HLTV) |
| `python deepdive.py` | Deep analysis: engagements, grenade audit, zones vs pros |
| `python rounds.py` then `python midround.py` | Round context and mid-round analysis of every demo (run automatically by the app) |
| `python profile_all.py --plans` | Rebuilds the progress plan of every profile |
| `python profile_all.py --existing` | Full analysis again for every existing profile |
| `autostart.bat` | Starts the app automatically with Windows |

The server port is set with the `COACH_PORT` environment variable.

## Steam connection (optional, Settings)

- **Sign in with Steam**: Steam's official page confirms your account (OpenID); the app never sees your password.
- **Playtime**: read from the Steam client files on this PC, no connection needed.
- **Full, automatic history**: with a Steam API key ([steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)) and the authentication code of your history ([Steam's CS2 help page](https://help.steampowered.com/en/wizard/HelpWithGameIssue/?appid=730&issueid=128)), every new match is found, even weeks later, then analyzed. The app checks at launch and every 30 minutes, never during a match: downloads, demo extraction and analyses wait for the end of your match (the game detection tells the app), and their processes run at the lowest priority so the game keeps the CPU. Demos that are not online yet (a few minutes after the match) are tried again at the next analysis. Matches without a demo still count in your habits (date, score, K/A/D, teammates), and your Steam friends are used to detect your group.
- The key and code stay in `out/settings.json` (not versioned) and only go to Steam's official API. "Disconnect everything" removes them.

## Limits

- Valve only provides the **last 8 matches**, and demos expire after about **a month**.
- A player with no public Leetify profile and no shared demo only gets a light profile (Steam/csstats ranks).
- FACEIT isn't supported.

## Data and privacy

Everything stays local in `cache/` (demos) and `out/` (analyses, generated site, `settings.json` which can hold a Steam API key and an authentication code). These folders are **not versioned**.

## Credits

- [demoparser2](https://github.com/LaihoE/demoparser): demo parsing
- [boiler-writter](https://github.com/akiver/boiler-writter) (MIT): match list through the Game Coordinator
- Radars and map metadata from [CS Demo Manager](https://github.com/akiver/cs-demo-manager)
- [Leetify](https://leetify.com), [csstats.gg](https://csstats.gg), [HLTV](https://www.hltv.org): public stats and pro demos
