// The training session: one Play in the app, then everything follows on its own, block after block (aim on the map,
// stuff, situations), in the time chosen. The screen says what to do; each drill scores points, a streak multiplies
// them, a miss is tried once more right away (repetition), and each drill is written to coach/results.jsonl for the app
// (Leitner boxes: what you missed comes back next session).
//
// Commands during a session: !n skips the drill, !pause / !resume, !stop ends the session.
using System.Globalization;
using System.Numerics;
using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using Microsoft.Extensions.Logging;

namespace CoachReplay;

public class Spot
{
    [JsonPropertyName("pos")] public float[] Pos { get; set; } = new float[3];
    [JsonPropertyName("ang")] public float[] Ang { get; set; } = new float[2];   // pitch, yaw
    [JsonPropertyName("zone")] public string? Zone { get; set; }
    [JsonPropertyName("at")] public float At { get; set; }   // prefire: when it peeks (s after the start)
    [JsonPropertyName("poly")] public List<float[]> Poly { get; set; } = new();   // defend: the place's ground outline (06/10)
    [JsonPropertyName("duck")] public bool Duck { get; set; }   // prefire: an angle held crouched
    [JsonPropertyName("seq")] public int Seq { get; set; } = -1;   // prefire: its rank in the order the way shows them (07/10)
    [JsonPropertyName("li")] public int Li { get; set; }   // prefire: the gold line's point from where it is seen first
}

public class Drill
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("map")] public string Map { get; set; } = "";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("tip")] public string Tip { get; set; } = "";
    [JsonPropertyName("team")] public int Team { get; set; }
    [JsonPropertyName("me")] public Spot? Me { get; set; }
    [JsonPropertyName("bots")] public List<Spot> Bots { get; set; } = new();
    [JsonPropertyName("weapons")] public List<string> Weapons { get; set; } = new();
    [JsonPropertyName("bot_weapons")] public List<string> BotWeapons { get; set; } = new();
    [JsonPropertyName("type")] public string Type { get; set; } = "";
    [JsonPropertyName("item")] public string Item { get; set; } = "";
    [JsonPropertyName("how")] public string How { get; set; } = "";
    [JsonPropertyName("click")] public string Click { get; set; } = "";   // "" when the demos don't tell
    [JsonPropertyName("target")] public float[]? Target { get; set; }   // stuff: where it lands (x, y, and z when known)
    [JsonPropertyName("victims")] public List<Spot> Victims { get; set; } = new();   // stuff: the enemies' spots it is for
    [JsonPropertyName("level")] public int Level { get; set; }
    [JsonPropertyName("scenario")] public string? Scenario { get; set; }
    [JsonPropertyName("mode")] public string Mode { get; set; } = "";   // aim: prefire, defend, or "" (your duel spots)
    [JsonPropertyName("seconds")] public int Seconds { get; set; } = 75;
    [JsonPropertyName("alive")] public int Alive { get; set; } = 3;
    [JsonPropertyName("goal")] public int Goal { get; set; } = 8;   // defend: the frags that make it a success
    [JsonPropertyName("posts")] public List<Spot> Posts { get; set; } = new();   // defend: the spots to hold in turn, then free
    [JsonPropertyName("armor")] public int Armor { get; set; } = 100;   // both sides (a pistol defense: no helmet)
    [JsonPropertyName("helmet")] public bool Helmet { get; set; } = true;
    [JsonPropertyName("tracks")] public List<EntryTrack> Tracks { get; set; } = new();   // defend: real hits on the site
    [JsonPropertyName("route")] public List<string> Route { get; set; } = new();   // prefire: the places of the way
    [JsonPropertyName("line")] public List<float[]> Line { get; set; } = new();   // prefire: the way, drawn on the ground
    [JsonPropertyName("variant")] public string Variant { get; set; } = "";   // the aim map: flick, strafe, duel
    [JsonPropertyName("count")] public int Count { get; set; } = 3;   // the aim map: targets at once
    [JsonPropertyName("clock")] public float Clock { get; set; }   // the round's clock at GO (s left; 0: none)
    [JsonPropertyName("mate")] public Spot? Mate { get; set; }   // a boost: the teammate you stand on (06/10)
    [JsonPropertyName("step")] public int Step { get; set; } = 2;   // its tracks' ticks per frame (a rush, from the 0.5 s samples: 32)
    [JsonPropertyName("rush_at")] public float RushAt { get; set; }   // a timing smoke: the round's time (s) the real rush gets to its spot (07/10)
    [JsonPropertyName("marks")] public List<float[]> Marks { get; set; } = new();   // momentum: a way's checkpoints (x, y, z, its share of the way)
    [JsonPropertyName("par")] public float Par { get; set; }   // momentum: the base's time on that way (s); a silent walk's time allowed
    [JsonPropertyName("best")] public float Best { get; set; }   // momentum: the base's fastest runs of it (their 10th percentile)
    [JsonPropertyName("pro")] public float Pro { get; set; }   // momentum: the pros' time (0: no pro run of it)
    [JsonPropertyName("from")] public float[]? From { get; set; }   // momentum: a jump's takeoff
    [JsonIgnore] public bool Rush => Kind == "nade" && Tracks.Count > 0;
}

public class EntryTrack
{
    [JsonPropertyName("zone")] public string Zone { get; set; } = "";
    [JsonPropertyName("path")] public float[] Path { get; set; } = Array.Empty<float>();
    [JsonPropertyName("nades")] public List<Nade> Nades { get; set; } = new();   // the grenades its player threw on the way (f: its frame)
    [JsonPropertyName("post")] public int Post { get; set; } = -1;   // the post it walks into the sight of (-1: any, the free part)
    [JsonPropertyName("arrive")] public float Arrive { get; set; } = -1f;   // a rush: s after GO it gets to the grenade's spot
}

public class Block
{
    [JsonPropertyName("map")] public string Map { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("seconds")] public int Seconds { get; set; }
    [JsonPropertyName("drills")] public List<Drill> Drills { get; set; } = new();
}

public class Session
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("minutes")] public int Minutes { get; set; }
    [JsonPropertyName("maps")] public List<string> Maps { get; set; } = new();
    [JsonPropertyName("difficulty")] public int Difficulty { get; set; } = 2;
    [JsonPropertyName("blocks")] public List<Block> Blocks { get; set; } = new();
}

public partial class CoachReplay
{
    Session? sess;
    int blockIdx = -1, tries, points, streak, okN, doneN, drillNo, sessGen, waitFile;
    DateTime blockEnd;
    readonly LinkedList<Drill> queue = new();
    Drill? drill;
    // aim: the targets come one by one
    readonly List<int> aimOrder = new();
    readonly List<double> reacts = new();
    int aimNext, aimSpawn, aimHs, frags, deaths, plants, lastHud;
    readonly Dictionary<int, float> peekAt = new();   // prefire: the bots still hidden, and when they peek
    int lineAt, lastPeek;   // prefire: how far along the gold line you got (its point), the last one that peeked (tick)
    // stuff: three throws, the camera on your grenade, then from their side
    int attempts;
    bool nadeWait;
    int rushIn = -1;   // a timing smoke: the tick the first runner got to its spot (-1: not yet)
    float rushDelay;   // the runners' wait before they start (guided: 2 s, the spot: 1 s, alone: the real timing)
    string nadeStage = "";   // "throw": your throws (the camera follows them), "theirs": watching it from their spot
    bool pracOn;   // CS2's grenade practice views are on (stuff drills only)
    CDynamicProp? cam;
    CBaseCSGrenadeProjectile? camNade;
    Vector3 camDir = new(1, 0, 0);
    int camEnd, theirsDmg;
    float theirsFlash;
    (bool ok, string outcome, int pts, string detail)? theirsRes;
    DateTime attemptEnd;
    readonly List<float[]> nadePops = new();   // stuff: where your throws of this drill popped (the app learns the lineups that don't land)
    static readonly Random Rng = new();
    string introHtml = "";
    // the blocks: defending a site (CT), the push routes (T), aim on hostage maps, the stuff, the situations
    static readonly Dictionary<string, string> KindName = new() { ["defend"] = N("DEFENSE"), ["push"] = N("PUSH"), ["aim"] = N("AIM"), ["nade"] = N("STUFF"),
        ["situation"] = N("SITUATION"), ["wallbang"] = N("WALLBANG"), ["crossfire"] = N("CROSSFIRE"), ["momentum"] = N("MOMENTUM") };
    // a drill's end as the screen and the chat say it (the results keep the English word: the app reads them)
    static readonly Dictionary<string, string> OutcomeName = new() { ["cleared"] = N("CLEARED"), ["done"] = N("DONE"), ["timeout"] = N("TIME'S UP"),
        ["dead"] = N("DEAD"), ["won"] = N("WON"), ["survived"] = N("SURVIVED"), ["traded"] = N("TRADED"), ["kill"] = N("KILL, THEN DEAD"),
        ["passive"] = N("NO KILL"), ["defused"] = N("DEFUSED"), ["exploded"] = N("BOMB EXPLODED"), ["late"] = N("LATE"), ["in time"] = N("IN TIME"),
        ["perfect"] = N("PERFECT"), ["good"] = N("GOOD"), ["miss"] = N("MISS"), ["no throw"] = N("NO THROW"), ["skipped"] = N("SKIPPED") };
    string Shown(string outcome) => OutcomeName.TryGetValue(outcome, out var s) ? T(s) : outcome.ToUpper();
    static readonly Dictionary<string, string> KindColor = new() { ["defend"] = "#4fc3a1", ["push"] = "#ff8a3d", ["aim"] = "#ff8a3d", ["nade"] = "#5ab4ff", ["situation"] = "#e0a030", ["wallbang"] = "#c792ea", ["crossfire"] = "#ff8a3d", ["momentum"] = "#56d4c8" };
    int postIdx = -1;   // a defense: the spot you hold now (Posts), Posts.Count: free
    // a defense's attackers come in waves, all of them at once (09/10): the wave's number, its first death (tick), the
    // next one called
    int wave, waveFirstDead = -1;
    bool waveDue;
    int preKillAt;   // prefire: the last kill (tick); the last ones shown after 8 s without one (09/10)
    readonly HashSet<int> beaconed = new();
    // the aim map: when each target came, the last kill, the strafers' way and its end
    readonly Dictionary<int, int> cameAt = new();
    readonly Dictionary<int, (int sign, int until)> strafe = new();
    int lastKill;
    List<Vector3> rangeTheirs = new();
    // 07/10: the aim range left aim_map (an unsigned 2023 file the game no longer loads from a server) for a map with
    // cover: a spot of theirs you can't see from yours is dropped for the map (a target unseen 3 s moves on)
    // the spots themselves, not their place in rangeTheirs: that list is built again for each drill and narrowed by a
    // cone that depends on the variant (a duel's is 60 deg where a flick's is 80), while this set is only emptied when
    // the map changes, so kept as numbers its entries came to mean other spots from one drill to the next (13/10)
    readonly List<Vector3> rangeBlind = new();

    bool Blind(Vector3 p) => rangeBlind.Any(q => Vector3.Distance(q, p) < 2f);
    readonly Dictionary<int, int> rangeSeenAt = new();
    string rangeMap = "";
    bool rangeSpots;   // a target has been seen this drill: the game's spotting works for them, so unseen means hidden
    readonly List<(Drill d, bool ok, string outcome)> sessDone = new();   // this session's drills, each one's last try
    readonly List<(Drill d, bool ok, string outcome)> lastDone = new();   // the last session's (!again)
    Session? lastSess;
    int againN;

    void RegisterSession()
    {
        AddCommand("css_session", "start a training session: css_session <id>", (p, c) => CmdSession(p, c));
        AddCommand("css_report", "tell Wily's author what's wrong or what you'd want, from where you are: !report <text>", (p, c) => Report(p, c.ArgString));
        AddCommand("css_pause", "pause the session (the block's clock waits): !resume goes on", (p, c) => Pause(p));
        AddCommand("css_resume", "go on with a paused session", (p, c) => Resume(p));
        AddCommand("css_go", "go on with a paused session", (p, c) => Resume(p));
        AddCommand("css_again", "the last session's drills again: !again <number>[,<number>], missed or all", (p, c) => Again(p, c.ArgString));
        RegisterWorkshopGuard();
        RegisterCrossfire();
        RegisterMomentum();
        RegisterEventHandler<EventSmokegrenadeDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventFlashbangDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventHegrenadeDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventMolotovDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventBombPlanted>((e, _) => { BombPlanted(); return HookResult.Continue; });
        RegisterListener<Listeners.OnEntitySpawned>(ent =>
        {
            if (sess == null || nadeStage != "throw" || !ent.DesignerName.EndsWith("_projectile")) return;
            var h = ent.Handle;
            Server.NextFrame(() => CamStart(h));   // its thrower is set on the next frame
        });
    }

    static string MapName(string m)
    {
        if (m == "aim_botz") return "Aim Botz";
        var n = m.Replace("de_", "").Replace("cs_", "").Replace("ar_", "");
        return string.Join(" ", n.Split('_', StringSplitOptions.RemoveEmptyEntries).Select(w => char.ToUpper(w[0]) + w[1..]));
    }

