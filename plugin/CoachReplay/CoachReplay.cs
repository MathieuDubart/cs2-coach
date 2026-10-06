// The coach's replays: a situation of your own demo played again. The bots follow exactly the recorded paths of the
// other players (where they went, where they looked) and fight on their own once they have seen you for a human
// reaction time; you take your own spot (actor) or watch it all (spec: a bot plays your spot too). A bot killed in the
// demo dies at the same moment only if its killer is still alive here (you changed the story: it lives on); one you
// killed in the demo waits for you at the end of its path. Bots never hurt each other. The bomb is planted where and when
// it was (already ticking when the situation starts after the plant), each one has the defuse kit he had, and the
// dead drop their guns. Each try is appended to coach/results.jsonl.
//
// Commands (console, rcon, or chat with !): css_replay <id> [actor|spec], css_r (again), css_n / css_p (next,
// previous of this map), css_spec (switch actor/spec), css_list, css_diff <0-3>, css_stop; css_replay <id> <mode> <0-3>
// also sets the bots' level.
using System.Numerics;
using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Cvars;
using CounterStrikeSharp.API.Modules.Memory;
using CounterStrikeSharp.API.Modules.Memory.DynamicFunctions;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;
using CVector = CounterStrikeSharp.API.Modules.Utils.Vector;

namespace CoachReplay;

public class Track
{
    [JsonPropertyName("sid")] public string Sid { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("team")] public int Team { get; set; }
    [JsonPropertyName("me")] public bool Me { get; set; }
    [JsonPropertyName("hp")] public int Hp { get; set; } = 100;
    [JsonPropertyName("armor")] public int Armor { get; set; }
    [JsonPropertyName("helmet")] public bool Helmet { get; set; }
    [JsonPropertyName("weapons")] public List<string> Weapons { get; set; } = new();
    [JsonPropertyName("active")] public string? Active { get; set; }
    [JsonPropertyName("path")] public float[] Path { get; set; } = Array.Empty<float>();
    [JsonPropertyName("death")] public int Death { get; set; } = -1;
    [JsonPropertyName("killer")] public string Killer { get; set; } = "";
    [JsonPropertyName("kw")] public string KillWeapon { get; set; } = "";   // the gun it was killed with in the match
    [JsonPropertyName("hold")] public bool Hold { get; set; }   // stays on its spot (aim targets): only its aim is its own
    [JsonIgnore] public bool Still { get; set; }   // a prefire's, a wallbang's or a flick's target: its body and its aim held, never firing (06/10)
    [JsonIgnore] public bool Duck { get; set; }   // held crouched, like the players who hold that angle
    [JsonIgnore] public bool Strafe { get; set; }   // an aim map's strafing target: moved left and right by the session
    [JsonPropertyName("places")] public List<JsonElement> Places { get; set; } = new();   // your route in the match: [frame, place]
    [JsonIgnore] public float Start { get; set; }   // the frame its path starts at (a defense's attacker: when it spawned)
    [JsonPropertyName("at")] public string? At { get; set; }   // its place at the start
    [JsonPropertyName("kit")] public bool Kit { get; set; }   // a CT's defuse kit
    [JsonIgnore] public List<Nade> TrackNades { get; set; } = new();   // a defense's attacker: the grenades of the real hit it walks
    [JsonIgnore] public int NadeNext { get; set; }
    public int Frames => Path.Length / 5;
}

public class Bomb
{
    [JsonPropertyName("f")] public int F { get; set; }   // the frame it is planted at (0: already ticking at the start)
    [JsonPropertyName("pos")] public float[] Pos { get; set; } = new float[3];
    [JsonPropertyName("site")] public int Site { get; set; }   // 0 A, 1 B
    [JsonPropertyName("left")] public float Left { get; set; } = 40;   // seconds to the explosion once it is down here
    [JsonPropertyName("by")] public string By { get; set; } = "";   // the planter
}

public class Nade
{
    [JsonPropertyName("f")] public int F { get; set; }
    [JsonPropertyName("type")] public string Type { get; set; } = "";
    [JsonPropertyName("by")] public string By { get; set; } = "";
    [JsonPropertyName("inc")] public bool Inc { get; set; }
    [JsonPropertyName("life")] public int Life { get; set; }
    [JsonPropertyName("p")] public float[] P { get; set; } = new float[3];
    [JsonPropertyName("v")] public float[] V { get; set; } = new float[3];
}

public class Scenario
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("map")] public string Map { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "death";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("rate")] public int Rate { get; set; } = 64;
    [JsonPropertyName("step")] public int Step { get; set; } = 2;
    [JsonPropertyName("key")] public int Key { get; set; }
    [JsonPropertyName("team")] public int Team { get; set; }
    [JsonPropertyName("players")] public List<Track> Players { get; set; } = new();
    [JsonPropertyName("nades")] public List<Nade> Nades { get; set; } = new();
    [JsonPropertyName("danger")] public string Danger { get; set; } = "";
    [JsonPropertyName("goal")] public string Goal { get; set; } = "";
    [JsonPropertyName("bomb")] public Bomb? Bomb { get; set; }   // planted in the window (or before it)
    [JsonPropertyName("plant")] public string Plant { get; set; } = "";   // the bomb in the real round, said on screen
    [JsonPropertyName("line")] public List<float[]> Line { get; set; } = new();   // your way in the match, drawn on the ground
    [JsonPropertyName("clock")] public float Clock { get; set; }   // the real round's clock at the start (s left; 0: unknown)
    // who died in the round before the window, where (06/10: "il faut savoir où mes alliés meurent pour savoir où sont les
    // ennemis"), and where the players went before it (the doors and the vents they opened or broke)
    [JsonPropertyName("dead")] public List<Dead> Dead { get; set; } = new();
    [JsonPropertyName("trail")] public List<float[]> Trail { get; set; } = new();
}

public class Dead
{
    [JsonPropertyName("pos")] public float[] Pos { get; set; } = new float[3];
    [JsonPropertyName("team")] public int Team { get; set; }
    [JsonPropertyName("at")] public string At { get; set; } = "";
    [JsonPropertyName("clock")] public string Clock { get; set; } = "";   // the round's clock when it happened (1:23)
}

public partial class CoachReplay : BasePlugin
{
    public override string ModuleName => "CoachReplay";
    public override string ModuleVersion => "1.0";
    public override string ModuleAuthor => "cs2-coach";

    string Dir => System.IO.Path.GetFullPath(System.IO.Path.Combine(ModuleDirectory, "..", "..", "..", "..", "coach"));
    Scenario? cur;
    string mode = "actor";
    string phase = "idle";   // idle, setup, countdown, live, done
    readonly Dictionary<int, Track> bots = new();   // controller slot -> track
    readonly HashSet<string> gone = new();   // tracks dead here
    readonly HashSet<int> free = new();   // slots whose path is over: the bot plays on its own
    readonly Dictionary<int, int> contact = new();   // ticks a scripted bot has seen you: then it plays on its own, like a player
    readonly Dictionary<int, int> engaged = new();   // the tick a scripted bot started fighting you: it keeps the real player's moves 1.5 s
    const int EngageTicks = 96;
    int t0, countdownEnd, kills, dmg, generation, lastBeat, nextNade;
    bool awaitRestart;
    int emptyTries;   // a drill set up again because its bots did not come
    CCSGameRules? rules;   // the center text's blink fix (OnTick)
    const int MinHp = 40;   // a situation: at least that many HP (2 HP in the match: dead before you could do anything)
    // a bot on its recorded path keeps the real player's aim this long after it has seen you, then fights on its own: a
    // player's reaction time (04/10, "as if they had lag": they used to aim at you the very tick they saw you)
    const int ReactTicks = 13;
    // the aim map's duels: the ticks a target must have seen you before its shots hurt (0.47 s at Easy to 0.23 s at Expert)
    int DuelReact => difficulty switch { 0 => 30, 1 => 24, 2 => 19, _ => 15 };
    // a bot on its path notices you this close, or when you shoot this close (a silenced gun: half): it then plays on
    // its own (04/10: "expert bots that don't even look at me")
    const float Near = 350f, Earshot = 1200f;
    const string NullModel = "models/props_doors/null.vmdl";   // an empty model of the game (the grenade camera's)
    bool bombLive, bombDone;   // a situation: the bomb is down here / the demo's plant is done (or will not be)
    int protectUntil;   // a defense: you just came back, nothing hurts you until this tick
    bool humanDead, traded;   // a situation: you died, and your killer died within 3 s
    int tradeKiller = -1, tradeUntil;
    string? builtFor;   // the situation the bots on the server were made for
    int difficulty = 2;
    double devSum; int devN;   // how far the bots drift from their path between two ticks (checked in spec mode)
    // CSmokeGrenadeProjectile::Create(origin, angles, velocity, angular impulse, thrower, item definition, team): a smoke made
    // any other way never pops. Found in this server's server.dll (unique); null after a game update that moved it: no smokes
    const string SmokeSig = "48 8B C4 48 89 58 ? 48 89 68 ? 48 89 70 ? 57 41 56 41 57 48 81 EC ? ? ? ? 48 8B B4 24 ? ? ? ? 4D 8B F8 4C 8B C2";
    MemoryFunctionWithReturn<nint, nint, nint, nint, nint, int, int, nint>? smokeCreate;
    // CHEGrenadeProjectile::Create(origin, angles, velocity, angular impulse, thrower, item definition): sets its fuse and think
    const string HeSig = "48 89 5C 24 ? 48 89 6C 24 ? 48 89 74 24 ? 57 48 83 EC 50 48 8B AC 24 ? ? ? ? 49 8B F8 4C 8B C2 0F 29 74 24 ? 48 8B D1 0F 29 7C 24";
    MemoryFunctionWithReturn<nint, nint, nint, nint, nint, int, nint>? heCreate;
    // CMolotovProjectile::Create(origin, angles, velocity, angular impulse, thrower, item definition: 46 molotov, 48 incendiary)
    const string MolotovSig = "48 8B C4 48 89 58 ? 48 89 70 ? 48 89 78 ? 4C 89 40 ? 55 41 54 41 55 41 56 41 57 48 8D 6C 24 ? 48 81 EC ? ? ? ? 45 33 FF";
    MemoryFunctionWithReturn<nint, nint, nint, nint, nint, int, nint>? molotovCreate;

