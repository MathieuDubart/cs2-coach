# Wily, your CS2 coach

Wily is a free, open source coach for Counter-Strike 2 that runs on your PC. It analyzes your matchmaking demos, gives
you live advice on a second screen during your matches, and warms you up on a local training server with bots
replaying your own deaths.

**Download:** [wily.valentingassend.com](https://wily.valentingassend.com/) (Windows installer, Linux script) ·
**Releases with checksums:** [GitHub releases](https://github.com/ValentinGassend/cs2-coach/releases) ·
**Status:** public alpha (0.0.1-alpha), expect rough edges.

## What it does

- **Live (during the match, second screen):** what to buy this round and the next, where the Ts are likely to go
  (updated with the round clock and what you call), your paths and strong spots on the radar, the grenades worth
  throwing now, the post-plant and the retake. Numpad binds tell your team the plan in one chat line ("Rush B").
- **Prepare (before you play):** a timed warm-up built on your weak points, on a local training server where bots
  replay your real deaths and clutches, with grenade drills from the spots you actually play.
- **Review (after the session):** what changed against your previous matches and why, your focus of the week, every
  match round by round, compared with a base of thousands of anonymized matches and with pro demos.

## Can I trust it?

You should be careful with any tool you run next to your game. Here is what you can check yourself:

- **The code is public.** Every line of the app is in this repository (Python, plus a small C# plugin for the
  training server). The releases are built from it.
- **Same checksums everywhere.** Each [GitHub release](https://github.com/ValentinGassend/cs2-coach/releases) is tied
  to the exact commit it was built from and lists the SHA-256 of `WilySetup.exe` and of the Linux installer, the same
  values the website shows.
- **Signed updates.** Every update (code, base, Python runtime) is described in `latest.json`, signed with the
  author's Ed25519 key; the app and the Linux installer check that signature and each file's SHA-256 before installing
  anything. The public key ships with the app (`release_key.pub`).
- **Not code-signed yet.** `WilySetup.exe` has no paid Windows certificate, so SmartScreen warns once ("More info",
  then "Run anyway"). That is the only reason for the warning.
- **No anti-cheat risk.** Wily only uses what Valve provides: Game State Integration (the official feature used by
  HUDs and RGB keyboards), the console log CS2 writes, the Steam Web API and your match demos. It never reads the
  game's memory or network traffic, never injects anything, and never plays for you. The training server is a separate
  local copy of the game that only you join.

## Your data

- **Stays on your PC:** your demos, your profile and analyses, your Steam codes, your voice recordings (if you turn
  that feature on), your settings.
- **Shared by default, anonymized:** the tables Wily extracts from your new matches (positions, duels, grenades, buys,
  rounds) join the reference base, with every SteamID replaced by a random id used for that match only, no names and
  no match id. Also anonymous usage counters (pages opened, buttons used, errors). The first launch tells you and turns
  both off in one click; Settings does it at any time.
- Details: [privacy policy](https://wily.valentingassend.com/privacy.html).

## Requirements

- Windows 10 or 11 (64-bit), or Linux with Python 3.11+ (review and Live; the training server is experimental there).
- CS2 on Steam, 8 GB of RAM, disk space for your demos (about 250 MB per match).

## Install

- **Windows:** download `WilySetup.exe` from the website and run it. It downloads the parts, checks them and installs
  Wily for your account (no administrator rights).
- **Linux:** download `wily-linux.sh`, then run `sh wily-linux.sh`. It checks the release's signature and installs
  Wily into `~/.local/share/wily` with its own Python environment, plus a menu entry.

At the first launch, three steps: your Steam account, CS2 connected (one launch option to paste), your match history
code. Your matches are then analyzed on your PC.

## Run from source

```
pip install -r requirements.txt
python serve.py            # the app, at http://127.0.0.1:8765
```

Useful entry points:

| Command | What it does |
|---|---|
| `python serve.py` | The local app (Review, Live, Prepare, Settings) |
| `python cs2coach.py` | Fetches and analyzes your latest matches (signed-in Steam account) |
| `python cs2coach.py --sharecode CSGO-...` | Analyzes one match |
| `python make_beta.py --release <version> --notes "..."` | Builds a release (code, base, runtime, installers, signed `latest.json`) |

`cache/` (demos) and `out/` (analyses, settings, keys) are local and never versioned. The training server's plugin is in
`plugin/CoachReplay` (C#, CounterStrikeSharp).

## Contributing

Issues and pull requests are welcome. Bug reports from the app itself (the **alpha · report** tag) show you exactly
what is sent before sending it.

## Credits

- [demoparser2](https://github.com/LaihoE/demoparser): demo parsing
- [boiler-writter](https://github.com/akiver/boiler-writter) (MIT): the match list through Steam's Game Coordinator
- Radars and map metadata from [CS Demo Manager](https://github.com/akiver/cs-demo-manager)
- [Metamod:Source](https://www.metamodsource.net/) and [CounterStrikeSharp](https://github.com/roflmuffin/CounterStrikeSharp): the training server's plugin framework
- [Leetify](https://leetify.com) and [HLTV](https://www.hltv.org): public stats and pro demos

## License

Copyright 2026 [Valentin Gassend](https://valentingassend.com/).

Licensed under the [Apache License, Version 2.0](LICENSE): you may use, modify, redistribute and contribute to this
work, provided you keep the copyright and the [NOTICE](NOTICE) file, which credits its author, Valentin Gassend,
with a link to [valentingassend.com](https://valentingassend.com/). Contributions are accepted under the same
license. The CoachReplay plugin is under the MIT License; third-party components keep their own licenses.