    // 07/10, the user's pick for the aim block: Aim Botz (Steam Workshop), loaded by its id. Its own config (run at its
    // load) sets 123 things for its own play: undone before any other map, and the ones that matter undone by each Setup
    public static readonly Dictionary<string, string> Workshop = new() { ["aim_botz"] = "3070244462" };
    static readonly string[] AfterWorkshop = {
        "game_type 0", "game_mode 1", "sv_cheats 0", "sv_infinite_ammo 0", "bot_all_weapons", "bot_join_team any", "bot_join_delay 0",
        "mp_humanteam any", "mp_allowspectators 1", "mp_respawn_on_death_ct 0", "mp_respawn_on_death_t 0", "weapon_auto_cleanup_time 0",
        "weapon_max_before_cleanup 0", "mp_ct_default_primary \"\"", "mp_ct_default_secondary weapon_hkp2000", "mp_t_default_primary \"\"",
        "mp_t_default_secondary weapon_glock", "mp_t_default_melee weapon_knife", "mp_free_armor 0", "mp_max_armor 2", "mp_buy_anywhere 0",
        "mp_startmoney 800", "sv_autobuyammo 0", "sv_buy_status_override -1", "mp_weapons_allow_heavyassaultsuit 0", "mp_drop_knife_enable 0",
        "mp_disconnect_kills_players 0", "mp_force_pick_time 15", "spec_freeze_time 3", "bot_quota 0", "bot_kick" };

    void ChangeMap(string map)
    {
        if (Workshop.ContainsKey(Server.MapName) && !Workshop.ContainsKey(map))
            foreach (var c in AfterWorkshop) Server.ExecuteCommand(c);
        Server.ExecuteCommand(Workshop.TryGetValue(map, out var id) ? $"host_workshop_map {id}" : $"changelevel {map}");
    }

    // 08/10, his warm-up video (20:29 and 20:30): Aim Botz runs its own logic at each round start through its command
    // entities (a point_servercommand and a point_clientcommand, both "@servercommand"): its config again (bot_quota 12,
    // its bots on T, respawns...), bot_add_t, then a check that, short of its 12 bots, sends "restart". The round restart
    // of each drill set it off, and a Workshop map can't be loaded by its name here: the server was left with no map and
    // the player in the menu. On a Workshop map the plugin sets everything itself: the map's command entities are
    // removed, and a load by name goes through the map's Workshop id.
    int wsCut;

    string HowClick(Drill d) => d.Click != "" ? $"{How(d.How)} · {How(d.Click)}" : How(d.How);

    static bool MapLogic(string n) => n.StartsWith("logic_") || n.StartsWith("math_") || n.StartsWith("trigger_")
        || n is "point_servercommand" or "point_clientcommand" or "point_broadcastclientcommand" or "point_script" or "point_template"
            or "game_player_equip" or "player_weaponstrip" or "game_ui" or "game_text" or "env_hudhint";

    void RegisterWorkshopGuard()
    {
        // its logic removed as it spawns (each round restart makes it again): its console commands, its scripts, relays,
        // counters, timers, templates and triggers. 08/10 22:58, his second warm-up: its weapon handling took the drill's
        // rifle at his spawn (@weapon_relay.kill.primary: a Glock and a knife left) and its kill zones killed the strafing
        // targets 15 times in 11 s. Walls, floors and spawns stay. (Reading an output's connections to stop only some of
        // them crashed the server: CounterStrikeSharp's layout of them is off.)
        RegisterListener<Listeners.OnEntitySpawned>(ent =>
        {
            if (!MapLogic(ent.DesignerName) || !Workshop.ContainsKey(Server.MapName)) return;
            ent.Remove();
            if (wsCut++ == 0) Log("workshop map: its own logic removed ({c}...)", ent.DesignerName);
        });
        RegisterListener<Listeners.OnMapStart>(_ => wsCut = 0);
        AddCommand("css_dbgfire", "an input to the entities of that name: css_dbgfire <name> <input> [value]", (p, c) =>
        {
            var n = 0;
            foreach (var e in Utilities.GetAllEntities())
                if (e.IsValid && e.Entity?.Name == c.GetArg(1)) { e.AcceptInput(c.GetArg(2), null, null, c.ArgCount > 3 ? c.GetArg(3) : ""); n++; }
            c.ReplyToCommand($"{n} entities");
        });
        foreach (var cmd in new[] { "restart", "map", "changelevel" })
            AddCommandListener(cmd, (p, info) =>
            {
                if (p != null) return HookResult.Continue;   // a player's own console: the game's rules
                var target = cmd == "restart" || info.ArgCount < 2 ? Server.MapName : info.GetArg(1);
                if (!Workshop.TryGetValue(target, out var id)) return HookResult.Continue;
                Log("workshop map: \"{c}\" by name stopped", info.GetCommandString);
                if (cmd != "restart") Server.NextFrame(() => Server.ExecuteCommand($"host_workshop_map {id}"));
                return HookResult.Stop;
            }, HookMode.Pre);
    }

    // the screen: the drill's line stays all the time (sent again every 0.4 s), an event shows above it for a few seconds
    string hudMain = "", hudFlash = "";
    DateTime hudFlashUntil;
    int hudSent;
    void Html(string html, int secs = 3) { hudFlash = html; hudFlashUntil = DateTime.UtcNow.AddSeconds(secs); SendHud(); }
    void SetMain(string html) { if (html == hudMain) return; hudMain = html; SendHud(); }
    void SendHud()
    {
        hudSent = Server.TickCount;
        var fl = DateTime.UtcNow < hudFlashUntil ? hudFlash : "";
        var h = fl != "" && hudMain != "" ? $"{fl}<br>{hudMain}" : fl + hudMain;
        if (h == "") return;
        foreach (var p in Humans()) p.PrintToCenterHtml(h, 1);
    }
    void HudTick() { if ((sess != null || hudFlash != "") && Server.TickCount - hudSent >= 26) SendHud(); }

    // prefire: the way, a gold line on the ground
    readonly List<CBeam> beams = new();
    void DrawLine(List<float[]> pts)
    {
        ClearLine();
        var gold = System.Drawing.Color.FromArgb(255, 255, 205, 60);
        for (int i = 0; i + 1 < pts.Count; i++)
        {
            var a = new Vector3(pts[i][0], pts[i][1], pts[i][2] + 8);
            var b = new Vector3(pts[i + 1][0], pts[i + 1][1], pts[i + 1][2] + 8);
            Beam(a, b, gold, 5f);   // 06/10: a line you see from afar ("le path à prendre au sol avec un trait"; no arrows: "pas besoin de flèches")
        }
    }
    void ClearLine() { foreach (var b in beams) if (b.IsValid) b.Remove(); beams.Clear(); }

    // a situation's zone: its place's outline (or a ring when the place is unknown), light blue
    void DrawZone(Scenario s)
    {
        var blue = System.Drawing.Color.FromArgb(255, 90, 180, 255);
        if (s.ZonePoly.Count >= 3)
            for (int i = 0; i < s.ZonePoly.Count; i++)
            {
                var a = s.ZonePoly[i]; var b = s.ZonePoly[(i + 1) % s.ZonePoly.Count];
                Beam(new Vector3(a[0], a[1], a[2] + 6), new Vector3(b[0], b[1], b[2] + 6), blue, 4f);
            }
        else if (s.ZoneAt is { Length: >= 3 } at)
            for (int i = 0; i < 24; i++)
            {
                float a0 = i * MathF.PI / 12, a1 = (i + 1) * MathF.PI / 12;
                Beam(new Vector3(at[0] + 250 * MathF.Cos(a0), at[1] + 250 * MathF.Sin(a0), at[2] + 6),
                     new Vector3(at[0] + 250 * MathF.Cos(a1), at[1] + 250 * MathF.Sin(a1), at[2] + 6), blue, 3f);
            }
    }

    void Beam(Vector3 a, Vector3 b2, System.Drawing.Color c, float w)
    {
        var b = Utilities.CreateEntityByName<CBeam>("beam");
        if (b == null) return;
        b.Render = c;
        b.Width = w;
        b.Teleport(a, Vector3.Zero, Vector3.Zero);
        b.EndPos.X = b2.X; b.EndPos.Y = b2.Y; b.EndPos.Z = b2.Z;
        b.DispatchSpawn();
        beams.Add(b);
    }

    // stuff: where it must land: a beam standing there (from under your feet to well above when its height is not
    // known), and a ring on the ground of the PERFECT zone when it is
    void DrawMark(float x, float y, float z, float? ground, float r)
    {
        var blue = System.Drawing.Color.FromArgb(255, 90, 180, 255);
        Beam(new Vector3(x, y, (ground ?? z) - (ground == null ? 300 : 0)), new Vector3(x, y, (ground ?? z) + (ground == null ? 500 : 260)), blue, 5f);
        if (ground == null) return;
        for (int i = 0; i < 16; i++)
        {
            var a0 = i * MathF.PI / 8; var a1 = (i + 1) * MathF.PI / 8;
            Beam(new Vector3(x + r * MathF.Cos(a0), y + r * MathF.Sin(a0), ground.Value + 4), new Vector3(x + r * MathF.Cos(a1), y + r * MathF.Sin(a1), ground.Value + 4), blue, 3f);
        }
    }

    // stuff: where you stand, a green ring at your feet (06/10: "le repère de où moi je dois me mettre, il n'y en a pas")
    void DrawStand(Spot me)
    {
        var green = System.Drawing.Color.FromArgb(255, 90, 230, 90);
        var c = new Vector3(me.Pos[0], me.Pos[1], me.Pos[2] + 3);
        for (int i = 0; i < 12; i++)
        {
            float a0 = i * MathF.PI / 6, a1 = (i + 1) * MathF.PI / 6;
            Beam(c + new Vector3(18 * MathF.Cos(a0), 18 * MathF.Sin(a0), 0), c + new Vector3(18 * MathF.Cos(a1), 18 * MathF.Sin(a1), 0), green, 1.5f);
        }
    }

    // a situation: an ally down, a red cross where it fell, a post over it seen from afar
    void DrawX(Vector3 p)
    {
        var red = System.Drawing.Color.FromArgb(255, 255, 70, 70);
        Beam(p + new Vector3(-22, -22, 4), p + new Vector3(22, 22, 4), red, 3f);
        Beam(p + new Vector3(-22, 22, 4), p + new Vector3(22, -22, 4), red, 3f);
        Beam(p + new Vector3(0, 0, 4), p + new Vector3(0, 0, 90), red, 2f);
    }

    // stuff: a green cross 150 u ahead on the aim, from your eyes: put the crosshair on it. A small one 40 u ahead on the
    // same line, the same size on screen, is seen when a box stands between you and the far one (09/10, Dust2's smoke
    // to Mid Doors: "où est le repère ? le repère est derrière la caisse"); the two on one point: you stand right and aim right
    void DrawCross(Drill d)
    {
        if (d.Me == null) return;
        var eye = new Vector3(d.Me.Pos[0], d.Me.Pos[1], d.Me.Pos[2] + (d.How.Contains("crouch") ? 46 : 64));
        float p = d.Me.Ang[0] * MathF.PI / 180, y = d.Me.Ang[1] * MathF.PI / 180;
        var fw = new Vector3(MathF.Cos(p) * MathF.Cos(y), MathF.Cos(p) * MathF.Sin(y), -MathF.Sin(p));
        var right = new Vector3(MathF.Sin(y), -MathF.Cos(y), 0);
        var up = Vector3.Normalize(Vector3.Cross(right, fw));
        var green = System.Drawing.Color.FromArgb(255, 90, 230, 90);
        foreach (var (dist, arm, w) in new[] { (150f, 4f, 0.8f), (40f, 1.1f, 0.3f) })
        {
            var at = eye + fw * dist;
            Beam(at - right * arm, at + right * arm, green, w);
            Beam(at - up * arm, at + up * arm, green, w);
        }
    }

    // CS2's grenade practice views (stuff drills only): the trail after the throw. Never the landing preview while you
    // aim (04/10: "the camera at the bottom left is a bit of a cheat": in a match you find the throw without it)
    void Prac(bool on)
    {
        if (on == pracOn) return;
        pracOn = on;
        Server.ExecuteCommand("sv_grenade_trajectory_prac_pipreview 0");
        Server.ExecuteCommand($"sv_grenade_trajectory_prac_trailtime {(on ? 4 : 0)}");
    }

    // the grenade camera: your view follows your grenade (a camera prop as your view entity), you wait meanwhile
    void CamStart(nint h)
    {
        if (sess == null || drill == null || cur?.Kind != "nade" || nadeStage != "throw" || cam != null) return;
        var nd = new CBaseCSGrenadeProjectile(h);
        if (!nd.IsValid || nd.Thrower.Value?.OriginalController.Value is not { IsBot: false } c) return;
        var pawn = c.PlayerPawn.Value;
        if (pawn?.CameraServices == null) return;
        var cp = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
        if (cp == null) return;
        cp.DispatchSpawn();
        // an empty model, drawn by nobody: without a model it was the ERROR model, its shadow following your grenade
        // (04/10: "the shadow of the Gmod ERROR is still there")
        cp.SetModel(NullModel);
        cp.RenderMode = RenderMode_t.kRenderNone;
        Utilities.SetStateChanged(cp, "CBaseModelEntity", "m_nRenderMode");
        cp.AcceptInput("DisableShadow");
        cam = cp; camNade = nd; camEnd = Server.TickCount + 8 * 64;   // at most 8 s
        camDir = new Vector3(1, 0, 0);
        CamTick();
        pawn.CameraServices.ViewEntity.Raw = cp.EntityHandle.Raw;
        Utilities.SetStateChanged(pawn, "CBasePlayerPawn", "m_pCameraServices");
        Freeze(pawn, true);
    }

