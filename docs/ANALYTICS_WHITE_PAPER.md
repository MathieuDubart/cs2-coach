# CS2 Coach Analytics Methodology: A White Paper

## Executive Summary
This white paper outlines the advanced analytical models and coaching methodologies powering the CS2 Coach application. Moving beyond traditional scoreboard statistics like K/D and ADR, our engine parses demo files to extract deep spatial, temporal, and situational data. By analyzing macro-strategy, mid-round micro-decisions, and pro-level behavioral metrics, we provide actionable, data-driven insights to elevate team performance and individual mechanics.

---

## 1. Macro-Strategy & Predictive Modeling (T-Side Analytics)

Understanding T-side behavior requires analyzing the flow of the round, attack pacing, and sequential decision-making. Our `tside.py` engine builds a predictive profile of the opposing team.

### Attack Dynamics & Tempo
Attacks are dynamically categorized based on the number of players committed and the round timer, allowing defense to anticipate the opponent's pacing:
- **Rush:** 3+ players committing to a site within the first 30 seconds.
- **Fast Push:** 1-2 players taking aggressive early space within the first 30 seconds.
- **Execute:** Coordinated site takes occurring between 30 and 75 seconds.
- **Late Hit:** Desperation or default-heavy hits occurring after 75 seconds (under 0:40 remaining).

### Predictive Site Modeling
Using logistic regression, we model the probability of a team hitting Bombsite A or B on any given round. The model is fed features such as:
- **Sequential Behaviors:** Do they repeat a site after a win? Do they switch after a loss?
- **Streaks:** Have they hit the same site 2+ times in a row?
- **Half Preferences:** What is their baseline bias toward one site over the course of the half?
- **Lone deaths before the hit:** the Ts lost alone earlier in the round (no teammate within 1,000 units, not traded) and on the previous round, which shift the odds of the main attack's destination.

The fit is a ridge-regularized logistic regression with the map's own A/B odds as an offset (Newton steps, `tside._fit`), so a team with little history stays close to the map's base rate.

### Map Control & Lurking
We track "lone" players—defined as a Terrorist with no teammate within 1,000 units. By analyzing these isolated deaths and engagements, we differentiate between active map-control (gathering information) and ineffective lurking, adjusting site predictions accordingly.

---

## 2. Mid-Round Decision Making

Matches are won and lost in the mid-round. The `midround.py` module evaluates how players react to evolving situations, focusing on rotations, anchoring, and situational discipline.

### CT Rotation Efficiency
Rotations are heavily scrutinized to evaluate map awareness and safety:
- **Reaction Time:** Time elapsed between the first sign of a site hit and the player starting their rotation. Negative times indicate high-level anticipation (early rotations).
- **Travel Time & Routing:** The specific pathways taken (e.g., through spawn vs. through mid) and the time it takes to arrive.
- **Rotation Safety:** Identifying rounds where rotators are caught and killed in transition ("died on the way").

### Site Anchoring
A good anchor doesn't necessarily need to kill the entire team; they need to buy time. We measure anchor effectiveness by:
- **Hold Time:** The percentage of site hits where the anchor survives for at least 5 seconds after the hit commences.
- **Kills Per Hit:** The average number of kills an anchor secures when their site is executed upon.

### Situational Discipline & Awareness
- **Man-Advantage Thrown:** Rounds where a team has a numerical advantage, but a player dies untraded, effectively "throwing" the advantage.
- **Economy & Save Discipline ("Lost Causes"):** When a player is left in a 1v3+ scenario with less than 30 seconds remaining, we track whether they successfully save their equipment or take reckless, low-percentage engagements and die.
- **Noise Management:** Tracking audible footsteps (within a 1,100-unit hearing radius) when a player is lurking alone or in a clutch situation, highlighting unintentional information leaks.

---

## 3. Pro-Level Micro-Metrics

`pro_analyst.py` counts, for each match, four habits an analyst points at, as raw numbers with their base (saved in the match's `stats.json`); the review adds them up over the session and only reports what has enough cases. The first version (03/10) counted team flashes, called a 10% flash rate "excellent" and flagged a single round as "predictable"; it was rewritten on 04/10.

### Died soon after your first kill
The rounds where the player died within 8 seconds of their first kill, out of the rounds where they got a kill (both sides). After a kill the numbers favor the team; peeking again gives the advantage back. Reported from 8 kill rounds: 30% or more is a priority, 20-30% a warning, 10% or less a strength.

### Deaths without impact
Deaths that no teammate traded within 5 seconds (the killer killed by a teammate) and with no damage dealt to an enemy in the 3 seconds before. Out of all deaths, from 8 deaths: 50% or more is a priority, 35-50% a warning, 20% or less a strength.

### Flashes your team uses
Every enemy the player's flashes blinded for more than 1.5 seconds (teammates and the player excluded), and whether the player's team damaged that enemy while blind. From 6 such enemies: 20% or less is a warning (call the flash, or flash for your own peek), 50% or more a strength.

### Death spots
Where the player died, by the game's place name. A place that holds at least 4 deaths and 30% of the player's deaths on that map over the session is reported: the enemies can expect them there. Bombsites are left out, since an anchor dies on their site by role, not by habit.

---

## 4. Match Rating and the Review

### Match rating
The rating is an approximation of HLTV Rating 2.0 (the multiple regression published by flashed.gg, `context.rating`):
`0.0073·KAST + 0.3591·KPR − 0.5329·DPR + 0.2372·Impact + 0.0032·ADR + 0.1587`, with `Impact = 2.13·KPR + 0.42·APR − 0.41`.
The page colors it like HLTV: under 0.85, 0.85-0.95, 0.95-1.05, 1.05-1.20, over 1.20.

### The review in three tiers
`review.py` compares the last session (the games played less than 3.5 hours apart, at least 2; else the last 3 matches) with up to 12 matches before it, on eight indicators (rating, ADR, deaths traded, isolated deaths, man advantages thrown, grenades that died with the player, crosshair offset, opening duels). A change is a "trend" from 1.5 standard errors and "clear" from 2.5 (eight indicators on a few games: with 2, one session in three would show a clear change by chance). Its possible reasons (late games, long sessions, the session's maps, solo or group, experiments started) are coincidences to check, not proofs.

The page shows it in three tiers: a quick brief (record, rating and its trend match by match, ADR, what works, what slips, the next session), map by map (record, rating, round wins per side, what to play and to avoid there), and the deep dive (every change with its reasons, the pro insights of the session, the matches, the focus areas, calls, mood, demo facts, live check, tests).