    public override void Load(bool hotReload)
    {
        Directory.CreateDirectory(System.IO.Path.Combine(Dir, "scenarios"));
        try { smokeCreate = new(SmokeSig); } catch (Exception e) { smokeCreate = null; Logger.LogInformation("no smokes: {m}", e.Message); }
        try { heCreate = new(HeSig); } catch (Exception e) { heCreate = null; Logger.LogInformation("no HE: {m}", e.Message); }
        try { molotovCreate = new(MolotovSig); } catch (Exception e) { molotovCreate = null; Logger.LogInformation("no molotov: {m}", e.Message); }
        RegisterListener<Listeners.OnTick>(OnTick);
        RegisterListener<Listeners.OnServerPrecacheResources>(m => m.AddResource(NullModel));
        RegisterListener<Listeners.OnMapStart>(_ =>
        {
            rules = null;
            phase = cur != null || sess != null ? "setup" : "idle";
            AddTimer(4f, () => { Server.ExecuteCommand("sv_hibernate_when_empty 0"); if (sess != null) SessionResume(); else if (cur != null) Setup(); });
        });
        RegisterEventHandler<EventRoundStart>(OnRoundStart);
        RegisterEventHandler<EventPlayerDeath>(OnDeath);
        // the bots' scripted deaths (a target waiting for its turn, a death of the demo) stay out of your kill feed
        RegisterEventHandler<EventPlayerDeath>((e, info) =>
        {
            if (cur != null && e.Userid is { IsValid: true, IsBot: true } v && (e.Attacker is not { IsValid: true } || e.Attacker.Slot == v.Slot))
                info.DontBroadcast = true;
            return HookResult.Continue;
        }, HookMode.Pre);
        RegisterEventHandler<EventPlayerHurt>(OnHurt);
        RegisterEventHandler<EventPlayerConnectFull>((e, _) =>
        {
            if (e.Userid is { IsBot: false }) { if (sess != null) AddTimer(3f, SessionResume); else if (cur != null) AddTimer(2f, Setup); }
            return HookResult.Continue;
        });
        RegisterListener<Listeners.OnEntityTakeDamagePre>(OnTakeDamage);
        // your shots: the bots on their path that hear them react (they fight on their own)
        RegisterEventHandler<EventWeaponFire>((e, _) =>
        {
            if (cur == null || phase != "live" || mode != "actor" || e.Userid is not { IsValid: true, IsBot: false } h) return HookResult.Continue;
            var w = e.Weapon ?? "";
            if (w.Contains("knife") || w.Contains("grenade") || w.Contains("flashbang") || w.Contains("molotov") || w.Contains("decoy")) return HookResult.Continue;
            if (h.PlayerPawn.Value?.AbsOrigin is not { } o) return HookResult.Continue;
            var me = new Vector3(o.X, o.Y, o.Z);
            var r = e.Silenced || w.Contains("silencer") ? Earshot / 2 : Earshot;
            foreach (var (slot, t) in bots.ToList())
            {
                if (t.Hold || t.Team == cur.Team || free.Contains(slot) || gone.Contains(t.Sid)) continue;   // your enemies
                var c = Utilities.GetPlayerFromSlot(slot);
                if (c?.PlayerPawn.Value?.AbsOrigin is { } bo && Vector3.Distance(new Vector3(bo.X, bo.Y, bo.Z), me) < r)
                { Free(slot, c, t); Logger.LogInformation("heard {n}", t.Name); }
            }
            return HookResult.Continue;
        });
        // a situation's bomb: defused or blown up, the situation is over
        RegisterEventHandler<EventBombDefused>((e, _) => { if (cur is { Kind: "death" or "clutch" } && phase == "live") Finish("defused"); return HookResult.Continue; });
        RegisterEventHandler<EventBombExploded>((e, _) => { if (cur is { Kind: "death" or "clutch" } && phase == "live") Finish("exploded"); return HookResult.Continue; });
        RegisterEventHandler<EventBombPlanted>((e, _) => { if (cur is { Kind: "death" or "clutch" }) bombLive = bombDone = true; return HookResult.Continue; });
        RegisterEventHandler<EventSmokegrenadeDetonate>((e, _) => { Logger.LogInformation("smoke pops {x:F0} {y:F0}", e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventFlashbangDetonate>((e, _) => { Logger.LogInformation("flash pops {x:F0} {y:F0}", e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventHegrenadeDetonate>((e, _) => { Logger.LogInformation("he pops {x:F0} {y:F0}", e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventInfernoStartburn>((e, _) => { Logger.LogInformation("fire {x:F0} {y:F0}", e.X, e.Y); return HookResult.Continue; });
        Server.ExecuteCommand("sv_hibernate_when_empty 0");
        RegisterSession();
        AddCommand("css_replay", "play a scenario: css_replay <id> [actor|spec]", (p, c) => CmdReplay(p, c));
        AddCommand("css_r", "the same situation again", (p, c) => { if (cur != null) Setup(); });
        AddCommand("css_n", "next situation of this map (in a session: skip the drill)", (p, c) => { if (sess != null) SkipDrill(); else Cycle(1); });
        AddCommand("css_p", "previous situation of this map", (p, c) => Cycle(-1));
        AddCommand("css_spec", "switch between playing your spot and watching", (p, c) => { mode = mode == "spec" ? "actor" : "spec"; if (cur != null) Setup(); });
        AddCommand("css_list", "situations of this map", (p, c) => { foreach (var s in List()) Say(p, s); });
        AddCommand("css_diff", "bot difficulty 0-3", (p, c) => { if (int.TryParse(c.GetArg(1), out var d)) difficulty = Math.Clamp(d, 0, 3); Say(p, $"difficulty {difficulty}"); if (cur != null) Setup(); });
        AddCommand("css_dbg", "state of the bots", (p, c) =>
        {
            foreach (var cls in new[] { "smokegrenade_projectile", "hegrenade_projectile", "flashbang_projectile", "molotov_projectile" })
                foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseCSGrenadeProjectile>(cls))
                    Logger.LogInformation("dbg {c} at {x:F0} {y:F0} {z:F0} vel {v:F0} det {d:F1} now {n:F1} think {t} live {l} smoke {s}", cls, e.AbsOrigin?.X, e.AbsOrigin?.Y, e.AbsOrigin?.Z,
                        e.AbsVelocity?.Length(), e.DetonateTime, Server.CurrentTime, e.NextThinkTick, e.IsLive, cls.StartsWith("smoke") ? new CSmokeGrenadeProjectile(e.Handle).DidSmokeEffect : null);
            foreach (var b in Utilities.GetPlayers().Where(x => x is { IsValid: true }))
                Logger.LogInformation("dbg {n} slot {s} team {t} alive {a} life {l} hp {h}", b.PlayerName, b.Slot, b.Team, b.PawnIsAlive, b.PlayerPawn.Value?.LifeState, b.PlayerPawn.Value?.Health);
        });
        AddCommand("css_dbgbots", "the players' body angle, aim, move type, speed and kit; the bomb; the guns on the ground", (p, c) =>
        {
            foreach (var b in Utilities.GetPlayers().Where(x => x is { IsValid: true, PawnIsAlive: true }))
            {
                var pw = b.PlayerPawn.Value;
                if (pw == null) continue;
                var r = pw.AbsRotation; var e = pw.EyeAngles; var v = pw.AbsVelocity;
                var kit = pw.ItemServices == null ? (bool?)null : new CCSPlayer_ItemServices(pw.ItemServices.Handle).HasDefuser;
                Logger.LogInformation("dbgbots {n} body {bp:F1} {by:F1} {br:F1} eye {ep:F1} {ey:F1} move {m} speed {s:F0} kit {k} free {f} life {l} hp {h}", b.PlayerName,
                    r?.X, r?.Y, r?.Z, e?.X, e?.Y, pw.MoveType, v == null ? -1 : Math.Sqrt(v.X * v.X + v.Y * v.Y), kit, free.Contains(b.Slot), pw.LifeState, pw.Health);
            }
            foreach (var c4 in Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4"))
                Logger.LogInformation("dbgbots bomb at {x:F0} {y:F0} {z:F0} site {s} ticking {t} blows in {l:F1} s", c4.AbsOrigin?.X, c4.AbsOrigin?.Y, c4.AbsOrigin?.Z,
                    c4.BombSite, c4.BombTicking, c4.C4Blow - Server.CurrentTime);
            Logger.LogInformation("dbgbots guns on the ground: {n}", Utilities.FindAllEntitiesByDesignerName<CBasePlayerWeapon>("weapon_").Count(w => w.OwnerEntity.Value == null));
        });
        // the In game page's numpad keys say a path with CS2's chat wheel "Ping Site A": what the server makes of it
        // (a ping entity, and where), tried with a bot
        AddCommand("css_dbgping", "a bot uses the chat wheel's Ping Site A: the pings made, and where", (p, c) =>
        {
            var b = Utilities.GetPlayers().FirstOrDefault(x => x is { IsValid: true, IsBot: true, PawnIsAlive: true }
                                                                && x.PlayerPawn.Value?.LifeState == (byte)LifeState_t.LIFE_ALIVE);
            if (b == null) { Logger.LogInformation("dbgping: no bot alive"); return; }
            var arg = c.ArgCount > 1 ? c.GetArg(1) : "CW.GoA";
            var before = Utilities.GetAllEntities().Select(e => e.Index).ToHashSet();
            // a CW.* item through the chat wheel's command; anything else as it is (player_ping: a ping where it looks)
            b.ExecuteClientCommandFromServer(arg.StartsWith("CW.") ? $"playerchatwheel {arg} \"#Chatwheel_aplan\"" : c.ArgString);
            AddTimer(0.5f, () =>
            {
                foreach (var e in Utilities.GetAllEntities().Where(e => !before.Contains(e.Index) || (e.DesignerName != null && e.DesignerName.Contains("ping"))))
                {
                    var be = new CBaseEntity(e.Handle);
                    Logger.LogInformation("dbgping new or ping entity {d} at {x:F0} {y:F0} {z:F0}", e.DesignerName, be.AbsOrigin?.X, be.AbsOrigin?.Y, be.AbsOrigin?.Z);
                }
                foreach (var s in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>("func_bomb_target"))
                    Logger.LogInformation("dbgping site trigger at {x:F0} {y:F0} {z:F0}", s.AbsOrigin?.X, s.AbsOrigin?.Y, s.AbsOrigin?.Z);
                Logger.LogInformation("dbgping: {n} by {b} ({a})", "done", b.PlayerName, arg);
            });
        });
        AddCommand("css_dbgspawns", "the map's spawn points", (p, c) =>
        {
            foreach (var cls in new[] { "info_player_terrorist", "info_player_counterterrorist" })
                foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>(cls))
                    Logger.LogInformation("dbgspawns {c} {x:F0} {y:F0} {z:F0} yaw {w:F0}", cls, e.AbsOrigin?.X, e.AbsOrigin?.Y, e.AbsOrigin?.Z, e.AbsRotation?.Y);
        });
        AddCommand("css_dbgbreak", "the map's breakables", (p, c) =>
        {
            foreach (var cls in new[] { "func_breakable", "func_breakable_surf", "prop_dynamic", "prop_physics_multiplayer" })
                foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>(cls))
                    Logger.LogInformation("dbgbreak {c} {n} {x:F0} {y:F0} {z:F0} hp {h}", cls, e.Entity?.Name, e.AbsOrigin?.X, e.AbsOrigin?.Y, e.AbsOrigin?.Z, e.Health);
        });
        AddCommand("css_dbgbreakat", "break the breakables near x y z", (p, c) =>
        {
            if (float.TryParse(c.GetArg(1), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var x)
                && float.TryParse(c.GetArg(2), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var y)
                && float.TryParse(c.GetArg(3), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var z))
                Break(new List<Vector3> { new(x, y, z) });
            AddTimer(1f, () =>
            {
                foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>("prop_dynamic").Where(e => (e.Entity?.Name ?? "").Contains("vent")))
                    Logger.LogInformation("dbgbreakat after: {n} valid {v} hp {h}", e.Entity?.Name, e.IsValid, e.Health);
            });
        });
        AddCommand("css_dbgboost", "two bots of a team: one held still (crouched with 1), the other dropped on its head; heights after 1.5 s", (p, c) =>
        {
            var duck = c.ArgCount > 1 && c.GetArg(1) == "1";
            var bs = Utilities.GetPlayers().Where(x => x is { IsValid: true, IsBot: true, PawnIsAlive: true }).GroupBy(x => x.Team).FirstOrDefault(g => g.Count() >= 2)?.Take(2).ToList();
            if (bs == null || bs[0].PlayerPawn.Value?.AbsOrigin == null || bs[1].PlayerPawn.Value == null) { Logger.LogInformation("dbgboost: two living bots of one team needed"); return; }
            Zombie(true);
            var a = bs[0].PlayerPawn.Value!; var b = bs[1].PlayerPawn.Value!;
            var at = new Vector3(a.AbsOrigin!.X, a.AbsOrigin.Y, a.AbsOrigin.Z);
            Freeze(a, true);
            b.Teleport(at + new Vector3(0, 0, 100), null, Vector3.Zero);
            Freeze(b, false);
            var tm = AddTimer(0.05f, () => { if (a.IsValid) { a.Teleport(at, null, Vector3.Zero); HoldAim(a, new Vector3(0, 90, 0), duck); } }, CounterStrikeSharp.API.Modules.Timers.TimerFlags.REPEAT);
            AddTimer(1.5f, () =>
            {
                tm.Kill();
                var da = a.MovementServices == null ? -1f : new CCSPlayer_MovementServices(a.MovementServices.Handle).DuckAmount;
                Logger.LogInformation("dbgboost duck {d}: the one below has duck amount {da:F2}, the one on top is {h:F1} u above it (solid teammates {s})", duck, da,
                    b.IsValid && b.AbsOrigin != null ? b.AbsOrigin.Z - at.Z : -999f, ConVar.Find("mp_solid_teammates")?.GetPrimitiveValue<int>());
            });
        });
        AddCommand("css_dbgents", "the map's entity classes and how many of each", (p, c) =>
        {
            foreach (var g in Utilities.GetAllEntities().Where(e => e.DesignerName != null).GroupBy(e => e.DesignerName).OrderBy(g => g.Key))
                Logger.LogInformation("dbgents {d} {n}", g.Key, g.Count());
        });
        AddCommand("css_dbgdoors", "the map's doors: class and position", (p, c) =>
        {
            foreach (var d in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>("prop_door_rotating"))
            {
                try
                {
                    var o = d.AbsOrigin;
                    var n = d.CBodyComponent?.SceneNode;
                    Logger.LogInformation("dbgdoors #{i} valid {v} origin {o} node {n} at {x:F0} {y:F0} {z:F0}", d.Index, d.IsValid, o != null, n != null,
                        o?.X ?? n?.AbsOrigin?.X, o?.Y ?? n?.AbsOrigin?.Y, o?.Z ?? n?.AbsOrigin?.Z);
                }
                catch (Exception ex) { Logger.LogInformation("dbgdoors #{i}: {m}", d.Index, ex.Message); }
            }
        });
        AddCommand("css_dbgline", "draw a test line (3 segments) and count the beams", (p, c) =>
        {
            DrawLine(new List<float[]> { new[] { 0f, 0f, 0f }, new[] { 200f, 0f, 0f }, new[] { 200f, 200f, 0f }, new[] { 0f, 200f, 0f } });
            Logger.LogInformation("dbgline: {n} beams drawn, {m} in the world", beams.Count, Utilities.FindAllEntitiesByDesignerName<CBeam>("beam").Count());
            AddTimer(2f, () => { ClearLine(); Logger.LogInformation("dbgline: cleared, {m} in the world", Utilities.FindAllEntitiesByDesignerName<CBeam>("beam").Count()); });
        });
        AddCommand("css_stop", "stop the replay (or the session)", (p, c) =>
        {
            if (sess != null) { EndSession(true); return; }
            cur = null; phase = "idle"; bots.Clear(); builtFor = null; Server.ExecuteCommand("bot_quota 0"); Server.ExecuteCommand("bot_kick");
        });
    }

    void Say(CCSPlayerController? p, string s) { if (p == null) Logger.LogInformation("{s}", s); else p.PrintToChat($" \x04[coach]\x01 {s}"); }

    void All(string s) { foreach (var p in Humans()) p.PrintToChat($" \x04[coach]\x01 {s}"); Logger.LogInformation("{s}", s); }

    static IEnumerable<CCSPlayerController> Humans() => Utilities.GetPlayers().Where(p => p is { IsValid: true, IsBot: false, IsHLTV: false });

    List<string> List()
    {
        var map = Server.MapName;
        return Directory.GetFiles(System.IO.Path.Combine(Dir, "scenarios"), "*.json").Select(f => System.IO.Path.GetFileNameWithoutExtension(f)!)
            .Where(id => Peek(id)?.Map == map).OrderBy(x => x).ToList();
    }

    Scenario? Peek(string id)
    {
        var f = System.IO.Path.Combine(Dir, "scenarios", id + ".json");
        if (!File.Exists(f)) return null;
        try { return JsonSerializer.Deserialize<Scenario>(File.ReadAllText(f)); } catch (Exception e) { Logger.LogInformation($"{id}: {e.Message}"); return null; }
    }

    void CmdReplay(CCSPlayerController? p, CommandInfo c)
    {
        var s = Peek(c.GetArg(1));
        if (s == null) { Say(p, $"no scenario {c.GetArg(1)}"); return; }
        if (c.ArgCount > 2 && (c.GetArg(2) == "spec" || c.GetArg(2) == "actor")) mode = c.GetArg(2);
        if (c.ArgCount > 3 && int.TryParse(c.GetArg(3), out var d)) difficulty = Math.Clamp(d, 0, 3);
        cur = s;
        if (Server.MapName != s.Map) { phase = "setup"; Server.ExecuteCommand($"changelevel {s.Map}"); return; }
        Setup();
    }

    void Cycle(int d)
    {
        var l = List();
        if (l.Count == 0) return;
        var i = cur == null ? -1 : l.IndexOf(cur.Id);
        cur = Peek(l[((i + d) % l.Count + l.Count) % l.Count]);
        if (cur != null) Setup();
    }

    // the bots (one per recorded player but you), their names, your team; then a clean round
    void Setup()
    {
        if (cur == null) return;
        var g = ++generation;
        gone.Clear(); free.Clear(); contact.Clear(); engaged.Clear();
        if (mode == "actor" && !Humans().Any()) { phase = "waiting"; return; }   // starts when you join
        phase = "setup";
        // the same situation again: the same bots, only a clean round (fast retries)
        var diff = drill?.Mode == "defend" ? Math.Max(0, difficulty - 1) : difficulty;   // a defense: three at a time, one level easier
        var key = $"{cur.Id}|{mode}|{diff}";
        if (builtFor == key && bots.Count > 0 && bots.Keys.All(sl => Utilities.GetPlayerFromSlot(sl) is { IsValid: true, IsBot: true }))
        {
            Teams();
            awaitRestart = true;
            Server.ExecuteCommand("mp_restartgame 1");
            return;
        }
        bots.Clear();
        builtFor = key;
        // a situation as it was: the dead drop their gun and their kit, to pick up like in the match (the round restart
        // of each try clears the ground); the drills keep the ground clean
        var drop = cur.Kind is "death" or "clutch" ? 1 : 0;
        // the game's clock says the real round's time (from GO: the countdown first), 04/10 "put the real timing of the
        // game"; a drill's too: when its angles get fought, when its lineup is thrown, an aim drill's own time (06/10: "le
        // vrai temps in-game de la situation, pas 58 minutes"); without one: an hour
        var rt = (cur.Clock > 0 ? (cur.Clock + (cur.Kind is "death" or "clutch" ? 5 : 3)) / 60f : 60f).ToString("0.###", System.Globalization.CultureInfo.InvariantCulture);
        foreach (var cmd in new[] { "mp_warmup_end", "mp_ignore_round_win_conditions 1", "mp_freezetime 0", $"mp_roundtime {rt}",
                     $"mp_roundtime_defuse {rt}", $"mp_roundtime_hostage {rt}", "mp_buytime 0", "mp_autoteambalance 0", "mp_limitteams 0",
                     "mp_friendlyfire 0", "mp_autokick 0", "mp_halftime 0", "mp_maxrounds 99", "mp_match_can_clinch 0",
                     "mp_give_player_c4 0", $"mp_death_drop_gun {drop}", $"mp_death_drop_defuser {drop}", "mp_c4timer 40",
                     "mp_randomspawn 0", "bot_quota_mode normal", $"mp_solid_teammates {(drill?.Id.StartsWith("boost") == true ? 1 : 0)}",   // no teammate's path blocks yours (04/10); a boost: you stand on one
                     "mp_playercashawards 0", "mp_teamcashawards 0",
                     "bot_join_after_player 0", "bot_chatter off", "sv_hibernate_when_empty 0", "sv_falldamage_scale 0",
                     $"bot_difficulty {diff}", "bot_quota 0", "bot_kick" })   // quota 0 first: kicked with the last drill's quota (10), the game added 10 of its own and a prefire got none (06/10)
            Server.ExecuteCommand(cmd);
        var want = cur.Players.Where(t => !t.Me || mode == "spec").ToList();
        AddBots(g, want, 0);
    }

    // a bot really in the game (a kicked one stays listed a moment, leaving)
    static bool Here(CCSPlayerController p) => p is { IsValid: true, IsBot: true } && p.Connected == PlayerConnectedState.Connected;
    static bool Coming(CCSPlayerController p) => p is { IsValid: true, IsBot: true }
                                                 && p.Connected is PlayerConnectedState.Connected or PlayerConnectedState.Connecting or PlayerConnectedState.Reconnecting;
    static bool Leaving(CCSPlayerController p) => p is { IsValid: true, IsBot: true } && p.Connected != PlayerConnectedState.Disconnected
                                                  && p.Connected != PlayerConnectedState.NeverConnected;

    // the old bots gone first: added while they leave, the team still looks full and the new ones are refused (03/10:
    // a prefire with no bot, a clutch's enemy that was a leaving bot); then the new ones, every one in before the roles
    void AddBots(int g, List<Track> want, int tries)
    {
        AddTimer(0.25f, () =>
        {
            if (g != generation || cur == null) return;
            if (Utilities.GetPlayers().Any(Leaving) && tries < 16) { if (tries == 8) Server.ExecuteCommand("bot_kick"); AddBots(g, want, tries + 1); return; }
            AddTimer(0.75f, () =>   // gone: the game still counts them a moment (04/10: 1 CT of 4 right after 10 CTs left)
            {
                if (g != generation || cur == null) return;
                foreach (var t in want) Server.ExecuteCommand(t.Team == 2 ? "bot_add_t" : "bot_add_ct");
                Teams();
                WaitBots(g, want, 0);
            });
        });
    }

    void WaitBots(int g, List<Track> want, int tries)
    {
        AddTimer(0.3f, () =>
        {
            if (g != generation || cur == null) return;
            var all = want.GroupBy(t => t.Team).All(k => Utilities.GetPlayers().Count(p => Here(p) && (int)p.Team == k.Key) >= k.Count());
            if (!all && tries < 14)
            {
                if (tries % 4 == 3)   // still short: ask again for the missing ones (the ones on their way count)
                    foreach (var k in want.GroupBy(t => t.Team))
                    {
                        var miss = k.Count() - Utilities.GetPlayers().Count(p => Coming(p) && (int)p.Team == k.Key);
                        for (int i = 0; i < miss; i++) Server.ExecuteCommand(k.Key == 2 ? "bot_add_t" : "bot_add_ct");
                    }
                WaitBots(g, want, tries + 1);
                return;
            }
            Roles(g, want);
        });
    }

    void Roles(int g, List<Track> want)
    {
        {
            foreach (var team in new[] { 2, 3 })
            {
                var tracks = want.Where(t => t.Team == team).ToList();
                var bs = Utilities.GetPlayers().Where(p => Here(p) && (int)p.Team == team).ToList();
                for (int i = 0; i < Math.Min(tracks.Count, bs.Count); i++)
                {
                    bots[bs[i].Slot] = tracks[i];
                    bs[i].PlayerName = tracks[i].Me ? tracks[i].Name + " (you)" : tracks[i].Name;
                    Utilities.SetStateChanged(bs[i], "CBasePlayerController", "m_iszPlayerName");
                }
                if (bs.Count != tracks.Count) Logger.LogInformation($"team {team}: {bs.Count} bots for {tracks.Count} tracks");
                foreach (var extra in bs.Skip(tracks.Count)) Server.ExecuteCommand($"kickid {extra.UserId}");   // a bot the game added on its own
            }
            Server.ExecuteCommand($"bot_quota {bots.Count}");   // the game keeps that many: no bot added on its own
            // a drill without its bots (or a situation without any enemy): once more from scratch, then skipped
            var foes = want.Count(t => t.Team != cur!.Team);
            if (want.Count > 0 && (bots.Count == 0 || (mode == "actor" && foes > 0 && !bots.Values.Any(t => t.Team != cur!.Team))))
            {
                Logger.LogInformation("no bots for {id} ({n} of {w})", cur!.Id, bots.Count, want.Count);
                if (emptyTries++ < 1) { builtFor = null; Setup(); return; }
                emptyTries = 0;
                if (sess != null && drill != null) { phase = "live"; DrillDone(false, "skipped", 0, "the bots did not come"); }
                return;
            }
            emptyTries = 0;
            awaitRestart = true;
            Server.ExecuteCommand("mp_restartgame 1");
        }
    }

    void Teams()
    {
        if (cur == null) return;
        var team = mode == "spec" ? CsTeam.Spectator : (CsTeam)cur.Team;
        foreach (var h in Humans())
        {
            if (h.Team == team) continue;
            // from one side to the other: switch without dying (ChangeTeam kills you); from the menu: join
            if (h.Team is CsTeam.Terrorist or CsTeam.CounterTerrorist && team is CsTeam.Terrorist or CsTeam.CounterTerrorist) h.SwitchTeam(team);
            else h.ChangeTeam(team);
        }
    }

    HookResult OnRoundStart(EventRoundStart e, GameEventInfo i)
    {
        if (!awaitRestart || cur == null) return HookResult.Continue;
        awaitRestart = false;
        var g = generation;
        AddTimer(0.3f, () => { if (g == generation) Place(); });
        return HookResult.Continue;
    }

    static void Loadout(CCSPlayerController c, Track t, int? hp = null)
    {
        var pawn = c.PlayerPawn.Value;
        if (pawn == null) return;
        c.RemoveWeapons();
        // bots get no grenades: the demo's are thrown again by the plugin, their own AI would throw others. No bot gets
        // the bomb (the demo's plant is the plugin's); you get it when you carried it
        var nade = (string w) => c.IsBot && (w.Contains("grenade") || w.Contains("flashbang") || w.Contains("molotov") || w.Contains("decoy"));
        var skip = (string w) => nade(w) || (w == "weapon_c4" && c.IsBot);
        foreach (var w in t.Weapons.Where(w => w != t.Active && !skip(w))) c.GiveNamedItem(w);
        if (!string.IsNullOrEmpty(t.Active) && !skip(t.Active)) c.GiveNamedItem(t.Active);
        if (t.Kit && t.Team == 3) c.GiveNamedItem("item_defuser");
        pawn.Health = Math.Max(1, hp ?? t.Hp);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
        pawn.ArmorValue = t.Armor;
        Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_ArmorValue");
        if (pawn.ItemServices != null) new CCSPlayer_ItemServices(pawn.ItemServices.Handle).HasHelmet = t.Helmet;
        if (c.InGameMoneyServices != null) { c.InGameMoneyServices.Account = 0; Utilities.SetStateChanged(c, "CCSPlayerController", "m_pInGameMoneyServices"); }
        if (!string.IsNullOrEmpty(t.Active) && t.Active != "weapon_c4") c.ExecuteClientCommandFromServer($"use {t.Active}");
    }

    static void Freeze(CCSPlayerPawn pawn, bool on)
    {
        pawn.MoveType = on ? MoveType_t.MOVETYPE_OBSOLETE : MoveType_t.MOVETYPE_WALK;
        Schema.SetSchemaValue(pawn.Handle, "CBaseEntity", "m_nActualMoveType", on ? 1 : 2);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_MoveType");
    }

    // a still target's view on its angle, crouched or standing, every tick (its own AI idles: bot_zombie)
    static void HoldAim(CCSPlayerPawn pawn, Vector3 a, bool duck)
    {
        if (pawn.EyeAngles is { } eye && (Math.Abs(eye.X - a.X) > 0.5f || Math.Abs(((eye.Y - a.Y + 540f) % 360f) - 180f) > 0.5f))
        { eye.X = a.X; eye.Y = a.Y; Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_angEyeAngles"); }
        if (pawn.MovementServices != null)
        {
            var mv = new CCSPlayer_MovementServices(pawn.MovementServices.Handle);
            if (mv.DuckOverride != duck) mv.DuckOverride = duck;
        }
    }

    // the game's bots idle or not (bot_zombie: a cheat setting the plugin sets itself, never sv_cheats for you): still
    // targets never turn to you nor fire (06/10)
    static void Zombie(bool on)
    {
        try { ConVar.Find("bot_zombie")?.SetValue(on); } catch (Exception) { }
    }

    // the aim map: the guns never run dry (reloads stay)
    static void Ammo(bool on)
    {
        try { ConVar.Find("sv_infinite_ammo")?.SetValue(on ? 2 : 0); } catch (Exception) { }
    }

    // a teleport's angles turn the whole body: with a pitch the player leans, his head off his feet, and his view goes
    // through walls (04/10, the video: "my character leans", "my view through the wall"). Bodies stay upright: only the
    // yaw; you look up or down yourself
    static Vector3 Upright(Vector3 ang) => new(0, ang.Y, 0);

    // the map's doors near these points opened (a door in the way of a real player's path was open in the match; one
    // in a grenade's way, open for the pro who threw it)
    void OpenDoors(IEnumerable<Vector3> pts, float r = 96f)
    {
        var doors = Utilities.FindAllEntitiesByDesignerName<CBaseEntity>("prop_door_rotating")
            .Where(d => d.IsValid && d.AbsOrigin != null).Select(d => (d, o: new Vector3(d.AbsOrigin!.X, d.AbsOrigin.Y, d.AbsOrigin.Z))).ToList();
        if (doors.Count == 0) return;
        var open = new HashSet<uint>();
        foreach (var p in pts)
            foreach (var (d, o) in doors)
                if (!open.Contains(d.Index) && Vector3.DistanceSquared(p, o) < r * r)
                {
                    d.AcceptInput("Open");
                    open.Add(d.Index);
                }
        if (open.Count > 0) Logger.LogInformation("{n} door(s) opened", open.Count);
    }

    // the map's breakables near these points broken (a vent cover, a window the players went through). Nuke's vent is a
    // prop_dynamic named nuke_vent (448 -1403 -416), not a func_breakable
    void Break(List<Vector3> pts, float r = 72f)
    {
        var n = 0;
        foreach (var cls in new[] { "func_breakable", "func_breakable_surf", "prop_dynamic" })
            foreach (var e in Utilities.FindAllEntitiesByDesignerName<CBaseEntity>(cls))
            {
                if (!e.IsValid || e.AbsOrigin == null) continue;
                var name = (e.Entity?.Name ?? "").ToLowerInvariant();
                if (cls == "prop_dynamic" && (e.Health <= 0 || !(name.Contains("vent") || name.Contains("window") || name.Contains("glass")))) continue;
                var o = new Vector3(e.AbsOrigin.X, e.AbsOrigin.Y, e.AbsOrigin.Z);
                if (pts.Any(p => Vector3.DistanceSquared(p, o) < r * r)) { e.AcceptInput("Break"); n++; Logger.LogInformation("broken: {c} {n}", cls, name); }
            }
        if (n > 0) Logger.LogInformation("{n} breakable(s) broken", n);
    }

    // a path's point at a (fractional) frame
    static Vector3 PathAt(Track t, float ft)
    {
        var i = Math.Clamp((int)ft, 0, Math.Max(0, t.Frames - 2));
        return t.Frames < 2 ? Pos(t, 0) : Vector3.Lerp(Pos(t, i), Pos(t, i + 1), Math.Clamp(ft - i, 0f, 1f));
    }

    // a bot leaves its recorded path and plays on its own: it moves again by itself, with its grenades
    void Free(int slot, CCSPlayerController c, Track t)
    {
        if (!free.Add(slot)) return;
        var pw = c.PlayerPawn.Value;
        if (pw != null && pw.IsValid) Freeze(pw, false);
        if (phase == "live") Arm(c, t);
        // the planter off its way before the plant: it carries the bomb, the game's AI plants it if it lives (06/10: "il
        // n'y avait personne sur le B, impossible qu'ils plantent: le seul qui allait planter est mort")
        if (phase == "live" && cur?.Bomb is { F: > 0 } b && !bombDone && t.Sid == b.By && t.Team == 2)
        { c.GiveNamedItem("weapon_c4"); bombDone = true; Logger.LogInformation("{n} plays on its own with the bomb", t.Name); }
    }

    // a bot playing on its own: its grenades back (the AI throws them). A situation: the ones it had in the match; a
    // defense's attacker: a flash and a molotov
    void Arm(CCSPlayerController? c, Track t)
    {
        if (c == null || !c.IsValid || !c.PawnIsAlive) return;
        var nades = t.Weapons.Where(w => w.Contains("grenade") || w.Contains("flashbang") || w.Contains("molotov")).ToList();
        if (nades.Count == 0 && drill?.Mode == "defend") nades = new() { "weapon_flashbang", t.Team == 2 ? "weapon_molotov" : "weapon_incgrenade" };
        foreach (var w in nades) c.GiveNamedItem(w);
    }

    static Vector3 Pos(Track t, int i) => new(t.Path[i * 5], t.Path[i * 5 + 1], t.Path[i * 5 + 2]);
    static Vector3 Ang(Track t, int i) => new(t.Path[i * 5 + 4], t.Path[i * 5 + 3], 0);

    // everyone on the first frame, loadouts of the demo, 3 s to look around, then it plays. The doors the real players
    // went through are open (04/10: shot through a door that was open for them in the match, closed here). A bot on
    // its path walks it (OnTick); an aim target holds its spot without moving
    void Place()
    {
        if (cur == null) return;
        var went = cur.Players.SelectMany(t => Enumerable.Range(0, t.Frames).Where(k => k % 4 == 0).Select(k => Pos(t, k)))
            .Concat(cur.Trail.Where(p => p.Length >= 3).Select(p => new Vector3(p[0], p[1], p[2]))).ToList();
        OpenDoors(went);
        Break(went);   // a vent the players went through was broken (06/10, Nuke: "la vent est censée être cassée")
        foreach (var (slot, t) in bots)
        {
            var c = Utilities.GetPlayerFromSlot(slot);
            if (c == null || !c.IsValid) continue;
            if (!c.PawnIsAlive) c.Respawn();
            Loadout(c, t);
            t.NadeNext = 0;
            var pw = c.PlayerPawn.Value;
            if (pw == null) continue;
            pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero);
            Freeze(pw, t.Hold);
        }
        var me = cur.Players.FirstOrDefault(t => t.Me);
        if (mode == "actor" && me != null)
            foreach (var h in Humans())
            {
                if ((int)h.Team != me.Team) continue;
                if (!h.PawnIsAlive) h.Respawn();
                Loadout(h, me, cur.Kind is "death" or "clutch" ? Math.Max(MinHp, me.Hp) : null);
                var pawn = h.PlayerPawn.Value;
                if (pawn == null) continue;
                pawn.Teleport(Pos(me, 0), Upright(Ang(me, 0)), Vector3.Zero);
                Freeze(pawn, true);
            }
        kills = dmg = 0; devSum = 0; devN = 0;
        humanDead = traded = false; tradeKiller = -1;
        // the demo's plant: already down at the start, or later by its planter (yours later: you plant it yourself)
        bombLive = false;
        bombDone = cur.Bomb == null || (cur.Bomb.F > 0 && mode == "actor" && cur.Players.Any(t => t.Me && t.Sid == cur.Bomb.By));
        SessionPlaced();
        phase = "countdown";
        var cd = cur.Kind is "death" or "clutch" ? 5 : 3;   // a situation: time to read it and get ready
        countdownEnd = Server.TickCount + cd * 64;
        var g = generation;
        for (int s = cd; s >= 1; s--)
        {
            var n = s;
            AddTimer(cd - n, () => { if (g == generation && !SessionCount(n)) foreach (var h in Humans()) h.PrintToCenter($"{cur?.Title}   {n}"); });
        }
    }

    void Go()
    {
        // a situation whose enemies are all dead already (a bot that left): not a win, set up again (once)
        if (mode == "actor" && cur is { Kind: "death" or "clutch" })
        {
            var foes = bots.Where(b => b.Value.Team != cur.Team).Select(b => Utilities.GetPlayerFromSlot(b.Key)).ToList();
            if (foes.Count > 0 && foes.All(c => c == null || !c.IsValid || !c.PawnIsAlive))
            {
                Logger.LogInformation("{id}: no enemy alive at the start, set up again", cur.Id);
                if (emptyTries++ < 1) { builtFor = null; Setup(); return; }
                emptyTries = 0;   // still none: skipped, never a win for nothing
                if (sess != null && drill != null) { phase = "live"; DrillDone(false, "skipped", 0, "no enemy at the start"); return; }
            }
            emptyTries = 0;
        }
        phase = "live";
        t0 = Server.TickCount;
        nextNade = 0;
        if (cur?.Bomb is { F: <= 0 } && !bombDone) PlantBomb();   // after the plant: it ticks from the first second
        // an aim drill: a reaction time before a target can hurt you (04/10, Office: killed 0.06 s after GO)
        if (cur?.Kind == "aim") protectUntil = Server.TickCount + 48;
        SessionGo();
        foreach (var h in Humans()) { var pw = h.PlayerPawn.Value; if (pw != null) Freeze(pw, false); h.PrintToCenter("GO"); }
    }

    bool Alive(string sid)
    {
        if (gone.Contains(sid)) return false;
        return true;
    }

    void OnTick()
    {
        // the center text (the drill's card) blinks off every second while the game rules say a restart is
        // pending: set on every tick (CS2FlashingHtmlHudFix, the workaround found by Poggu)
        rules ??= Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
        if (rules != null) rules.GameRestart = rules.RestartRoundTime < Server.CurrentTime;
        var now = Server.TickCount;
        if (now - lastBeat >= 64 || now < lastBeat) { lastBeat = now; Beat(); }   // the tick count starts over with each map
        if (now < hudSent) hudSent = 0;
        HudTick();
        CamTick();
        if (cur == null || (phase != "countdown" && phase != "live")) return;
        if (phase == "countdown" && now >= countdownEnd) Go();
        var f = phase == "live" ? (now - t0) / (float)cur.Step : 0f;
        var mePawn = Humans().Select(h => h.PlayerPawn.Value).FirstOrDefault(p => p != null && p.IsValid && p.LifeState == (byte)LifeState_t.LIFE_ALIVE);
        uint[]? seen = null;
        if (mePawn != null && mode == "actor") { var m = mePawn.EntitySpottedState.SpottedByMask; seen = new[] { m[0], m[1] }; }
        Vector3? mePos = mode == "actor" && mePawn?.AbsOrigin is { } mo ? new Vector3(mo.X, mo.Y, mo.Z) : null;
        var meSid = cur.Players.FirstOrDefault(t => t.Me)?.Sid ?? "";
        int maxFrames = 0;
        foreach (var (slot, t) in bots)
        {
            maxFrames = Math.Max(maxFrames, t.Frames);
            if (free.Contains(slot) || gone.Contains(t.Sid)) continue;
            var c = Utilities.GetPlayerFromSlot(slot);
            var pawn = c?.PlayerPawn.Value;
            if (c == null || pawn == null || !c.PawnIsAlive) { gone.Add(t.Sid); Logger.LogInformation("gone {n} at {f}", t.Name, (int)f); continue; }
            if (t.Strafe) continue;   // an aim map's strafing target: the session moves it
            if (t.Hold)
            {
                // a target on its spot. A prefire's, a wallbang's or a flick's holds its angle and never fires (06/10: "fais
                // pas bouger les bots sur le préfire"); a duel's aims on its own and counts how long it has seen you
                pawn.Teleport(Pos(t, 0), t.Still ? Upright(Ang(t, 0)) : null, Vector3.Zero);
                if (t.Still) HoldAim(pawn, Ang(t, 0), t.Duck);
                else if (phase == "live" && seen != null && (seen[slot / 32] & (1u << (slot % 32))) != 0) contact[slot] = contact.GetValueOrDefault(slot) + 1;
                continue;
            }
            var ft = f - t.Start;
            var i = Math.Max(0, (int)ft);
            // a defense's attacker throws the grenades of the real hit it walks, at their moment
            while (phase == "live" && t.NadeNext < t.TrackNades.Count && t.TrackNades[t.NadeNext].F <= ft) ThrowAs(c, pawn, t.TrackNades[t.NadeNext++]);
            if (i >= t.Frames - 1 && drill?.Mode == "defend" && sess != null && !engaged.ContainsKey(slot))
            {   // a defense's attacker at the end of its way without meeting you: another one comes on a real way (06/10:
                // "un mec dans mon spawn, derrière": it roamed on its own)
                gone.Add(t.Sid);
                pawn.CommitSuicide(false, true);
                Logger.LogInformation("again {n} at {f}", t.Name, (int)f);
                continue;
            }
            if (i >= t.Frames - 1)
            {
                // the end of its recorded path: a death in the demo (by a player still alive here, or the world), or the
                // window is over / you were the killer: the bot plays on from there
                if (t.Death >= 0 && t.Killer != meSid && (t.Killer == "" || !cur.Players.Any(q => q.Sid == t.Killer) || Alive(t.Killer)))
                { DemoKill(c, pawn, t); gone.Add(t.Sid); Logger.LogInformation("demo kill {n} at {f}", t.Name, (int)f); }
                else { Free(slot, c, t); Logger.LogInformation("free {n} at {f} (death {d}, killer {k})", t.Name, (int)f, t.Death, t.Killer); }
                continue;
            }
            var a = Math.Clamp(ft - i, 0f, 1f);
            var p0 = Pos(t, i); var p1 = Pos(t, i + 1);
            var pos = Vector3.Lerp(p0, p1, a);
            if (phase == "live" && mode == "spec" && pawn.AbsOrigin != null)
            { var o = pawn.AbsOrigin; devSum += Vector3.Distance(new Vector3(o.X, o.Y, o.Z), pos); devN++; }
            // it has seen you for a reaction time: it fights you now, its aim is the game's. For 1.5 s it still moves the
            // way the real player moved there (his peek, his strafe, his stop: 06/10, "les bots ne se déplacent pas comme des
            // joueurs"), then it plays on its own
            var eng = engaged.TryGetValue(slot, out var et);
            if (eng && Server.TickCount - et > EngageTicks) { Free(slot, c, t); continue; }
            if (!eng && phase == "live" && seen != null && (seen[slot / 32] & (1u << (slot % 32))) != 0 && (contact[slot] = contact.GetValueOrDefault(slot) + 1) >= ReactTicks)
            { engaged[slot] = Server.TickCount; eng = true; Logger.LogInformation("contact {n} at {f}", t.Name, (int)f); }
            var here = pawn.AbsOrigin is { } ho ? new Vector3(ho.X, ho.Y, ho.Z) : pos;
            if (phase == "live" && mePos != null && t.Team != cur.Team && Vector3.DistanceSquared(here, mePos.Value) < Near * Near)
            {   // you are right on it: a player would notice you, path or not
                Free(slot, c, t); Logger.LogInformation("close {n} at {f}", t.Name, (int)f); continue;
            }
            // the real player's way and facing; until it reacts, the real player's aim too (not yet yours)
            var y0 = t.Path[i * 5 + 3]; var dy = ((t.Path[i * 5 + 8] - y0 + 540f) % 360f) - 180f;
            var pitch = t.Path[i * 5 + 4] + (t.Path[i * 5 + 9] - t.Path[i * 5 + 4]) * a;
            var face = new Vector3(0, y0 + dy * a, 0);
            // it walks: its speed takes it to where the path is at the next tick, and the game moves it (its legs move
            // like a player's; moved by teleports it slid, 04/10). Too far from its path (a closed door, a box it
            // jumped on in the match), or not live yet: put back on it
            var next = PathAt(t, ft + 1f / cur.Step) - here;
            if (eng && (new Vector2(next.X, next.Y).Length() > 72f || Math.Abs(next.Z) > 56f)) { Free(slot, c, t); continue; }   // fighting, off its way: on its own
            if (phase != "live" || new Vector2(next.X, next.Y).Length() > 72f || Math.Abs(next.Z) > 56f)
                pawn.Teleport(pos, face, phase == "live" ? (p1 - p0) * (cur.Rate / (float)cur.Step) : Vector3.Zero);
            else
            {   // the path's own speed, plus a third of the gap beyond it each tick (all of a gap at once: 786 u/s jolts)
                var pv = (p1 - p0) * (cur.Rate / (float)cur.Step);
                var gap = next - pv / 64f;
                var v = new Vector2(pv.X + gap.X * 22f, pv.Y + gap.Y * 22f);
                // a player walking there (shift, under 135 u/s) was silent: so is the bot, catching up never makes it run
                // (06/10: "des bruits de pas alors qu'il n'y a personne")
                if (new Vector2(pv.X, pv.Y).Length() < 135f && v.Length() > 126f) v = Vector2.Normalize(v) * 126f;
                pawn.Teleport(null, eng ? null : face, new Vector3(v.X, v.Y, pawn.AbsVelocity?.Z ?? 0f));   // fighting: its own aim
            }
            if (!eng && pawn.EyeAngles is { } eye && Math.Abs(eye.X - pitch) > 0.5f)
            { eye.X = pitch; Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_angEyeAngles"); }
        }
        if (phase != "live") return;
        if (!bombDone && cur.Bomb != null && f >= cur.Bomb.F)   // the demo's plant: its planter alive here and still on its way
        {
            var pl = bots.FirstOrDefault(kv => kv.Value.Sid == cur.Bomb.By);
            if (gone.Contains(cur.Bomb.By)) { bombDone = true; Logger.LogInformation("no plant: its planter is dead here"); }
            else if (pl.Value != null && free.Contains(pl.Key)) { bombDone = true; Logger.LogInformation("no plant: its planter plays on its own"); }
            else PlantBomb();
        }
        SessionTick();
        if (cur == null || phase != "live" || cur.Kind is "aim" or "nade") return;   // their end is the session's
        while (nextNade < cur.Nades.Count && cur.Nades[nextNade].F <= f) Throw(cur.Nades[nextNade++]);
        if (mode == "spec" && devN > 0 && (now - t0) % 320 == 0)
            Logger.LogInformation($"drift {devSum / devN:F1} u over {devN} samples");
        if (humanDead)   // you died: traded or not, the drill ends (the bots keep moving meanwhile)
        {
            if (traded) Finish("traded");
            else if (now > tradeUntil) Finish("dead");
            return;
        }
        // a CT once the bomb is down wins by the defuse, not by the last kill; the window then lasts until it is defused
        // or blows up
        var defuse = bombLive && cur.Team == 3;
        var foes = bots.Where(b => b.Value.Team != cur.Team).ToList();
        if (mode == "actor" && foes.Count > 0 && foes.All(b => gone.Contains(b.Value.Sid)) && !defuse) { Finish("won"); return; }
        var endF = cur.Kind == "clutch" ? maxFrames + 64 * 10 / cur.Step : maxFrames + 64 * 2 / cur.Step;
        if (f >= endF + (bombLive ? 45 * 64 / cur.Step : 0)) Finish(mode == "spec" ? "watched" : "survived");
    }

    // a death of the demo, as it was heard and seen: its killer's shots (the sound of its gun, where it stands) and the kill
    // feed's line, then the death (04/10: "when the Ts kill my teammates I hear them shoot: I want the real situation")
    void DemoKill(CCSPlayerController c, CCSPlayerPawn pawn, Track t)
    {
        var kc = bots.Where(b => b.Value.Sid == t.Killer).Select(b => Utilities.GetPlayerFromSlot(b.Key)).FirstOrDefault(x => x is { IsValid: true, PawnIsAlive: true });
        if (kc?.PlayerPawn.Value is { } kp)
        {
            // the gun of the match's kill (the killer takes it out), else the one it holds
            var w = t.KillWeapon != "" ? t.KillWeapon : kp.WeaponServices?.ActiveWeapon.Value?.DesignerName?.Replace("weapon_", "") ?? "";
            if (t.KillWeapon != "") kc.ExecuteClientCommandFromServer($"use weapon_{t.KillWeapon}");
            if (ShotSound.TryGetValue(w, out var snd))
                for (int k = 0; k < (w is "awp" or "ssg08" or "deagle" or "revolver" ? 1 : 3); k++)
                    AddTimer(0.09f * k, () => { if (kp.IsValid) kp.EmitSound(snd); });
            try
            {
                var ev = NativeAPI.CreateEvent("player_death", true);
                NativeAPI.SetEventPlayerController(ev, "userid", c.Handle);
                NativeAPI.SetEventPlayerController(ev, "attacker", kc.Handle);
                NativeAPI.SetEventString(ev, "weapon", w == "" ? "world" : w);
                NativeAPI.FireEvent(ev, false);
            }
            catch (Exception e) { Logger.LogInformation("kill feed: {m}", e.Message); }
        }
        pawn.CommitSuicide(false, true);   // its own death event stays out of the feed (the Pre hook)
    }

    // the sound event of each gun's shot
    static readonly Dictionary<string, string> ShotSound = new()
    {
        ["ak47"] = "Weapon_AK47.Single", ["m4a1"] = "Weapon_M4A1.Single", ["m4a1_silencer"] = "Weapon_M4A1.Silenced", ["awp"] = "Weapon_AWP.Single",
        ["deagle"] = "Weapon_DEagle.Single", ["glock"] = "Weapon_Glock.Single", ["hkp2000"] = "Weapon_HKP2000.Single", ["usp_silencer"] = "Weapon_USP.SilencedShot",
        ["p250"] = "Weapon_P250.Single", ["tec9"] = "Weapon_Tec9.Single", ["fiveseven"] = "Weapon_FiveSeven.Single", ["cz75a"] = "Weapon_CZ75A.Single",
        ["elite"] = "Weapon_Elite.Single", ["revolver"] = "Weapon_Revolver.Single", ["famas"] = "Weapon_FAMAS.Single", ["galilar"] = "Weapon_GalilAR.Single",
        ["aug"] = "Weapon_AUG.Single", ["sg556"] = "Weapon_SG556.Single", ["ssg08"] = "Weapon_SSG08.Single", ["scar20"] = "Weapon_SCAR20.Single",
        ["g3sg1"] = "Weapon_G3SG1.Single", ["mp9"] = "Weapon_MP9.Single", ["mac10"] = "Weapon_MAC10.Single", ["mp7"] = "Weapon_MP7.Single",
        ["mp5sd"] = "Weapon_MP5SD.Single", ["ump45"] = "Weapon_UMP45.Single", ["p90"] = "Weapon_P90.Single", ["bizon"] = "Weapon_bizon.Single",
        ["nova"] = "Weapon_Nova.Single", ["xm1014"] = "Weapon_XM1014.Single", ["mag7"] = "Weapon_Mag7.Single", ["sawedoff"] = "Weapon_Sawedoff.Single",
        ["m249"] = "Weapon_M249.Single", ["negev"] = "Weapon_Negev.Single",
    };

    // the demo's bomb on the ground where it was planted, ticking with the time it had left: the game's own planted_c4,
    // made the way retake servers plant it, and the game told (HUD, bots)
    void PlantBomb()
    {
        bombDone = true;
        var b = cur?.Bomb;
        if (b == null) return;
        try
        {
            foreach (var old in Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4")) old.Remove();
            var c4 = Utilities.CreateEntityByName<CPlantedC4>("planted_c4");
            if (c4?.AbsOrigin == null) return;
            c4.AbsOrigin.X = b.Pos[0]; c4.AbsOrigin.Y = b.Pos[1]; c4.AbsOrigin.Z = b.Pos[2];
            c4.HasExploded = false;
            c4.BombSite = b.Site;
            c4.BombTicking = true;
            c4.CannotBeDefused = false;
            c4.DispatchSpawn();
            var left = Math.Max(3f, b.Left);
            Server.NextFrame(() =>
            {
                if (!c4.IsValid) return;
                c4.C4Blow = Server.CurrentTime + left;
                Utilities.SetStateChanged(c4, "CPlantedC4", "m_flC4Blow");
            });
            if (rules != null) { rules.BombPlanted = true; rules.BombDefused = false; }
            bombLive = true;
            var by = bots.Where(kv => kv.Value.Sid == b.By).Select(kv => Utilities.GetPlayerFromSlot(kv.Key)).FirstOrDefault(x => x is { IsValid: true })
                     ?? Utilities.GetPlayers().FirstOrDefault(x => x is { IsValid: true } && (int)x.Team == 2);
            if (by != null)
            {
                var ev = NativeAPI.CreateEvent("bomb_planted", true);
                NativeAPI.SetEventPlayerController(ev, "userid", by.Handle);
                NativeAPI.SetEventInt(ev, "site", b.Site);
                NativeAPI.FireEvent(ev, false);
            }
            Logger.LogInformation("bomb planted at {x:F0} {y:F0} {z:F0} site {s}, {l:F1} s left", b.Pos[0], b.Pos[1], b.Pos[2], b.Site, left);
        }
        catch (Exception e) { Logger.LogInformation("bomb: {m}", e.Message); }
    }

    // a grenade of the demo, thrown again from the same point at the same speed, if its thrower is alive here (yours: you
    // throw it yourself)
    void Throw(Nade n)
    {
        if (cur == null || gone.Contains(n.By) || (mode == "actor" && cur.Players.Any(t => t.Me && t.Sid == n.By))) return;
        var slot = bots.Where(b => b.Value.Sid == n.By).Select(b => (int?)b.Key).FirstOrDefault();
        var c = slot == null ? null : Utilities.GetPlayerFromSlot(slot.Value);
        var pawn = c?.PlayerPawn.Value;
        if (c == null || pawn == null || !c.PawnIsAlive) return;
        ThrowAs(c, pawn, n);
    }

    void ThrowAs(CCSPlayerController c, CCSPlayerPawn pawn, Nade n)
    {
        var cls = n.Type switch { "smoke" => "smokegrenade_projectile", "flash" => "flashbang_projectile", "he" => "hegrenade_projectile",
            "molotov" => "molotov_projectile", "decoy" => "decoy_projectile", _ => "" };
        if (cls == "") return;
        try
        {
            if (n.Type is "smoke" or "he" or "molotov")
            {
                var o = new CVector(n.P[0], n.P[1], n.P[2]);
                var v = new CVector(n.V[0], n.V[1], n.V[2]);
                var spin = new CVector(600, 0, 0);
                if (n.Type == "smoke" && smokeCreate != null) smokeCreate.Invoke(o.Handle, new QAngle(0, 0, 0).Handle, v.Handle, spin.Handle, pawn.Handle, 45, c.TeamNum);
                else if (n.Type == "he" && heCreate != null) heCreate.Invoke(o.Handle, new QAngle(0, 0, 0).Handle, v.Handle, spin.Handle, pawn.Handle, 44);
                else if (n.Type == "molotov" && molotovCreate != null) molotovCreate.Invoke(o.Handle, new QAngle(0, 0, 0).Handle, v.Handle, spin.Handle, pawn.Handle, n.Inc ? 48 : 46);
                else return;
                Logger.LogInformation("nade {t} by {n} at {f}", n.Type, c.PlayerName, n.F);
                return;
            }
            var e = Utilities.CreateEntityByName<CBaseCSGrenadeProjectile>(cls);
            if (e == null) return;
            if (n.Inc) new CMolotovProjectile(e.Handle).IsIncGrenade = true;
            var pos = new Vector3(n.P[0], n.P[1], n.P[2]);
            var vel = new Vector3(n.V[0], n.V[1], n.V[2]);
            e.InitialPosition.X = pos.X; e.InitialPosition.Y = pos.Y; e.InitialPosition.Z = pos.Z;
            e.InitialVelocity.X = vel.X; e.InitialVelocity.Y = vel.Y; e.InitialVelocity.Z = vel.Z;
            e.Elasticity = 0.33f;
            e.IsLive = false;
            e.DmgRadius = 350f;
            e.Damage = 99f;
            e.TeamNum = c.TeamNum;
            e.Thrower.Raw = c.PlayerPawn.Raw;
            e.OriginalThrower.Raw = c.PlayerPawn.Raw;
            e.OwnerEntity.Raw = c.PlayerPawn.Raw;
            e.Teleport(pos, Vector3.Zero, vel);
            e.DispatchSpawn();
            e.AcceptInput("InitializeSpawnFromWorld");
            e.AcceptInput("FireUser1", pawn, pawn);
            Logger.LogInformation("nade {t} by {n} at {f}", n.Type, c.PlayerName, n.F);
        }
        catch (Exception ex) { Logger.LogInformation("nade {t}: {m}", n.Type, ex.Message); }
    }

    HookResult OnDeath(EventPlayerDeath e, GameEventInfo i)
    {
        if (cur == null || phase != "live") return HookResult.Continue;
        var v = e.Userid;
        if (v != null && v.IsValid && bots.TryGetValue(v.Slot, out var t)) gone.Add(t.Sid);
        Logger.LogInformation("death {f}/{s}: {v} by {a} ({w})", (Server.TickCount - t0) / cur.Step, cur.Id, v?.PlayerName, e.Attacker?.PlayerName, e.Weapon);
        if (e.Attacker is { IsValid: true, IsBot: false } && v != null && v.IsBot) kills++;
        if (humanDead && v != null && v.IsValid && v.Slot == tradeKiller && Server.TickCount <= tradeUntil) traded = true;   // your killer died right after: traded
        if (cur.Kind is "death" or "clutch" && v is { IsValid: true, IsBot: true } && bots.TryGetValue(v.Slot, out var tv) && tv.Team == cur.Team
            && v.PlayerPawn.Value?.AbsOrigin is { } dp)
            DrawX(new Vector3(dp.X, dp.Y, dp.Z));   // an ally down: where it fell, where the enemies are (06/10)
        if (SessionDeath(e, v)) return HookResult.Continue;   // a defense: you come back
        if (mode == "actor" && v is { IsValid: true, IsBot: false })
        {
            // a situation: 3 s to see if a teammate trades you (your killer dead), unless nobody is left to
            var mates = bots.Any(b => b.Value.Team == cur.Team && !gone.Contains(b.Value.Sid));
            if (cur.Kind is "death" or "clutch" && mates && e.Attacker is { IsValid: true, IsBot: true } k)
            {
                humanDead = true; tradeKiller = k.Slot; tradeUntil = Server.TickCount + 3 * 64;
                return HookResult.Continue;
            }
            AddTimer(0.1f, () => Finish("dead"));
        }
        return HookResult.Continue;
    }

    HookResult OnHurt(EventPlayerHurt e, GameEventInfo i)
    {
        if (phase == "live" && e.Attacker is { IsValid: true, IsBot: false } && e.Userid is { IsBot: true } v)
        {
            dmg += e.DmgHealth;
            if (bots.TryGetValue(v.Slot, out var hit) && !hit.Hold && !hit.Strafe) Free(v.Slot, v, hit);   // hit: it reacts like a player (a target stays)
        }
        return HookResult.Continue;
    }

    // bots never hurt each other: only the demo (a recorded death) or you kill a bot
    HookResult OnTakeDamage(CEntityInstance victim, CTakeDamageInfo info)
    {
        if (cur == null) return HookResult.Continue;
        try
        {
            // stuff: your own grenades never hurt you; from their side, what they would take is counted
            if (cur.Kind == "nade" && victim.DesignerName == "player" && new CCSPlayerPawn(victim.Handle).OriginalController.Value is { IsBot: false })
            {
                if (nadeStage != "theirs") return HookResult.Handled;
                // from their side you take it, never to death (04/10: "I don't see the damage it does to me")
                var vp = new CCSPlayerPawn(victim.Handle);
                theirsDmg += (int)info.Damage;
                info.Damage = Math.Min(info.Damage, Math.Max(0, vp.Health - 1));
                return HookResult.Continue;
            }
            if (victim.DesignerName == "player" && Server.TickCount < protectUntil && new CCSPlayerPawn(victim.Handle).OriginalController.Value is { IsBot: false })
                return HookResult.Handled;   // a defense: you just came back on your spot
            if (victim.DesignerName == "player" && (phase == "setup" || phase == "countdown") && new CCSPlayerPawn(victim.Handle).OriginalController.Value is { IsBot: false })
                return HookResult.Handled;   // before GO nothing hurts you (06/10: killed during an aim drill's countdown, a minute on the floor)
            var att = info.Attacker.Value;
            var hurt = info.Inflictor.Value?.DesignerName == "trigger_hurt" || att?.DesignerName == "trigger_hurt";   // logged "by null (trigger_hurt)"
            if (victim.DesignerName == "player" && hurt && new CCSPlayerPawn(victim.Handle).OriginalController.Value is { IsBot: false })
                return HookResult.Handled;   // a map hurt zone (Boulder): no death by the map in training
            if (victim.DesignerName != "player" || att == null || att.DesignerName != "player") return HookResult.Continue;
            var vc = new CCSPlayerPawn(victim.Handle).OriginalController.Value;
            var ac = new CCSPlayerPawn(att.Handle).OriginalController.Value;
            // a bot on its recorded path dies only as recorded (a demo death is the bot on itself); one playing on its own
            // (it saw you) can be shot by anyone: your teammates can trade you
            if (vc is { IsBot: true } && ac is { IsBot: true } && vc.Slot != ac.Slot && !free.Contains(vc.Slot)) return HookResult.Handled;
            if (drill?.Mode == "prefire" && vc is { IsBot: false } && ac is { IsBot: true }) return HookResult.Handled;   // prefire: they don't shoot
            // the aim map: still and strafing targets never hurt you; a duel's only once it has seen you a player's reaction
            // time (06/10: "ils me préfirent, ils savent où je suis, c'est un temps de réaction terrible")
            if (drill?.Mode == "range" && vc is { IsBot: false } && ac is { IsBot: true } && (drill.Variant != "duel" || contact.GetValueOrDefault(ac.Slot) < DuelReact))
                return HookResult.Handled;
        }
        catch (Exception) { }
        return HookResult.Continue;
    }

    void Finish(string outcome)
    {
        if (cur == null || phase != "live") return;
        phase = "done";
        var alive = (Server.TickCount - t0) / 64.0;
        if (sess != null && drill != null) { SessionFinish(outcome, alive); return; }
        ClearLine();
        if (mode == "actor") outcome = SitOutcome(outcome);
        var line = JsonSerializer.Serialize(new Dictionary<string, object> {
            ["id"] = cur.Id, ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["outcome"] = outcome, ["mode"] = mode,
            ["kills"] = kills, ["dmg"] = dmg, ["alive_s"] = Math.Round(alive, 1), ["difficulty"] = difficulty,
            ["drift"] = devN > 0 ? Math.Round(devSum / devN, 1) : -1 });
        try { File.AppendAllText(System.IO.Path.Combine(Dir, "results.jsonl"), line + "\n"); } catch (Exception e) { Logger.LogInformation($"{e.Message}"); }
        var msg = outcome switch { "won" => "\x04WON\x01", "survived" => "\x04SURVIVED\x01", "traded" => "\x04TRADED\x01",
            "kill" => "\x04KILL, THEN DEAD\x01", "passive" => "\x02NO KILL\x01", "dead" => "\x02DEAD\x01",
            "defused" => BombWon(outcome) ? "\x04DEFUSED\x01" : "\x02DEFUSED\x01", "exploded" => BombWon(outcome) ? "\x04BOMB EXPLODED\x01" : "\x02BOMB EXPLODED\x01",
            _ => outcome };
        All($"{msg} · {kills} kill(s) · {dmg} dmg · {alive:F1} s — again in 3 s (!n next · !p previous · !spec · !stop)");
        var g = generation;
        AddTimer(3f, () => { if (g == generation && phase == "done" && cur != null) Setup(); });
    }

    // a situation's outcome: a kill or a trade is needed. won / survived with no kill of yours: passive; dead after a
    // kill: kill (one for one); traded and dead stay
    string SitOutcome(string o) => o switch
    {
        "won" or "survived" => kills >= 1 ? o : "passive",
        "dead" => kills >= 1 ? "kill" : "dead",
        _ => o,   // the bomb decides: defused or exploded
    };

    // the bomb's end is yours when you defuse it as a CT, or it blows up as a T
    bool BombWon(string o) => (o == "defused" && cur?.Team == 3) || (o == "exploded" && cur?.Team == 2);

    void Beat()
    {
        try
        {
            var o = new Dictionary<string, object?> { ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["humans"] = Humans().Count(),
                ["scenario"] = cur?.Id, ["state"] = phase, ["mode"] = mode, ["map"] = Server.MapName };
            foreach (var (k, v) in SessionBeat()) o[k] = v;
            File.WriteAllText(System.IO.Path.Combine(Dir, "live.json"), JsonSerializer.Serialize(o));
        }
        catch (Exception) { }
    }
}