    void CamTick()
    {
        if (cam == null) return;
        if (!cam.IsValid) { cam = null; return; }
        if (camNade != null && camNade.IsValid && camNade.AbsOrigin is { } o)
        {
            var pos = new Vector3(o.X, o.Y, o.Z);
            var v = camNade.AbsVelocity;
            var vel = v == null ? Vector3.Zero : new Vector3(v.X, v.Y, v.Z);
            if (vel.Length() > 60) camDir = Vector3.Normalize(vel);   // landed: the last way it went
            var at = pos - camDir * 90 + new Vector3(0, 0, 20);
            var look = pos - at;
            var yaw = MathF.Atan2(look.Y, look.X) * 180 / MathF.PI;
            var pitch = -MathF.Atan2(look.Z, MathF.Sqrt(look.X * look.X + look.Y * look.Y)) * 180 / MathF.PI;
            cam.Teleport(at, new Vector3(pitch, yaw, 0), Vector3.Zero);
        }
        if (Server.TickCount >= camEnd) CamStop();
    }

    void CamStop()
    {
        var cp = cam;
        cam = null; camNade = null;
        foreach (var h in Humans())
        {
            var pawn = h.PlayerPawn.Value;
            if (pawn?.CameraServices == null) continue;
            pawn.CameraServices.ViewEntity.Raw = uint.MaxValue;
            AddTimer(0.3f, () => { if (pawn.IsValid) Utilities.SetStateChanged(pawn, "CBasePlayerPawn", "m_pCameraServices"); });
            if (nadeStage == "throw") Freeze(pawn, false);
        }
        if (cp != null) AddTimer(0.4f, () => { if (cp.IsValid) cp.Remove(); });
    }

    // the smokes and fires on the ground: gone (a missed throw's, your own before their side's)
    static void ClearNades()
    {
        foreach (var cls in new[] { "smokegrenade_projectile", "molotov_projectile", "incendiarygrenade_projectile", "inferno" })
            foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>(cls))
                if (e.IsValid) e.Remove();
    }

    // from their side: you stand where the enemies it is for stand, on the line they hold there, and the same grenade comes again
    void Theirs((bool ok, string outcome, int pts, string detail) res)
    {
        if (drill == null || drill.Victims.Count == 0) { DrillDone(res.ok, res.outcome, res.pts, res.detail); return; }
        var v = drill.Victims[Rng.Next(drill.Victims.Count)];
        nadeStage = "theirs"; theirsDmg = 0; theirsFlash = 0; theirsRes = res;
        foreach (var h in Humans())
        {
            var pawn = h.PlayerPawn.Value;
            if (pawn == null || !h.PawnIsAlive) continue;
            pawn.Teleport(new Vector3(v.Pos[0], v.Pos[1], v.Pos[2]), Upright(new Vector3(v.Ang[0], v.Ang[1], 0)), Vector3.Zero);
            Freeze(pawn, true);
        }
        SetMain($"<font color='#5ab4ff'>{T("FROM THEIR SIDE")}</font> · {drill.Title}<br><font class='fontSize-s'>{T("where they really stand: watch it come")}</font>");
        var g = sessGen;
        AddTimer(0.8f, () =>
        {
            if (g != sessGen || nadeStage != "theirs") return;
            // your own throw's smoke or fire goes first: only the one coming at you (04/10: "a double smoke")
            ClearNades();
            Server.ExecuteCommand("sv_cheats 1");   // only for this: the same grenade again
            Server.ExecuteCommand("sv_rethrow_last_grenade");
            Server.ExecuteCommand("sv_cheats 0");
        });
        AddTimer(12f, () => TheirsDone(g));   // in case it never pops
    }

    // it popped on them: what it did, then the drill ends
    void TheirsPopped()
    {
        if (drill == null || nadeStage != "theirs") return;
        var g = sessGen;
        AddTimer(0.2f, () =>
        {
            if (g != sessGen) return;
            foreach (var h in Humans()) theirsFlash = Math.Max(theirsFlash, h.PlayerPawn.Value?.FlashDuration ?? 0);
        });
        AddTimer(drill.Type switch { "smoke" => 5f, "molotov" => 4f, "flash" => 3f, _ => 2.5f }, () => TheirsDone(g));
    }

    void TheirsDone(int g)
    {
        if (g != sessGen || nadeStage != "theirs" || theirsRes == null || drill == null) return;
        nadeStage = "";
        foreach (var h in Humans()) { var pw = h.PlayerPawn.Value; if (pw != null) Freeze(pw, false); }
        var what = drill.Type switch
        {
            "flash" => theirsFlash > 0.3f ? F("blinded {s} s here", "s", theirsFlash.ToString("F1", CultureInfo.InvariantCulture)) : T("not blinded from here: it pops out of their sight"),
            "smoke" => T("their view through it: cut"),
            _ => theirsDmg > 0 ? F("−{hp} HP here", "hp", theirsDmg) : T("no damage here"),
        };
        var r = theirsRes.Value;
        theirsRes = null;
        DrillDone(r.ok, r.outcome, r.pts, $"{r.detail} · {F("from their side: {what}", "what", what)}");
    }

    // prefire: where the last ones are (the game's place names: "BombsiteA" -> "Bombsite A")
    string LeftPlaces()
    {
        var names = bots.Where(b => !gone.Contains(b.Value.Sid) && !peekAt.ContainsKey(b.Key))
            .Select(b => Utilities.GetPlayerFromSlot(b.Key)?.PlayerPawn.Value?.LastPlaceName)
            .Where(n => !string.IsNullOrEmpty(n))
            .Select(n => System.Text.RegularExpressions.Regex.Replace(n!, "(?<=[a-z])(?=[A-Z0-9])", " ")).Distinct();
        return string.Join(", ", names);
    }

    void CmdSession(CCSPlayerController? p, CommandInfo c)
    {
        var id = c.GetArg(1);
        var f = System.IO.Path.Combine(Dir, "sessions", id + ".json");
        Io(() =>   // a session is 1-2 MB of JSON: read and parsed off the game's thread (08/10)
        {
            Session? s = null;
            string? err = null;
            var u = ReadUi();   // the app's language: written with the session
            try { if (File.Exists(f)) s = JsonSerializer.Deserialize<Session>(File.ReadAllText(f)); else err = "?"; }
            catch (Exception e) { err = e.Message; }
            OnGame(() =>
            {
                UseUi(u);
                if (err == "?") err = F("no session {id}", "id", id);
                if (err != null) { Say(p is { IsValid: true } ? p : null, err); return; }
                if (s == null || s.Blocks.Count == 0) { sess = null; return; }
                StartSession(s);
            });
        });
    }

    // a situation's file (the whole round of the demo, hundreds of KB) read by the io thread: null while it loads
    readonly Dictionary<string, Scenario?> scLoaded = new();
    readonly HashSet<string> scLoading = new();
    Scenario? PeekSoon(string id, out bool pending)
    {
        pending = false;
        if (scLoaded.Remove(id, out var s)) return s;
        pending = true;
        if (scLoading.Add(id))
            Io(() => { var r = Peek(id); OnGame(() => { scLoading.Remove(id); scLoaded[id] = r; }); });
        return null;
    }

    void StartSession(Session s)
    {
        sess = s;
        difficulty = Math.Clamp(sess.Difficulty, 0, 3);
        mode = "actor";
        blockIdx = -1; points = streak = okN = doneN = drillNo = 0; drill = null; queue.Clear(); cur = null;
        sessDone.Clear();
        Log("session {id}: {n} blocks", sess.Id, sess.Blocks.Count);
        if (!Humans().Any()) { phase = "waiting"; return; }   // starts when you join
        Welcome();
        AddTimer(4f, NextBlock);
    }

    // the drills of the session that just ended, played again: one or some (!again 3, !again 2,5), the missed ones
    // (!again missed) or all of them (!again all), in their order, all of them whatever the time (04/10: "a recap with
    // inputs to replay the situations I missed, the defenses, the prefires, or restart the whole session")
    void Again(CCSPlayerController? p, string arg)
    {
        if (lastSess == null || lastDone.Count == 0) { Say(p, T("no session to play again yet")); return; }
        if (sess != null) { Say(p, T("a session is running: !stop first")); return; }
        arg = arg.Trim().ToLowerInvariant();
        var pick = arg is "" or "all" ? lastDone.Select(x => x.d).ToList()
            : arg == "missed" ? lastDone.Where(x => !x.ok).Select(x => x.d).ToList()
            : arg.Split(new[] { ',', ' ' }, StringSplitOptions.RemoveEmptyEntries).Select(x => int.TryParse(x, out var n) ? n - 1 : -1)
                 .Where(n => n >= 0 && n < lastDone.Count).Distinct().Select(n => lastDone[n].d).ToList();
        if (pick.Count == 0) { Say(p, arg == "missed" ? T("nothing missed: well played") : T("!again and a drill's number, missed or all")); return; }
        var blocks = new List<Block>();
        foreach (var d in pick)   // the drills of one map and one kind in a row: one block
        {
            var kind = d.Kind != "aim" ? d.Kind : d.Mode == "defend" ? "defend" : d.Mode == "prefire" ? "push" : d.Mode == "crossfire" ? "crossfire" : "aim";
            if (blocks.Count > 0 && blocks[^1].Map == d.Map && blocks[^1].Kind == kind) blocks[^1].Drills.Add(d);
            else blocks.Add(new Block { Map = d.Map, Kind = kind, Seconds = 3600, Drills = new() { d } });
        }
        StartSession(new Session { Id = $"{lastSess.Id}_again{++againN}", Minutes = lastSess.Minutes, Difficulty = lastSess.Difficulty,
            Maps = blocks.Select(b => b.Map).Distinct().ToList(), Blocks = blocks });
    }

    // 07/10, the user: "fais une commande report sur le serveur d'entraînement aussi": a note to Wily's author with the
    // drill and where you stand (coach/reports.jsonl; the app sends it within half a minute)
    void Report(CCSPlayerController? p, string? text)
    {
        text = (text ?? "").Trim().Trim('"').Trim();
        if (text.Length == 0) { Say(p, T("!report and what's wrong, or what you'd want: it goes to Wily's author with this drill and where you stand")); return; }
        var pw = p?.PlayerPawn.Value;
        var o = pw?.AbsOrigin;
        var a = pw?.EyeAngles;
        var rec = new Dictionary<string, object?>
        {
            ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["text"] = text.Length > 2000 ? text[..2000] : text,
            ["session"] = sess?.Id, ["block"] = sess != null && blockIdx >= 0 && blockIdx < sess.Blocks.Count ? sess.Blocks[blockIdx].Kind : null,
            ["drill"] = drill?.Id, ["drill_title"] = drill?.Title ?? cur?.Title, ["map"] = Server.MapName, ["phase"] = phase,
            ["pos"] = o == null ? null : new[] { o.X, o.Y, o.Z }, ["ang"] = a == null ? null : new[] { a.X, a.Y }
        };
        try
        {
            Append("reports.jsonl", JsonSerializer.Serialize(rec));
            Say(p, T("📨 noted: it goes to Wily's author with this drill and where you stand. Thanks!"));
        }
        catch (Exception e) { Log("report: {m}", e.Message); Say(p, F("couldn't keep it, sorry: the app's \"{tag}\" tag works too", "tag", T("alpha · report"))); }
    }

    void Welcome()
    {
        if (sess == null) return;
        var order = string.Join(" → ", sess.Blocks.Select(b => T(KindName[b.Kind])).Distinct());
        Html($"<font color='#e0a030'>{F("TRAINING · {n} MIN", "n", sess.Minutes)}</font><br><font class='fontSize-l'>{string.Join(" · ", sess.Maps.Select(MapName))}</font><br>{order}", 4);
        All($"{F("Training {n} min", "n", sess.Minutes)} · {string.Join(", ", sess.Maps.Select(MapName))} · {order}. "
            + T("!n skips a drill, !pause pauses (!resume), !stop ends, !report and a few words tells Wily's author."));
    }

    // 09/10, his warm-up: "si je mets stop, ça se met en pause ? Il faudrait pouvoir la mettre en pause, et la reprendre":
    // the drill stops, the bots go, the block's clock waits; !resume plays that drill again from its start
    bool paused;
    DateTime pausedAt;

    void Pause(CCSPlayerController? p)
    {
        if (sess == null) { Say(p, T("no session running")); return; }
        if (paused) { Say(p, T("already paused: !resume goes on")); return; }
        paused = true;
        pausedAt = DateTime.UtcNow;
        sessGen++; generation++;   // the timers on their way (next drill, a bot back, the setup) do nothing
        phase = "paused";
        ClearLine();
        if (cam != null) CamStop();
        bots.Clear(); builtFor = null;
        Server.ExecuteCommand("bot_quota 0");
        Server.ExecuteCommand("bot_kick");
        SetMain(PausedHtml());
        All(T("Paused · the block's clock waits · !resume goes on (that drill again from its start)."));
    }

    string PausedHtml() => $"<font color='#e0a030'>⏸ {T("PAUSED")}</font><br>{F("the block's clock waits · {cmd} goes on", "cmd", "<b>!resume</b>")}";

    void Resume(CCSPlayerController? p)
    {
        if (sess == null) { Say(p, T("no session running")); return; }
        if (!paused) { Say(p, T("not paused")); return; }
        paused = false;
        if (blockEnd != DateTime.MinValue) blockEnd += DateTime.UtcNow - pausedAt;
        SetMain("");
        All(T("Go on."));
        if (drill != null) RunDrill(drill); else NextDrill();
    }

    // after a map change, or when you join the server
    void SessionResume()
    {
        if (sess == null || !Humans().Any()) return;
        if (paused) { SetMain(PausedHtml()); return; }
        if (blockIdx < 0) { Welcome(); AddTimer(4f, NextBlock); return; }
        var b = sess.Blocks[blockIdx];
        if (Server.MapName != b.Map) { ChangeMap(b.Map); return; }
        if (drill != null) RunDrill(drill); else NextDrill();
    }

    void NextBlock()
    {
        if (sess == null) return;
        blockIdx++;
        if (blockIdx >= sess.Blocks.Count) { EndSession(); return; }
        var b = sess.Blocks[blockIdx];
        queue.Clear();
        foreach (var d in b.Drills) queue.AddLast(d);
        blockEnd = DateTime.MinValue;   // the block's clock starts with its first drill (after a map change)
        drill = null;
        if (Server.MapName != b.Map)
        {
            phase = "setup"; cur = null;
            Html($"<font color='#e0a030'>{T("NEXT MAP")}</font><br><font class='fontSize-l'>{MapName(b.Map)}</font>", 4);
            AddTimer(2f, () => ChangeMap(b.Map));
            return;
        }
        NextDrill();
    }

    void NextDrill()
    {
        if (sess == null) return;
        var b = sess.Blocks[blockIdx];
        if (blockEnd == DateTime.MinValue) blockEnd = DateTime.UtcNow.AddSeconds(b.Seconds);
        if (queue.Count == 0 || DateTime.UtcNow > blockEnd) { NextBlock(); return; }
        drill = queue.First!.Value;
        queue.RemoveFirst();
        tries = 0;
        drillNo++;
        RunDrill(drill);
    }

    void RunDrill(Drill d)
    {
        if (sess == null) return;
        sessGen++;
        var pending = false;
        var s = d.Kind switch { "situation" => d.Scenario != null ? PeekSoon(d.Scenario, out pending) : null, "aim" => d.Mode == "range" ? RangeScenario(d) : d.Mode == "crossfire" ? CrossfireScenario(d) : AimScenario(d),
            "nade" => NadeScenario(d), "momentum" => MomentumScenario(d), _ => null };
        if (pending)
        {
            var gp = sessGen;
            AddTimer(0.2f, () => { if (gp == sessGen && drill == d) RunDrill(d); });
            return;
        }
        if (s == null && d.Kind == "situation" && waitFile++ < 20)   // the app is still building it from the demo
        {
            Html($"<font color='#e0a030'>{T(KindName["situation"])}</font><br>{F("loading {title}…", "title", d.Title)}", 2);
            var g = sessGen;
            AddTimer(2f, () => { if (g == sessGen && drill == d) RunDrill(d); });
            return;
        }
        waitFile = 0;
        if (s == null) { Log("drill {id}: nothing to play", d.Id); NextDrill(); return; }
        if (!string.IsNullOrEmpty(s.Lost))
        {   // 07/10: "la situation est perdue d'avance, autant pas me la faire jouer"
            All($"\x10{T(KindName["situation"])}\x01 {d.Title}: {s.Lost} · {T("skipped")}");
            Html($"<font color='#e0a030'>{Shown("skipped")}</font> · {d.Title}<br>{s.Lost}", 3);
            var g2 = sessGen;
            AddTimer(3f, () => { if (g2 == sessGen) NextDrill(); });
            return;
        }
        cur = s;
        // an aim drill's own time on the game's clock (09/10, his defense: "le temps d'en haut finit avant le temps de la
        // situation", 10 s before): the round's clock ends with the drill; a stuff drill keeps its throw's real moment
        if (d.Kind == "aim" && d.Seconds > 0) cur.Clock = d.Seconds;
        else if (d.Kind == "momentum" && d.Seconds > 0) cur.Clock = d.Seconds * 1.5f;   // its last rep starts before 1.5 times its time
        else if (d.Kind != "situation" && d.Clock > 0) cur.Clock = d.Clock + (d.Rush ? rushDelay : 0);   // a rush's wait: its arrival stays on the real clock
        rushIn = -1;
        mode = "actor";
        aimOrder.Clear(); reacts.Clear(); aimHs = 0; aimNext = 0; attempts = 0; nadeWait = false; frags = deaths = plants = 0;
        wave = 0; waveFirstDead = -1; waveDue = false; beaconed.Clear();
        nadePops.Clear();
        if (d.Kind == "nade") ClearNades();
        cameAt.Clear(); strafe.Clear(); lastKill = 0;
        // the targets that must stay still idle: a prefire's, a wallbang's, the aim map's flicks and strafers (06/10)
        Zombie(d.Kind == "aim" && (d.Mode == "prefire" || d.Id.StartsWith("wallbang") || d.Id.StartsWith("boost") || (d.Mode == "range" && d.Variant != "duel")));
        DontShoot(d.Rush || (d.Mode == "crossfire" && d.Variant == "spray"));   // Crossfire's spray: two targets, nothing else   // a rush's runners run their way like a situation's players (driven, not idle), and never fire
        BotStop(false);   // Aim Botz's config stops them (07/10)
        Ammo(d.Kind == "aim");   // 07/10: "chargeur infini dans le sens où ... il faut que je recharge": the reserve never ends
        Intro(d);
        Setup();
    }

    string Left() { var l = blockEnd - DateTime.UtcNow; return l.TotalSeconds > 0 ? $"{(int)l.TotalMinutes}:{l.Seconds:D2}" : T("last"); }

    void Intro(Drill d)
    {
        var how = d.Kind == "situation" && cur != null ? SituationText() : d.Kind != "nade" ? d.Tip : d.Level switch
        {
            0 or 1 when d.Rush => $"{HowClick(d)} — {F("a real rush gets to the blue ring at {t}: your grenade must be up before · it comes at GO", "t", RoundClock(d.RushAt))}",
            _ when d.Rush => T("they rush: your grenade up on its spot in time · it comes at GO"),
            0 or 1 => $"<font color='#ffd34d' class='fontSize-l'>{How(d.How).ToUpper()}</font>{(d.Click != "" ? $" · {How(d.Click)}" : "")}<br>{T("crosshair on the green cross · it must land in the blue ring · stand in the green ring")}",
            _ => $"<font color='#ffd34d' class='fontSize-l'>{How(d.How).ToUpper()}</font>{(d.Click != "" ? $" · {How(d.Click)}" : "")} · {T("find the aim")}",
        };        var again = tries > 0 ? $" · {T("AGAIN")}" : "";
        introHtml = $"<font color='{KindColor[d.Kind]}'>{T(KindName[d.Kind])}{again}</font> · {Left()} · ⭐ {points}<br><font class='fontSize-l'>{d.Title}</font><br>{how}";
        hudFlash = "";
        SetMain(introHtml);
        var plain = System.Text.RegularExpressions.Regex.Replace(how.Replace("<br>", " · "), "<[^>]+>", "");
        All($"\x10{T(KindName[d.Kind])}{again}\x01 {d.Title} — {plain}");
    }

    Scenario AimScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "aim", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Armor = d.Armor, Helmet = d.Helmet, Weapons = d.Weapons,
            Active = d.Weapons.LastOrDefault(), Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], me.Ang[1], me.Ang[0] } });
        if (d.Mode == "defend")   // a few attackers at a time on real hits' ways, with their grenades, then the game's AI
        {
            for (int k = 0; k < Math.Min(d.Alive, Math.Max(d.Bots.Count, d.Tracks.Count)); k++)
            {
                var tr = PickTrack(d, 0);
                var b = d.Bots.Count > 0 ? d.Bots[Rng.Next(d.Bots.Count)] : new Spot();
                s.Players.Add(new Track { Sid = $"att{k}", Name = tr?.Zone ?? b.Zone ?? $"Attacker {k + 1}", Team = 5 - d.Team, Hp = 100, Armor = d.Armor, Helmet = d.Helmet,
                    Weapons = d.BotWeapons, Active = d.BotWeapons.FirstOrDefault(w => w.Contains("ak47") || w.Contains("m4")) ?? d.BotWeapons.LastOrDefault(),
                    Path = tr?.Path ?? new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] }, TrackNades = tr?.Nades ?? new() });
            }
            return s;
        }
        for (int k = 0; k < d.Bots.Count; k++)
        {
            var b = d.Bots[k];
            s.Players.Add(new Track { Sid = $"target{k}", Name = b.Zone ?? $"Target {k + 1}", Team = 5 - d.Team, Hp = 100, Armor = 100, Helmet = true,
                Weapons = d.BotWeapons, Active = d.BotWeapons.LastOrDefault(), Path = new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] }, Hold = true,
                Still = d.Mode == "prefire" || d.Id.StartsWith("wallbang") || d.Id.StartsWith("boost"), Duck = b.Duck });
        }
        if (d.Mate is { } m)   // a boost: the teammate below, still, crouched when the boost was on a crouched one
            s.Players.Add(new Track { Sid = "mate", Name = m.Zone ?? "your boost", Team = d.Team, Hp = 100, Armor = 100, Helmet = true,
                Weapons = d.Weapons, Active = d.Weapons.LastOrDefault(), Path = new[] { m.Pos[0], m.Pos[1], m.Pos[2], m.Ang[1], m.Ang[0] }, Hold = true, Still = true, Duck = m.Duck });
        return s;
    }

    // a defense's attacker: a real hit that walks into the sight of the post you hold (06/10: "les bots n'attaquent pas
    // ma zone"), any of them once you play free
    static EntryTrack? PickTrack(Drill d, int post)
    {
        if (d.Tracks.Count == 0) return null;
        var mine = d.Tracks.Where(t => post < d.Posts.Count ? t.Post == post : t.Post < 0).ToList();
        if (mine.Count == 0) mine = d.Tracks;
        return mine[Rng.Next(mine.Count)];
    }

    // the aim map (06/10, the user: "fais le travail d'aim sur une map d'aim, ensuite lance les maps que j'ai choisies"):
    // you at the middle of your side's spawns, the targets on the other side's, turned to you
    Scenario RangeScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "aim", Title = d.Title, Team = d.Team, Clock = d.Clock };
        List<(Vector3 p, float yaw)> Of(string cls)
        {   // the spawns the game uses (some maps hold a disabled second set)
            var all = Utilities.FindAllEntitiesByDesignerName<SpawnPoint>(cls).Where(e => e.AbsOrigin != null).ToList();
            var on = all.Where(e => e.Enabled).ToList();
            return (on.Count > 0 ? on : all).Select(e => (new Vector3(e.AbsOrigin!.X, e.AbsOrigin.Y, e.AbsOrigin.Z), e.AbsRotation?.Y ?? 0f)).ToList();
        }
        var mineY = Of(d.Team == 2 ? "info_player_terrorist" : "info_player_counterterrorist");
        var theirsY = Of(d.Team == 2 ? "info_player_counterterrorist" : "info_player_terrorist");
        var mine = mineY.Select(x => x.p).ToList();
        rangeTheirs = theirsY.Select(x => x.p).ToList();
        if (d.Map != rangeMap) { rangeBlind.Clear(); rangeMap = d.Map; }
        rangeSeenAt.Clear(); rangeSpots = false;
        var mid = mine.Count > 0 ? new Vector3(mine.Average(p => p.X), mine.Average(p => p.Y), mine.Average(p => p.Z)) : Vector3.Zero;
        var me = mine.Count > 0 ? mine.OrderBy(p => Vector3.Distance(p, mid)).First() : Vector3.Zero;
        var far = rangeTheirs.Count > 0 ? new Vector3(rangeTheirs.Average(p => p.X), rangeTheirs.Average(p => p.Y), rangeTheirs.Average(p => p.Z)) : me + new Vector3(1000, 0, 0);
        var flat = new Vector2(far.X - me.X, far.Y - me.Y).Length();
        var face = flat > 200 ? YawTo(me, far) : mineY.FirstOrDefault(x => Vector3.Distance(x.p, me) < 1f).yaw;   // around you: the map's own way
        if (flat <= 200) far = me + new Vector3(1000 * MathF.Cos(face * MathF.PI / 180), 1000 * MathF.Sin(face * MathF.PI / 180), 0);
        float Off(Vector3 p) => MathF.Abs(((YawTo(me, p) - face) % 360 + 540) % 360 - 180);
        foreach (var cone in d.Variant == "duel" ? new[] { 60f, 90f, 120f, 180f } : new[] { 80f, 100f, 130f, 180f })
        {   // a duel's shooters in front only; enough spots to change places
            var front = rangeTheirs.Where(p => Off(p) <= cone).ToList();
            if (front.Count >= 8 || cone >= 180f) { rangeTheirs = front; break; }
        }
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Armor = 100, Helmet = true, Weapons = d.Weapons,
            Active = d.Weapons.LastOrDefault(), Path = new[] { me.X, me.Y, me.Z, YawTo(me, far), 0f } });
        var order = rangeTheirs.Where(p => !Blind(p)).OrderBy(_ => Rng.Next()).ToList();
        if (order.Count == 0) order = rangeTheirs.OrderBy(_ => Rng.Next()).ToList();
        for (int k = 0; k < Math.Max(1, d.Count); k++)
        {
            var p = order.Count > 0 ? order[k % order.Count] : far;
            s.Players.Add(new Track { Sid = $"target{k}", Name = $"Target {k + 1}", Team = 5 - d.Team, Hp = 100, Armor = 100, Helmet = true,
                Weapons = d.BotWeapons, Active = d.BotWeapons.LastOrDefault(), Path = new[] { p.X, p.Y, p.Z, YawTo(p, me), 0f },
                Hold = d.Variant != "strafe", Still = d.Variant == "flick", Strafe = d.Variant == "strafe" });
        }
        return s;
    }

    static float YawTo(Vector3 a, Vector3 b) => MathF.Atan2(b.Y - a.Y, b.X - a.X) * 180 / MathF.PI;

    // a prefire's bot: its spot in the drill (its track is "target<k>")
    Spot? BotSpot(Track t) => drill != null && int.TryParse(t.Sid.Replace("target", ""), out var k) && k >= 0 && k < drill.Bots.Count ? drill.Bots[k] : null;

    // a target of the aim map down: another one on a free spot of their side, turned to you
    void RangeAgain(int g, int slot)
    {
        if (g != generation || phase != "live" || cur == null || drill == null || !bots.TryGetValue(slot, out var t)) return;
        var c = Utilities.GetPlayerFromSlot(slot);
        if (c == null || !c.IsValid) return;
        var me = Humans().Select(h => h.PlayerPawn.Value?.AbsOrigin).FirstOrDefault(o => o != null) is { } mo ? new Vector3(mo.X, mo.Y, mo.Z) : Pos(cur.Players.First(p => p.Me), 0);
        var taken = bots.Where(b => b.Key != slot && !gone.Contains(b.Value.Sid)).Select(b => Pos(b.Value, 0)).ToList();
        var free_ = rangeTheirs.Where(p => !Blind(p) && taken.All(q => Vector3.Distance(p, q) > 120) && Vector3.Distance(p, Pos(t, 0)) > 120).ToList();
        if (free_.Count == 0) free_ = rangeTheirs.Where(p => !Blind(p)).ToList();
        if (free_.Count == 0) free_ = rangeTheirs;
        var p = free_.Count > 0 ? free_[Rng.Next(free_.Count)] : Pos(t, 0);
        t.Path = new[] { p.X, p.Y, p.Z, YawTo(p, me), 0f };
        c.Respawn();
        Loadout(c, t);
        if (c.PlayerPawn.Value is { } pw) { pw.Teleport(p, new Vector3(0, YawTo(p, me), 0), Vector3.Zero); Freeze(pw, !t.Strafe && t.Hold); }
        gone.Remove(t.Sid);
        contact.Remove(slot);
        strafe.Remove(slot);
        cameAt[slot] = Server.TickCount;
    }

    // the aim map's strafers: left and right across your line, a stop now and then (counter-strafe practice), 200 u
    // around their spot at most, turned to you
    // a target nobody can see from your spot (cover between): moved after 3 s, its spot dropped for the map. Only once a
    // target has been seen this drill (the game's spotting works for these bots: unseen then means hidden)
    void RangeBlindTick()
    {
        var me = Humans().Select(h => h.PlayerPawn.Value).FirstOrDefault(p => p != null && p.IsValid && p.LifeState == (byte)LifeState_t.LIFE_ALIVE);
        if (me == null) return;
        var m = me.EntitySpottedState.SpottedByMask;
        var now = Server.TickCount;
        foreach (var (slot, t) in bots.ToList())
        {
            if (gone.Contains(t.Sid)) continue;
            if ((m[slot / 32] & (1u << (slot % 32))) != 0) { rangeSeenAt[slot] = now; rangeSpots = true; continue; }
            if (!rangeSpots) continue;
            var since = Math.Max(cameAt.GetValueOrDefault(slot, t0), rangeSeenAt.GetValueOrDefault(slot, 0));
            if (now - since < 3 * 64) continue;
            var here = Pos(t, 0);
            if (!Blind(here) && rangeTheirs.Count(q => !Blind(q)) > 4)
            {
                rangeBlind.Add(here);
                Log("range: their spot {s} unseen from yours, dropped ({n} left)", $"{here.X:F0} {here.Y:F0}", rangeTheirs.Count(q => !Blind(q)));
            }
            rangeSeenAt[slot] = now;
            RangeAgain(generation, slot);
        }
    }

    void StrafeTick()
    {
        var mo = Humans().Select(h => h.PlayerPawn.Value?.AbsOrigin).FirstOrDefault(o => o != null);
        if (mo == null) return;
        var me = new Vector3(mo.X, mo.Y, mo.Z);
        foreach (var (slot, t) in bots)
        {
            if (!t.Strafe || gone.Contains(t.Sid)) continue;
            var pw = Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value;
            if (pw?.AbsOrigin is not { } o || pw.LifeState != (byte)LifeState_t.LIFE_ALIVE) continue;
            var here = new Vector3(o.X, o.Y, o.Z);
            var to = new Vector3(me.X - here.X, me.Y - here.Y, 0);
            if (to.Length() < 1) continue;
            var spot = Pos(t, 0);
            if (here.Z < spot.Z - 40)
            {   // off its ledge (Aim Botz's walkways are narrow, 08/10): back on its spot, going the other way
                pw.Teleport(spot, new Vector3(0, MathF.Atan2(to.Y, to.X) * 180 / MathF.PI, 0), Vector3.Zero);
                strafe[slot] = (strafe.TryGetValue(slot, out var was) && was.sign != 0 ? -was.sign : 1, Server.TickCount + Rng.Next(20, 50));
                continue;
            }
            var side = Vector3.Normalize(new Vector3(-to.Y, to.X, 0));
            var off = Vector3.Dot(here - Pos(t, 0), side);
            (int sign, int until) st = strafe.TryGetValue(slot, out var s0) ? s0 : (Rng.Next(2) * 2 - 1, Server.TickCount + Rng.Next(20, 50));
            if (Math.Abs(off) > 200 && Math.Sign(off) == st.sign) st = (-st.sign, Server.TickCount + Rng.Next(20, 50));
            else if (Server.TickCount >= st.until)
                st = st.sign != 0 && Rng.Next(4) == 0 ? (0, Server.TickCount + Rng.Next(12, 30)) : (st.sign == 0 ? Rng.Next(2) * 2 - 1 : -st.sign, Server.TickCount + Rng.Next(20, 56));
            strafe[slot] = st;
            var v = side * (st.sign * 230f);
            var yaw = MathF.Atan2(to.Y, to.X) * 180 / MathF.PI;
            pw.Teleport(null, new Vector3(0, yaw, 0), new Vector3(v.X, v.Y, pw.AbsVelocity?.Z ?? 0f));
            HoldAim(pw, new Vector3(0, yaw, 0), false);
        }
    }

    // a situation: what to do, your route in the match, who got you and from where
    // the essentials only (06/10, the user: "moins d'infos écrites, que l'essentiel, pour nous pousser à les lire"): the
    // goal, how many on each side and where your dead allies fell (red crosses on the ground), the bomb, who got you
    string SituationText()
    {
        var mine = cur?.Players.FirstOrDefault(p => p.Me);
        var lines = new List<string> { string.IsNullOrEmpty(cur?.Goal) ? T("survive") : cur!.Goal };
        if (mine != null && cur != null)
        {
            var al = cur.Players.Count(p => p.Team == mine.Team);
            var en = cur.Players.Count(p => p.Team != mine.Team);
            var dead = cur.Dead.Where(x => x.Team == mine.Team && x.At != "").Select(x => x.At).Distinct().ToList();
            lines.Add($"{al}v{en}{(dead.Count > 0 ? $" · {F("allies dead: {where} (red crosses)", "where", string.Join(", ", dead))}" : "")}");
        }
        if (!string.IsNullOrEmpty(cur?.Plant)) lines.Add($"💣 {cur!.Plant}");   // planted or not: what you have to do (04/10)
        if (!string.IsNullOrEmpty(cur?.Danger)) lines.Add($"⚠ {cur!.Danger}");
        if (!string.IsNullOrEmpty(cur?.ZoneName) || cur?.ZonePoly.Count >= 3)
            lines.Add("🔵 " + (string.IsNullOrEmpty(cur!.ZoneName) ? T("it happens in the blue zone: play it your way") : F("it happens in {zone} (blue): play it your way", "zone", cur.ZoneName)));
        return string.Join("<br>", lines);
    }

    Scenario NadeScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "nade", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        float pitch = me.Ang[0], yaw = me.Ang[1];
        if (d.Level >= 1) { yaw += (float)(Rng.NextDouble() * 120 - 60); pitch = 0; }   // the spot, not the aim
        // a timing smoke: the grenade comes at GO (none thrown during the countdown, the runners still)
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Weapons = d.Rush ? new() { "weapon_knife" } : new() { "weapon_knife", d.Item },
            Active = d.Rush ? "weapon_knife" : d.Item, Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], yaw, pitch } });
        if (d.Rush)
        {   // the real rush's runners, on their way at their pace (07/10)
            s.Step = Math.Max(1, d.Step);
            rushDelay = Math.Max(0, 2 - d.Level);
            var w = d.BotWeapons.Count > 0 ? d.BotWeapons : new() { "weapon_knife", d.Team == 3 ? "weapon_ak47" : "weapon_m4a1" };
            for (int k = 0; k < d.Tracks.Count; k++)
                s.Players.Add(new Track { Sid = $"rush{k}", Name = d.Tracks[k].Zone, Team = 5 - d.Team, Hp = 100, Armor = 100, Helmet = true,
                    Weapons = w, Active = w.Last(), Path = d.Tracks[k].Path, Runner = true, Start = rushDelay * 64f / s.Step });
        }
        return s;
    }

    // Place() is done: the aim targets but the first wait (dead) for their turn
    void SessionPlaced()
    {
        if (cur is { Kind: "death" or "clutch" } && cur.Line.Count > 1) DrawLine(cur.Line);   // your way in the match, up to the zone
        if (cur is { Kind: "death" or "clutch" }) DrawZone(cur);
        if (cur is { Kind: "death" or "clutch" })   // the allies dead before it: where they fell
            foreach (var x in cur.Dead.Where(x => x.Team == cur.Team && x.Pos.Length >= 3)) DrawX(new Vector3(x.Pos[0], x.Pos[1], x.Pos[2]));
        if (sess == null || cur == null) return;
        if (drill?.Mode == "prefire" && drill.Line.Count > 1) DrawLine(drill.Line);
        if (cur.Kind == "momentum") MoPlaced();
        else if (cur.Kind == "aim" && drill?.Mode == "crossfire") CfPlaced();
        else if (cur.Kind == "aim" && drill?.Mode == "range")
        {
            aimOrder.Clear();
            aimOrder.AddRange(bots.Keys);
            foreach (var sl in bots.Keys) cameAt[sl] = Server.TickCount + 3 * 64;
        }
        else if (cur.Kind == "aim" && drill?.Mode is "prefire" or "defend")
        {
            aimOrder.Clear();
            aimOrder.AddRange(bots.Keys);
            peekAt.Clear();
            lineAt = 0; lastPeek = Server.TickCount;
            if (drill.Mode == "prefire")   // the ones that peek later wait, hidden, for their turn (07/10: one after the other, in the
                foreach (var (slot, t) in bots)   // order your way shows them, not three at once in front of you)
                {
                    var b = BotSpot(t);
                    var ordered = drill.Bots.Any(x => x.Seq >= 0);
                    var at = b?.At ?? 0f;
                    if (ordered ? (b == null || b.Seq > 0 || b.Li > 1 || at > 0.3f) : at > 0.3f)
                    { peekAt[slot] = at; Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.CommitSuicide(false, true); }
                }
        }
        else if (cur.Kind == "aim")
        {
            aimOrder.Clear();
            aimOrder.AddRange(bots.Where(b => b.Value.Team != cur.Team).Select(b => b.Key).OrderBy(_ => Rng.Next()));
            for (int k = 1; k < aimOrder.Count; k++) Utilities.GetPlayerFromSlot(aimOrder[k])?.PlayerPawn.Value?.CommitSuicide(false, true);
            aimNext = 1;
            // you start turned to the first target
            if (aimOrder.Count > 0 && bots.TryGetValue(aimOrder[0], out var first))
            {
                var me = cur.Players.First(p => p.Me);
                var d = Pos(first, 0) - Pos(me, 0);
                var yaw = MathF.Atan2(d.Y, d.X) * 180 / MathF.PI;
                foreach (var h in Humans()) h.PlayerPawn.Value?.Teleport(Pos(me, 0), new Vector3(0, yaw, 0), Vector3.Zero);
            }
        }
        if (cur.Kind == "nade") { nadeWait = true; attemptEnd = DateTime.UtcNow.AddSeconds(30); }   // a throw during the countdown counts
        Prac(cur.Kind == "nade");
        nadeStage = cur.Kind == "nade" ? "throw" : "";
        if (cur.Kind == "nade" && drill?.Target is { Length: >= 2 } tg && drill.Me != null)
        {
            ClearLine();
            var r = drill.Type switch { "flash" or "he" or "molotov" => 120f, _ => 80f };   // the PERFECT zone
            // a flash pops in the air: its ring would float; the beam then stands from your feet's height
            DrawMark(tg[0], tg[1], drill.Me.Pos[2], tg.Length >= 3 && drill.Type != "flash" ? tg[2] : null, r);
            DrawStand(drill.Me);
            if (drill.Level <= 1) DrawCross(drill);   // 06/10: "il manque de repères, je n'ai aucun repère visuel"
            // the doors in its way open, as for the player who threw it (04/10: the HE through Squeaky hit the closed door)
            var from = new Vector3(drill.Me.Pos[0], drill.Me.Pos[1], drill.Me.Pos[2] + 64);
            var to = new Vector3(tg[0], tg[1], tg.Length >= 3 ? tg[2] : drill.Me.Pos[2]);
            var steps = Math.Max(1, (int)(Vector3.Distance(from, to) / 48));
            OpenDoors(Enumerable.Range(0, steps + 1).Select(k => Vector3.Lerp(from, to, k / (float)steps)), 128f);
        }
    }

    // the countdown of a drill keeps its card on screen; false: not in a session
    bool SessionCount(int n)
    {
        if (sess == null || drill == null) return false;
        SetMain($"{introHtml}<br><font class='fontSize-xl'>{n}</font>");
        return true;
    }

    void SessionGo()
    {
        if (sess == null || cur == null) return;
        aimSpawn = Server.TickCount;
        lastHud = Server.TickCount;
        if (cur.Kind == "aim" && string.IsNullOrEmpty(drill?.Mode)) AimCard();
        if (drill?.Mode == "prefire") { Html($"<font color='#ff8a3d'>{T("GO")}</font> · {F("clear {n}", "n", aimOrder.Count)} · {drill.Seconds} s", 2); preKillAt = Server.TickCount; }
        if (drill?.Mode == "range") { Html($"<font color='#ff8a3d'>{T("GO")}</font> · {Tn(drill.Goal, "{n} kill", "{n} kills")} · {drill.Seconds} s", 2); lastKill = Server.TickCount; foreach (var sl in bots.Keys) cameAt[sl] = Server.TickCount; }
        if (drill?.Mode == "crossfire") CfGo();
        if (drill?.Mode == "momentum") MoGo();
        if (drill?.Mode == "defend") { postIdx = -1; Html($"<font color='#ff8a3d'>{T("HOLD")}</font> · {drill.Seconds} s · {T("they are coming")}", 2); }
        if (drill is { Rush: true })
        {
            foreach (var h in Humans())
            {
                if (!h.PawnIsAlive) continue;
                h.GiveNamedItem(drill.Item);
                h.ExecuteClientCommandFromServer($"use {drill.Item}");
            }
            Html($"<font color='#ff5a5a'>{T("THEY RUSH")}</font>{(drill.Level < 2 ? $" · {F("there at {t}", "t", RoundClock(drill.RushAt))}" : "")}", 2);
        }
    }

    static string RoundClock(float t) { var l = (int)Math.Max(0, 115 - t); return $"{l / 60}:{l % 60:D2}"; }

    // a timing smoke: the first runner on its spot before it is up: late (07/10)
    void RushCheck()
    {
        if (drill is not { Rush: true } || cur == null || rushIn >= 0 || drill.Target is not { Length: >= 2 } tg) return;
        foreach (var (slot, t) in bots)
        {
            if (t.Team == cur.Team) continue;
            var o = Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.AbsOrigin;
            if (o == null) continue;
            var dz = tg.Length >= 3 ? Math.Abs(o.Z - tg[2]) : 0f;
            if (MathF.Sqrt((o.X - tg[0]) * (o.X - tg[0]) + (o.Y - tg[1]) * (o.Y - tg[1])) > 240f || dz > 160f) continue;
            rushIn = Server.TickCount;
            Log("rush: {n} on the spot at {s:F1} s", t.Name, (rushIn - t0) / 64.0);
            if (!nadeWait) return;   // up already (scored at its pop)
            nadeWait = false;
            DrillDone(false, "late", 0, F("{who} got there before your grenade", "who", t.Name));
            return;
        }
    }

    // a defense in turns: each spot to hold for its share of the time (marked on the ground, you are put on it), then free
    // (04/10: "a specific work on positions: backsite is my job, then that one, then free")
    void DefendPost(float el)
    {
        if (drill == null || cur == null || drill.Posts.Count == 0) return;
        var n = drill.Posts.Count + 1;
        var ph = Math.Min(n - 1, (int)(el / (drill.Seconds / (float)n)));
        if (ph == postIdx) return;
        var moved = postIdx >= 0;   // not the drill's start
        postIdx = ph;
        ClearLine();
        if (moved) NewWave();   // the next post's attackers, all at once (the last ones walked to the post you left)
        if (ph >= drill.Posts.Count)
        {   // 09/10, his defense video: "téléporte-moi sur le bombsite quand je suis en free pour vraiment montrer un
            // changement": back on the site (the drill's start), turned the way they come, refilled like at a post
            var me0 = cur.Players.FirstOrDefault(t => t.Me);
            if (drill.Me is { } site)
                foreach (var h in Humans())
                    if (h.PawnIsAlive && h.PlayerPawn.Value is { } pw0)
                    {
                        pw0.Teleport(new Vector3(site.Pos[0], site.Pos[1], site.Pos[2]), new Vector3(0, site.Ang[1], 0), Vector3.Zero);
                        if (me0 != null) Loadout(h, me0, 100);
                    }
            Html($"<font color='#4fc3a1'>{T("FREE")}</font> · {T("on the site: play it where you want")}", 3);
            return;
        }
        var p = drill.Posts[ph];
        var at = new Vector3(p.Pos[0], p.Pos[1], p.Pos[2]);
        var green = System.Drawing.Color.FromArgb(255, 79, 195, 161);
        // its corners on the post's floor, a thin line: one corner taken on a box top drew a line through the air at eye
        // height (09/10, Mirage's Van: "est-ce que les lignes ne gênent pas la vue ? typiquement là, ça gêne")
        float Floor(float z) => Math.Clamp(z, p.Pos[2] - 48f, p.Pos[2] + 8f) + 4f;
        if (p.Poly.Count >= 3)   // the place's own shape (06/10: "si c'est Garage, prends tout le Garage")
            for (int i = 0; i < p.Poly.Count; i++)
            {
                var a = p.Poly[i]; var b = p.Poly[(i + 1) % p.Poly.Count];
                Beam(new Vector3(a[0], a[1], Floor(a[2])), new Vector3(b[0], b[1], Floor(b[2])), green, 2f);
            }
        else
            for (int i = 0; i < 16; i++)
            {
                float a0 = i * MathF.PI / 8, a1 = (i + 1) * MathF.PI / 8;
                Beam(at + new Vector3(40 * MathF.Cos(a0), 40 * MathF.Sin(a0), 4), at + new Vector3(40 * MathF.Cos(a1), 40 * MathF.Sin(a1), 4), green, 2f);
            }
        var meT = cur.Players.FirstOrDefault(t => t.Me);
        foreach (var h in Humans())
            if (h.PawnIsAlive && h.PlayerPawn.Value is { } pw)
            {
                pw.Teleport(at, new Vector3(0, p.Ang[1], 0), Vector3.Zero);
                if (meT != null) Loadout(h, meT, 100);
            }
        Html($"<font color='#4fc3a1'>{F("HOLD {zone}", "zone", p.Zone)}</font> · {F("{i}/{n}, then free", "i", ph + 1, "n", drill.Posts.Count)}", 3);
    }

    // out of the place you hold (its outline drawn on the ground): the panel says to go back in it
    bool OutOfPost()
    {
        if (drill == null || postIdx < 0 || postIdx >= drill.Posts.Count) return false;
        var poly = drill.Posts[postIdx].Poly;
        if (poly.Count < 3) return false;
        var o = Humans().Where(h => h.PawnIsAlive).Select(h => h.PlayerPawn.Value?.AbsOrigin).FirstOrDefault(v => v != null);
        if (o == null) return false;
        bool inside = false;
        for (int i = 0, j = poly.Count - 1; i < poly.Count; j = i++)   // ray casting on the ground
            if ((poly[i][1] > o.Y) != (poly[j][1] > o.Y) && o.X < (poly[j][0] - poly[i][0]) * (o.Y - poly[i][1]) / (poly[j][1] - poly[i][1]) + poly[i][0])
                inside = !inside;
        return !inside;
    }

    // where you come back in a defense: the spot you hold, or the site's
    Vector3 DefendSpot() => drill != null && postIdx >= 0 && postIdx < drill.Posts.Count
        ? new Vector3(drill.Posts[postIdx].Pos[0], drill.Posts[postIdx].Pos[1], drill.Posts[postIdx].Pos[2])
        : Pos(cur!.Players.First(p => p.Me), 0);

    void SessionTick()
    {
        if (sess == null || cur == null || phase != "live") return;
        // dead without the drill knowing it (killed before GO: OnDeath only counts live deaths; 06/10, a minute on the
        // floor while the aim drill's targets came and went): the drill ends as dead, its retry puts you back on your spot
        if (drill?.Mode is not ("defend" or "range" or "crossfire" or "momentum") && !humanDead && Humans().Any() && Humans().All(h => !h.PawnIsAlive)) { Finish("dead"); return; }
        var el = (Server.TickCount - t0) / 64f;
        if (drill?.Mode == "crossfire") { CfTick(el); return; }
        if (drill?.Mode == "momentum") { MoTick(el); return; }
        if (drill?.Mode == "range")
        {
            if (el >= drill.Seconds || frags >= drill.Goal * 2) { Finish(frags >= drill.Goal ? "cleared" : "done"); return; }
            if (drill.Variant == "strafe") StrafeTick();
            RangeBlindTick();
            var avg = reacts.Count > 0 ? $" · {reacts.Average():F2} s" : "";
            var hs = frags > 0 ? $" · {100 * aimHs / frags}% HS" : "";
            SetMain($"<font color='#ff8a3d'>{drill.Title}</font> · ⚔ {frags}/{drill.Goal}{avg}{hs} · {(int)(drill.Seconds - el)} s"
                    + $"<br><font class='fontSize-s'>{drill.Tip}</font>");
            return;
        }
        if (drill?.Mode is "prefire" or "defend")
        {
            if (el >= drill.Seconds) { Finish(drill.Mode == "prefire" ? "timeout" : "done"); return; }
            if (drill.Mode == "defend") DefendPost(el);
            // a hidden one peeks at its time, or when you come near its spot (not after you passed it); the last two
            // all peek
            var mo = Humans().Select(h => h.PlayerPawn.Value?.AbsOrigin).FirstOrDefault(o => o != null);
            var mp = mo == null ? (Vector3?)null : new Vector3(mo.X, mo.Y, mo.Z);
            var fewLeft = drill.Mode == "prefire" && aimOrder.Count - frags <= 2;
            bool Near(int sl) => mp != null && bots.TryGetValue(sl, out var tt) && Vector3.Distance(Pos(tt, 0), mp.Value) < 1100;
            var ordered = drill.Mode == "prefire" && drill.Bots.Any(x => x.Seq >= 0);
            if (ordered && mp != null && drill.Line.Count > 1)
            {   // how far along the line you got: its nearest point within 300 u (same floor), never back
                for (int k = lineAt; k < drill.Line.Count; k++)
                {
                    var q = drill.Line[k];
                    if (MathF.Abs(q[2] - mp.Value.Z) < 120 && new Vector2(q[0] - mp.Value.X, q[1] - mp.Value.Y).Length() < 300) lineAt = Math.Max(lineAt, k);
                }
            }
            IEnumerable<int> due;
            if (ordered)
            {   // the next one in the way's order: at its time, or when you reach the line where it's seen; never two at once
                var next = peekAt.Keys.Select(sl => (sl, b: bots.TryGetValue(sl, out var tt) ? BotSpot(tt) : null)).Where(x => x.b != null)
                    .OrderBy(x => x.b!.Seq).FirstOrDefault();
                var ready = next.b != null && Server.TickCount - lastPeek >= 48 && (next.b.At <= el || lineAt >= next.b.Li - 1 || fewLeft);
                due = ready ? new[] { next.sl } : Array.Empty<int>();
            }
            else due = peekAt.Where(kv => kv.Value <= el || fewLeft || Near(kv.Key)).Select(kv => kv.Key).ToList();
            foreach (var slot in due.ToList())
            {   // its time: it peeks
                lastPeek = Server.TickCount;
                peekAt.Remove(slot);
                if (!bots.TryGetValue(slot, out var t)) continue;
                var c = Utilities.GetPlayerFromSlot(slot);
                if (c == null || !c.IsValid) continue;
                c.Respawn();
                Loadout(c, t);
                if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, true); }
                gone.Remove(t.Sid);
            }
            // the last ones not found in 8 s since your last kill: an orange post over each (09/10: one held Lower Tunnels,
            // behind the way, 37 s to find it: "et je ne trouve pas les derniers")
            if (drill.Mode == "prefire" && aimOrder.Count - frags <= 2 && Server.TickCount - preKillAt > 8 * 64) Beacons();
            {
                var left = (int)(drill.Seconds - el);
                var n = aimOrder.Count - frags;
                var where = drill.Mode == "prefire" && n <= 3 ? LeftPlaces() : "";
                SetMain(drill.Mode == "prefire"
                    ? $"<font color='#ff8a3d'>{drill.Title}</font> · {(where != "" ? F("{n} left: {where}", "n", n, "where", where) : F("{n} left", "n", n))}{(beaconed.Count > 0 ? $" ({T("orange posts")})" : "")}"
                      + $" · {left} s<br><font class='fontSize-s'>{string.Join(" → ", drill.Route)} · {T("follow the gold line")}</font>"
                    : $"<font color='#ff8a3d'>{drill.Title}</font> · {left} s · ⚔ {frags} · ☠ {deaths}"
                      + (drill.Posts.Count == 0 || postIdx < 0 ? "" : postIdx < drill.Posts.Count
                          ? (OutOfPost() ? $"<br><font color='#ff5a5a'>⚠ {F("back in {zone} (the green zone)", "zone", drill.Posts[postIdx].Zone)}</font>"
                                         : $"<br><font class='fontSize-s'>{F("hold {zone} (the green zone)", "zone", drill.Posts[postIdx].Zone)}</font>")
                          : $"<br><font class='fontSize-s'>{T("free")}</font>"));
            }
            return;
        }
        if (cur.Kind is "death" or "clutch")   // the drill's line and the next place of your route in the match
        {
            var me = cur.Players.FirstOrDefault(p => p.Me);
            var fr = (Server.TickCount - t0) / (float)cur.Step;
            var next = me?.Places.Select(p => (at: p[0].GetInt32(), nm: p[1].GetString())).Where(p => p.at > fr + 8).Select(p => p.nm).FirstOrDefault();
            var bomb = "";
            if (bombLive)   // the bomb's clock, and what it asks of you
                foreach (var c4 in Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4"))
                    bomb = $"<br><font color='#ff5a5a'>💣 {(c4.BombSite == 1 ? "B" : "A")} · {Math.Max(0, c4.C4Blow - Server.CurrentTime):F0} s</font> · {(cur.Team == 3 ? T("defuse it") : T("keep it ticking"))}";
            var way = cur.Line.Count > 1 ? T("the gold line takes you to the blue zone") : T("your route in the match");
            SetMain($"<font color='#e0a030'>{drill?.Title}</font>{bomb}{(next != null ? $"<br>→ {next} <font class='fontSize-s'>({way})</font>" : "")}");
        }
        if (cur.Kind == "aim" && string.IsNullOrEmpty(drill?.Mode))
            SetMain($"<font color='#ff8a3d'>{drill?.Title}</font> · {F("target {i}/{n}", "i", Math.Max(1, aimNext), "n", aimOrder.Count)}");
        if (cur.Kind == "nade" && drill != null)
            SetMain($"<font color='#5ab4ff'>{drill.Title}</font> · {(drill.Rush ? (drill.Level < 2 ? F("they get there at {t}", "t", RoundClock(drill.RushAt)) : T("in time")) : F("throw {i}/3", "i", Math.Min(3, attempts + 1)))}"
                    + $"<br><font class='fontSize-s'>{(drill.Level < 2 ? HowClick(drill) : T("find the aim and the throw"))}</font>");
        // a target not found in 12 s goes away (missed), the next one comes
        if (cur.Kind == "aim" && aimSpawn > 0 && Server.TickCount - aimSpawn > 12 * 64)
        {
            aimSpawn = 0;
            var slot = aimOrder.ElementAtOrDefault(aimNext - 1);
            Html($"<font color='#ff5a5a'>{T("MISSED")}</font> · {T("next one")}", 1);
            Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.CommitSuicide(false, true);
        }
        if (cur.Kind == "aim" && Server.TickCount - t0 > 120 * 64) Finish("timeout");
        if (cur.Kind == "nade" && nadeWait && DateTime.UtcNow > attemptEnd) NadeResult(double.NaN);
        if (cur.Kind == "nade") RushCheck();
    }

    // true: handled here (a defense: you come back instead of the drill ending)
    bool SessionDeath(EventPlayerDeath e, CCSPlayerController? v)
    {
        if (sess == null || cur?.Kind != "aim" || drill == null || v == null) return false;
        if (drill.Mode == "crossfire") return CfDeath(e, v);
        if (drill.Mode == "prefire")
        {
            if (!v.IsBot) return false;
            if (e.Attacker is { IsValid: true, IsBot: false }) { frags++; if (e.Headshot) aimHs++; preKillAt = Server.TickCount; }
            if (peekAt.ContainsKey(v.Slot)) return false;   // a hidden one going to wait for its timing
            var left = bots.Count(b => !gone.Contains(b.Value.Sid) && b.Key != v.Slot) + peekAt.Count;
            if (left == 0) AddTimer(0.3f, () => Finish("cleared"));
            else Html($"<font color='#ff8a3d'>{F("{n} left", "n", left)}</font>{(e.Headshot ? " · HS" : "")}", 1);
            return false;
        }
        if (drill.Mode == "range")
        {
            var g = generation;
            if (!v.IsBot)   // a duel lost: back on your spot in 1 s
            {
                deaths++;
                AddTimer(1f, () =>
                {
                    if (g != generation || phase != "live" || cur == null) return;
                    var me = cur.Players.First(p => p.Me);
                    protectUntil = Server.TickCount + 64;
                    foreach (var h in Humans()) { h.Respawn(); Loadout(h, me); h.PlayerPawn.Value?.Teleport(Pos(me, 0), Upright(Ang(me, 0)), Vector3.Zero); }
                });
                return true;
            }
            if (e.Attacker is { IsValid: true, IsBot: false })
            {
                frags++;
                if (e.Headshot) aimHs++;
                var now = Server.TickCount;   // from the later of its coming and your last kill: the time to find it and kill it
                reacts.Add((now - Math.Max(lastKill, cameAt.GetValueOrDefault(v.Slot, t0))) / 64.0);
                lastKill = now;
            }
            var sl0 = v.Slot;
            AddTimer(drill.Variant == "flick" ? 0.25f + (float)Rng.NextDouble() * 0.45f : 0.6f + (float)Rng.NextDouble() * 0.6f, () => RangeAgain(g, sl0));
            return false;
        }
        if (drill.Mode == "defend")
        {
            var g = generation;
            if (!v.IsBot)   // you: back on the spot in 1.5 s, out of reach for 2 s
            {
                deaths++;
                AddTimer(1.5f, () =>
                {
                    if (g != generation || phase != "live" || cur == null) return;
                    var me = cur.Players.First(p => p.Me);
                    var spot = DefendSpot();
                    // the wave that got you goes, a new one comes from the entrances, all of it at once (09/10): no death
                    // the moment you are back (04/10, "the spawn kill problem is very annoying"), nobody already in front
                    // of you (09/10 on Fachwerk's Long A: "pareil je spawn devant eux")
                    NewWave();
                    protectUntil = Server.TickCount + 2 * 64;
                    var face = postIdx >= 0 && postIdx < drill.Posts.Count ? new Vector3(0, drill.Posts[postIdx].Ang[1], 0) : Upright(Ang(me, 0));
                    foreach (var h in Humans()) { h.Respawn(); Loadout(h, me); h.PlayerPawn.Value?.Teleport(spot, face, Vector3.Zero); }
                });
                return true;
            }
            if (e.Attacker is { IsValid: true, IsBot: false }) { frags++; if (e.Headshot) aimHs++; }
            AddTimer(0.1f, () => WaveCheck(g));   // the next ones once this wave is down
            return false;
        }
        if (!v.IsBot) return false;
        if (e.Attacker is { IsValid: true, IsBot: false } && aimSpawn > 0)
        {
            reacts.Add((Server.TickCount - aimSpawn) / 64.0);
            if (e.Headshot) aimHs++;
            Html($"<font color='#ff8a3d'>{T("HIT")}</font> {reacts[^1]:F2} s{(e.Headshot ? " · HS" : "")} · {reacts.Count}/{aimOrder.Count}", 1);
        }
        aimSpawn = 0;
        if (aimNext < aimOrder.Count)
        {
            var slot = aimOrder[aimNext++];
            var g = generation;
            AddTimer(0.4f + (float)Rng.NextDouble() * 1.2f, () =>
            {
                if (g != generation || phase != "live" || !bots.TryGetValue(slot, out var t)) return;
                var c = Utilities.GetPlayerFromSlot(slot);
                if (c == null || !c.IsValid) return;
                c.Respawn();
                Loadout(c, t);
                if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, true); }
                gone.Remove(t.Sid);
                free.Remove(slot);
                aimSpawn = Server.TickCount;
                AimCard();
            });
        }
        else AddTimer(0.4f, () => Finish(reacts.Count == aimOrder.Count ? "cleared" : "done"));
        return false;
    }

    // a prefire's bots still up and out (not waiting for their turn): an orange post over each, once
    void Beacons()
    {
        var orange = System.Drawing.Color.FromArgb(255, 255, 140, 40);
        foreach (var (sl, t) in bots)
        {
            if (beaconed.Contains(sl) || peekAt.ContainsKey(sl) || gone.Contains(t.Sid) || !Up(sl)) continue;
            beaconed.Add(sl);
            var p = Pos(t, 0);
            Beam(p + new Vector3(0, 0, 80), p + new Vector3(0, 0, 400), orange, 4f);
        }
    }

    // a defense's attackers come in waves (09/10, his Dust2 A: "il y a 3 bots en vie théoriquement, et j'en croise très
    // rarement 3 en même temps"): one walking in as another one died, they came one by one. Now all of a wave start
    // together on real ways (their tracks start the same time before they come into sight) and the next wave comes once
    // this one is down; one of them staying away from the fight (it has not seen you for 4 s) 10 s after the wave's first
    // death is taken off.
    IEnumerable<int> Attackers() => cur == null ? Enumerable.Empty<int>() : bots.Where(b => b.Value.Team != cur.Team).Select(b => b.Key).ToList();
    static bool Up(int sl) => Utilities.GetPlayerFromSlot(sl) is { IsValid: true, PawnIsAlive: true };

    // the attackers still up go (your death, another post): their deaths call the next wave
    void NewWave()
    {
        var up = Attackers().Where(Up).ToList();
        if (up.Count == 0) { WaveCheck(generation); return; }
        foreach (var sl in up) Utilities.GetPlayerFromSlot(sl)?.PlayerPawn.Value?.CommitSuicide(false, true);
    }

    void WaveCheck(int g)
    {
        if (g != generation || phase != "live" || cur == null || drill?.Mode != "defend" || waveDue) return;
        if (!Attackers().Any(Up))
        {
            waveDue = true;
            var w = wave;
            AddTimer(1.2f + (float)Rng.NextDouble() * 0.8f, () => { if (g == generation && w == wave) StartWave(g); });
            return;
        }
        if (waveFirstDead < 0)
        {
            waveFirstDead = Server.TickCount;
            var w = wave;
            AddTimer(10f, () => WaveStale(g, w));
        }
    }

    void WaveStale(int g, int w)
    {
        if (g != generation || w != wave || waveDue || phase != "live" || cur == null) return;
        var now = Server.TickCount;
        var up = Attackers().Where(Up).ToList();
        if (up.Count == 0) { WaveCheck(g); return; }
        if (up.All(sl => now - sawYou.GetValueOrDefault(sl, -100000) > 4 * 64))
        {   // nobody of it in the fight any more: taken off, the next wave comes
            Log("wave {w}: {n} away from the fight, taken off", wave, up.Count);
            foreach (var sl in up) Utilities.GetPlayerFromSlot(sl)?.PlayerPawn.Value?.CommitSuicide(false, true);
            return;
        }
        AddTimer(2f, () => WaveStale(g, w));   // still fighting: wait
    }

    void StartWave(int g)
    {
        if (g != generation || phase != "live" || cur == null || drill == null) return;
        wave++; waveDue = false; waveFirstDead = -1;
        var start = (Server.TickCount - t0) / (float)cur.Step;   // the same for all: they come into sight together
        var n = 0;
        foreach (var sl in Attackers())
            if (Utilities.GetPlayerFromSlot(sl) is { IsValid: true } c && !c.PawnIsAlive && bots.TryGetValue(sl, out var t)) { Attacker(c, t, start); n++; }
        Log("wave {w}: {n} attackers", wave, n);
    }

    // one of the wave: a real hit on the site walked from now with its grenades (it fights once it sees you), or the game's
    // AI from an entrance not right next to you
    void Attacker(CCSPlayerController c, Track t, float start)
    {
        if (cur == null || drill == null) return;
        var slot = c.Slot;
        c.Respawn();
        Loadout(c, t);
        string? zone;
        if (drill.Tracks.Count > 0)
        {
            var tr = PickTrack(drill, postIdx < 0 ? 0 : postIdx)!;
            t.Path = tr.Path;
            t.TrackNades = tr.Nades;
            t.NadeNext = 0;
            t.Start = start;
            zone = tr.Zone;
            free.Remove(slot);
            contact.Remove(slot);
            engaged.Remove(slot);
            if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, false); }   // it walks its way
        }
        else
        {
            var me = Pos(cur.Players.First(p => p.Me), 0);
            var far = drill.Bots.Where(b => Vector3.Distance(new Vector3(b.Pos[0], b.Pos[1], b.Pos[2]), me) > 600).ToList();
            if (far.Count == 0) far = drill.Bots;
            var sp = far[Rng.Next(far.Count)];
            zone = sp.Zone;
            c.PlayerPawn.Value?.Teleport(new Vector3(sp.Pos[0], sp.Pos[1], sp.Pos[2]), new Vector3(0, sp.Ang[1], 0), Vector3.Zero);
        }
        if (zone != null) { c.PlayerName = zone; Utilities.SetStateChanged(c, "CBasePlayerController", "m_iszPlayerName"); }
        gone.Remove(t.Sid);
    }

    // a defense: a bomb planted is taken away (and costs points)
    void BombPlanted()
    {
        if (sess == null || drill?.Mode != "defend" || phase != "live") return;
        plants++;
        Html($"<font color='#ff5a5a'>{T("PLANTED")}</font> · −60", 2);
        AddTimer(0.2f, () => { foreach (var c4 in Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4")) c4.Remove(); });
    }

    // which target, where to look
    void AimCard()
    {
        var slot = aimOrder.ElementAtOrDefault(aimNext - 1);
        var where = bots.TryGetValue(slot, out var t) ? t.Name : "";
        Html($"<font color='#ff8a3d'>{F("TARGET {i}/{n}", "i", aimNext, "n", aimOrder.Count)}</font> → <font class='fontSize-l'>{where}</font>", 2);
    }

    void NadeHit(CCSPlayerController? u, float x, float y)
    {
        if (sess != null && cur?.Kind == "nade" && u is { IsValid: true, IsBot: false })
        {
            if (cam != null) camEnd = Math.Min(camEnd, Server.TickCount + 64);   // the camera stays 1 s on it
            if (nadeStage == "theirs") { TheirsPopped(); return; }
        }
        if (sess == null || drill == null || cur?.Kind != "nade" || phase is not ("live" or "countdown") || !nadeWait || u == null || !u.IsValid || u.IsBot) return;
        var tg = drill.Target;
        if (tg == null || tg.Length < 2) return;
        nadePops.Add(new[] { (float)Math.Round(x), (float)Math.Round(y) });
        NadeResult(Math.Sqrt((x - tg[0]) * (x - tg[0]) + (y - tg[1]) * (y - tg[1])));
    }

    // a throw landed (dist from the spot of the pros' throws) or 25 s without one (NaN)
    void NadeResult(double dist)
    {
        if (drill == null) return;
        attempts++;
        // a flash or an HE pops in the air, a molotov's fire spreads: wider than a smoke
        var (ok1, ok2) = drill.Type switch { "flash" or "he" => (120, 260), "molotov" => (120, 240), _ => (80, 180) };
        var q = double.IsNaN(dist) ? "no throw" : dist <= ok1 ? "perfect" : dist <= ok2 ? "good" : "miss";
        var away = double.IsNaN(dist) ? "" : F("{d} u from the spot", "d", Math.Round(dist));
        if (drill.Rush)
        {   // a timing smoke: up on its spot before the runners, one throw (they ran past otherwise: all again)
            nadeWait = false;
            var el = (Server.TickCount - t0) / 64f - rushDelay;
            var first = drill.Tracks.Where(x => x.Arrive >= 0).Select(x => x.Arrive).DefaultIfEmpty(99f).Min();
            var margin = first - el;
            var before = F("{s} s before them", "s", margin.ToString("F1", CultureInfo.InvariantCulture));
            if (q is "perfect" or "good" && rushIn < 0)
            {
                var pts = (int)((q == "perfect" ? 150 : 100) * (margin < 1.5f ? 1.2 : 1.0) * (1 + 0.25 * drill.Level));
                Html($"<font color='#5ad15a'>✔ {Shown("in time")}</font> · {before}<br>{away}", 3);
                var g1 = sessGen;
                AddTimer(3f, () => { if (g1 == sessGen) DrillDone(true, "in time", pts, $"{before} · {away}"); });   // they run into it
                return;
            }
            DrillDone(false, rushIn >= 0 ? "late" : q, 0, rushIn >= 0 ? $"{T("they were there before it")} · {away}" : away);
            return;
        }
        if (q is "perfect" or "good")
        {
            nadeWait = false;
            var pts = (int)((q == "perfect" ? 150 : 100) * (attempts == 1 ? 1 : attempts == 2 ? 0.6 : 0.35) * (1 + 0.25 * drill.Level));
            var res = (true, q, pts, $"{away} · {F("throw {i}", "i", attempts)}");
            if (drill.Victims.Count == 0) { DrillDone(res.Item1, res.Item2, res.pts, res.Item4); return; }
            Html($"<font color='#5ad15a'>✔ {Shown(q)}</font> {away}<br>{T("now from their side")}", 3);
            var g0 = sessGen;
            AddTimer(1.6f, () => { if (g0 == sessGen) Theirs(res); });   // after the camera
            return;
        }
        if (attempts >= 3) { nadeWait = false; DrillDone(false, "miss", 0, away); return; }
        // once more: back on the spot with a new grenade; after two misses the aim is shown
        var show = attempts >= 1 && drill.Level >= 1;   // the aim from the first miss (04/10: "it lacks cues")
        Html($"<font color='#ff5a5a'>{Shown(q)}</font> {away}<br>{F("throw {i}/3", "i", attempts + 1)}{(show ? $" · {T("here is the aim")}" : "")}", 2);
        nadeWait = false;
        AddTimer(1.2f, ClearNades);
        var g = sessGen;
        AddTimer(1.5f, () =>
        {
            if (g != sessGen || drill == null || cur == null || phase is not ("live" or "countdown")) return;
            var me = drill.Me ?? new Spot();
            foreach (var h in Humans())
            {
                if (!h.PawnIsAlive) continue;
                h.GiveNamedItem(drill.Item);
                h.ExecuteClientCommandFromServer($"use {drill.Item}");
                var t = cur.Players.First(p => p.Me);
                var ang = show ? new Vector3(me.Ang[0], me.Ang[1], 0) : Ang(t, 0);
                h.PlayerPawn.Value?.Teleport(new Vector3(me.Pos[0], me.Pos[1], me.Pos[2]), Upright(ang), Vector3.Zero);
            }
            if (show) DrawCross(drill);   // the aim shown: the green cross (your view is not turned to it: the body would lean)
            nadeWait = true;
            attemptEnd = DateTime.UtcNow.AddSeconds(25);
        });
    }

    // Finish() of a situation or an aim drill, in a session
    void SessionFinish(string outcome, double alive)
    {
        if (cur == null) return;
        bool ok;
        int pts = 0;
        string detail;
        if (cur.Kind == "momentum") (ok, pts, detail) = MoResult();
        else if (cur.Kind == "aim" && drill?.Mode == "crossfire") (ok, pts, detail) = CfResult();
        else if (cur.Kind == "aim" && drill?.Mode == "prefire")
        {
            ok = outcome == "cleared" || (aimOrder.Count >= 3 && frags >= aimOrder.Count - 1 && outcome != "dead");   // all, or all but one
            var el = (Server.TickCount - t0) / 64.0;
            pts = frags * 30 + aimHs * 15 + (ok ? 100 + (int)Math.Max(0, (drill.Seconds - el) * 4) : 0);
            detail = $"{frags}/{aimOrder.Count}{(ok ? $" · {el.ToString("F1", CultureInfo.InvariantCulture)} s" : "")} · {aimHs} HS";
        }
        else if (cur.Kind == "aim" && drill?.Mode == "range")
        {
            ok = frags >= drill.Goal;
            var avg = reacts.Count > 0 ? reacts.Average() : 0;
            pts = frags * 12 + aimHs * 8 + (int)Math.Max(0, (1.5 - avg) * 4 * frags) - deaths * 20;
            pts = Math.Max(0, pts) + (ok ? 100 : 0);
            detail = $"{Tn(frags, "{n} kill", "{n} kills")} · {(reacts.Count > 0 ? $"{F("{s} s each", "s", avg.ToString("F2", CultureInfo.InvariantCulture))} · " : "")}"
                     + $"{(frags > 0 ? 100 * aimHs / frags : 0)}% HS{(deaths > 0 ? $" · {Tn(deaths, "{n} death", "{n} deaths")}" : "")}";
        }
        else if (cur.Kind == "aim" && drill?.Mode == "defend")
        {
            ok = frags >= drill.Goal && frags >= deaths;   // 03/10: 15 frags for 11 deaths never counted
            pts = Math.Max(0, frags * 40 + aimHs * 15 - deaths * 50 - plants * 60);
            detail = $"{Tn(frags, "{n} kill", "{n} kills")} · {Tn(deaths, "{n} death", "{n} deaths")} · {aimHs} HS{(plants > 0 ? $" · {Tn(plants, "{n} plant", "{n} plants")}" : "")}";
        }
        else if (cur.Kind == "aim")
        {
            var n = Math.Max(1, aimOrder.Count);
            ok = outcome != "dead" && (reacts.Count == n || (n >= 3 && reacts.Count >= n - 1));
            if (drill?.Id.StartsWith("wallbang") == true) ok = reacts.Count * 2 >= n;   // half of them through the wall (06/10: no retry for playing it another way)
            foreach (var r in reacts) pts += 50 + (int)Math.Max(0, 50 * (1.2 - r) / 1.2);
            pts += aimHs * 20 + (ok ? 100 : 0);
            detail = reacts.Count > 0 ? $"{reacts.Count}/{aimOrder.Count} · {F("{s} s on average", "s", reacts.Average().ToString("F2", CultureInfo.InvariantCulture))} · {aimHs} HS" : T("no kill");
        }
        else
        {
            outcome = SitOutcome(outcome);   // a kill or a trade is needed (04/10); the bomb's end is the round's
            ok = outcome is "won" or "survived" or "traded" or "kill" || BombWon(outcome);
            pts = (outcome == "won" || BombWon(outcome) ? 300 : outcome == "survived" ? 200 : outcome is "traded" or "kill" ? 120 : 0) + 25 * kills;
            detail = SitDetail(alive);
        }
        DrillDone(ok, outcome, pts, detail);
    }

    void DrillDone(bool ok, string outcome, int pts, string detail)
    {
        if (sess == null || drill == null) return;
        phase = "done";
        ClearLine();
        if (cam != null) CamStop();
        nadeStage = "";
        if (ok) { streak++; okN++; } else streak = 0;
        var mult = ok ? 1 + 0.1 * Math.Min(5, streak - 1) : 1.0;
        pts = (int)Math.Round(pts * mult);
        points += pts;
        doneN++;
        var di = sessDone.FindIndex(x => x.d == drill);   // the recap: each drill's last try
        if (di >= 0) sessDone[di] = (drill, ok, outcome); else sessDone.Add((drill, ok, outcome));
        var rec = new Dictionary<string, object> { ["session"] = sess.Id, ["drill"] = drill.Id, ["kind"] = drill.Kind, ["map"] = drill.Map, ["ok"] = ok,
            ["outcome"] = outcome, ["points"] = pts, ["detail"] = detail, ["try"] = tries + 1, ["level"] = drill.Level, ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds() };
        if (drill.Kind == "nade" && nadePops.Count > 0 && drill.Target != null) { rec["pops"] = nadePops.ToList(); rec["target"] = drill.Target; }
        if (drill.Mode is "crossfire" or "momentum") { rec["mode"] = drill.Mode; rec["variant"] = drill.Variant; foreach (var (k, x) in drillExtra) rec[k] = x; }
        Write(rec);
        var st = streak >= 2 ? $" · 🔥 x{mult.ToString("F1", CultureInfo.InvariantCulture)}" : "";
        var shown = Shown(outcome);
        Html(ok ? $"<font color='#5ad15a'>✔ {shown}</font> +{pts}{st}<br>{detail}<br>⭐ {points}"
                : $"<font color='#ff5a5a'>✘ {shown}</font><br>{detail}<br>⭐ {points}", 3);
        All($"{(ok ? "\x04✔" : "\x02✘")} {drill.Title}\x01 · {shown.ToLower()} · {detail} · +{pts} ({F("total {n}", "n", points)}){st}");
        tries++;
        var again = !ok && outcome != "skipped" && tries < 2 && DateTime.UtcNow < blockEnd && drill.Mode is not ("range" or "crossfire" or "momentum");   // a miss: once more right away (Crossfire's and Momentum's reps are their own)
        var g = ++sessGen;
        AddTimer(3.5f, () =>
        {
            if (g != sessGen || sess == null) return;
            if (again && drill != null) RunDrill(drill); else NextDrill();
        });
    }

    void SkipDrill()
    {
        if (sess == null || drill == null) return;
        tries = 2;
        DrillDone(false, "skipped", 0, "");
    }

    void EndSession(bool early = false)
    {
        if (sess == null) return;
        Write(new Dictionary<string, object> { ["session"] = sess.Id, ["end"] = true, ["points"] = points, ["drills"] = doneN, ["ok"] = okN,
            ["early"] = early, ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds() });
        Html($"<font color='#e0a030'>🏁 {T("SESSION DONE")}</font><br><font class='fontSize-l'>{points} pts</font><br>{F("{ok}/{n} drills ✔", "ok", okN, "n", doneN)}<br><font class='fontSize-s'>{T("the recap is in the chat: !again to play some again")}</font>", 10);
        All($"{T("Session done")}: {points} pts · {F("{ok}/{n} drills ✔", "ok", okN, "n", doneN)} — {T("your progress is in the app.")}");
        lastSess = sess; lastDone.Clear(); lastDone.AddRange(sessDone);
        for (int i = 0; i < lastDone.Count; i++)
        {
            var (d, ok, o) = lastDone[i];
            foreach (var h in Humans()) h.PrintToChat($" {(ok ? "\x04✔" : "\x02✘")} {i + 1}\x01 {d.Title} · {Shown(o).ToLower()}");
        }
        if (lastDone.Count > 0) All(T("Again: !again and a number (one drill), !again missed (the missed ones), !again all (the whole session)."));
        // 13/10, the focus block's recap: what comes back (the app's boxes: a miss is due at the next session there)
        var missed = lastDone.Count(x => !x.ok && x.outcome != "skipped");
        if (missed > 0) All(Tn(missed, "{n} missed drill comes first next time you train there", "{n} missed drills come first next time you train there"));
        ClearLine();
        if (cam != null) CamStop();
        Prac(false);
        SetMain("");
        sess = null; drill = null; cur = null; phase = "idle"; bots.Clear(); builtFor = null; sessGen++; paused = false;
        Zombie(false);
        DontShoot(false);
        Ammo(false);
        Server.ExecuteCommand("bot_quota 0");   // or the game adds the last drill's count again
        Server.ExecuteCommand("bot_kick");
    }

    void Write(Dictionary<string, object> o) => Append("results.jsonl", JsonSerializer.Serialize(o));

    Dictionary<string, object?> SessionBeat() => sess == null ? new() : new()
    {
        ["session"] = sess.Id, ["block"] = blockIdx >= 0 && blockIdx < sess.Blocks.Count ? sess.Blocks[blockIdx].Kind : null,
        ["drill"] = drill?.Title, ["points"] = points, ["ok"] = okN, ["done"] = doneN, ["streak"] = streak,
        ["left"] = blockEnd > DateTime.UtcNow ? (int)((paused ? blockEnd + (DateTime.UtcNow - pausedAt) : blockEnd) - DateTime.UtcNow).TotalSeconds : 0,
        ["paused"] = paused,
    };
}
