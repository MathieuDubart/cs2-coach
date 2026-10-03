// The coach's replays: a situation of your own demo played again. The bots follow exactly the recorded paths of the
// other players (where they went, where they looked) and aim and shoot on their own as soon as they see you; you take
// your own spot (actor) or watch it all (spec: a bot plays your spot too). A bot killed in the demo dies at the same
// moment only if its killer is still alive here (you changed the story: it lives on); one you killed in the demo waits
// for you at the end of its path. Bots never hurt each other. Each try is appended to coach/results.jsonl.
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
    [JsonPropertyName("hold")] public bool Hold { get; set; }   // stays on its spot (aim targets): only its aim is its own
    public int Frames => Path.Length / 5;
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
    int t0, countdownEnd, kills, dmg, generation, lastBeat, nextNade;
    bool awaitRestart;
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
        RegisterListener<Listeners.OnMapStart>(_ =>
        {
            phase = cur != null || sess != null ? "setup" : "idle";
            AddTimer(4f, () => { Server.ExecuteCommand("sv_hibernate_when_empty 0"); if (sess != null) SessionResume(); else if (cur != null) Setup(); });
        });
        RegisterEventHandler<EventRoundStart>(OnRoundStart);
        RegisterEventHandler<EventPlayerDeath>(OnDeath);
        RegisterEventHandler<EventPlayerHurt>(OnHurt);
        RegisterEventHandler<EventPlayerConnectFull>((e, _) =>
        {
            if (e.Userid is { IsBot: false }) { if (sess != null) AddTimer(3f, SessionResume); else if (cur != null) AddTimer(2f, Setup); }
            return HookResult.Continue;
        });
        RegisterListener<Listeners.OnEntityTakeDamagePre>(OnTakeDamage);
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
        AddCommand("css_stop", "stop the replay (or the session)", (p, c) =>
        {
            if (sess != null) { EndSession(true); return; }
            cur = null; phase = "idle"; bots.Clear(); builtFor = null; Server.ExecuteCommand("bot_kick");
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
        gone.Clear(); free.Clear();
        if (mode == "actor" && !Humans().Any()) { phase = "waiting"; return; }   // starts when you join
        phase = "setup";
        // the same situation again: the same bots, only a clean round (fast retries)
        var key = $"{cur.Id}|{mode}|{difficulty}";
        if (builtFor == key && bots.Count > 0 && bots.Keys.All(sl => Utilities.GetPlayerFromSlot(sl) is { IsValid: true, IsBot: true }))
        {
            Teams();
            awaitRestart = true;
            Server.ExecuteCommand("mp_restartgame 1");
            return;
        }
        bots.Clear();
        builtFor = key;
        foreach (var cmd in new[] { "mp_warmup_end", "mp_ignore_round_win_conditions 1", "mp_freezetime 0", "mp_roundtime 60",
                     "mp_roundtime_defuse 60", "mp_roundtime_hostage 60", "mp_buytime 0", "mp_autoteambalance 0", "mp_limitteams 0",
                     "mp_friendlyfire 0", "mp_autokick 0", "mp_halftime 0", "mp_maxrounds 99", "mp_match_can_clinch 0",
                     "mp_give_player_c4 0", "mp_death_drop_gun 0", "mp_randomspawn 0", "bot_quota_mode normal",
                     "bot_join_after_player 0", "bot_chatter off", "sv_hibernate_when_empty 0", $"bot_difficulty {difficulty}", "bot_kick" })
            Server.ExecuteCommand(cmd);
        var want = cur.Players.Where(t => !t.Me || mode == "spec").ToList();
        AddTimer(0.3f, () =>
        {
            if (g != generation) return;
            foreach (var t in want) Server.ExecuteCommand(t.Team == 2 ? "bot_add_t" : "bot_add_ct");
            Teams();
        });
        AddTimer(1.5f, () =>
        {
            if (g != generation || cur == null) return;
            foreach (var team in new[] { 2, 3 })
            {
                var tracks = want.Where(t => t.Team == team).ToList();
                var bs = Utilities.GetPlayers().Where(p => p is { IsValid: true, IsBot: true } && (int)p.Team == team).ToList();
                for (int i = 0; i < Math.Min(tracks.Count, bs.Count); i++)
                {
                    bots[bs[i].Slot] = tracks[i];
                    bs[i].PlayerName = tracks[i].Me ? tracks[i].Name + " (you)" : tracks[i].Name;
                    Utilities.SetStateChanged(bs[i], "CBasePlayerController", "m_iszPlayerName");
                }
                if (bs.Count != tracks.Count) Logger.LogInformation($"team {team}: {bs.Count} bots for {tracks.Count} tracks");
            }
            awaitRestart = true;
            Server.ExecuteCommand("mp_restartgame 1");
        });
    }

    void Teams()
    {
        if (cur == null) return;
        var team = mode == "spec" ? CsTeam.Spectator : (CsTeam)cur.Team;
        foreach (var h in Humans())
            if (h.Team != team) h.ChangeTeam(team);
    }

    HookResult OnRoundStart(EventRoundStart e, GameEventInfo i)
    {
        if (!awaitRestart || cur == null) return HookResult.Continue;
        awaitRestart = false;
        var g = generation;
        AddTimer(0.3f, () => { if (g == generation) Place(); });
        return HookResult.Continue;
    }

    static void Loadout(CCSPlayerController c, Track t)
    {
        var pawn = c.PlayerPawn.Value;
        if (pawn == null) return;
        c.RemoveWeapons();
        // bots get no grenades: the demo's are thrown again by the plugin, their own AI would throw others
        var nade = (string w) => c.IsBot && (w.Contains("grenade") || w.Contains("flashbang") || w.Contains("molotov") || w.Contains("decoy"));
        foreach (var w in t.Weapons.Where(w => w != t.Active && !nade(w))) c.GiveNamedItem(w);
        if (!string.IsNullOrEmpty(t.Active) && !nade(t.Active)) c.GiveNamedItem(t.Active);
        pawn.Health = Math.Max(1, t.Hp);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
        pawn.ArmorValue = t.Armor;
        Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_ArmorValue");
        if (pawn.ItemServices != null) new CCSPlayer_ItemServices(pawn.ItemServices.Handle).HasHelmet = t.Helmet;
        if (c.InGameMoneyServices != null) { c.InGameMoneyServices.Account = 0; Utilities.SetStateChanged(c, "CCSPlayerController", "m_pInGameMoneyServices"); }
        if (!string.IsNullOrEmpty(t.Active)) c.ExecuteClientCommandFromServer($"use {t.Active}");
    }

    static void Freeze(CCSPlayerPawn pawn, bool on)
    {
        pawn.MoveType = on ? MoveType_t.MOVETYPE_OBSOLETE : MoveType_t.MOVETYPE_WALK;
        Schema.SetSchemaValue(pawn.Handle, "CBaseEntity", "m_nActualMoveType", on ? 1 : 2);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_MoveType");
    }

    static Vector3 Pos(Track t, int i) => new(t.Path[i * 5], t.Path[i * 5 + 1], t.Path[i * 5 + 2]);
    static Vector3 Ang(Track t, int i) => new(t.Path[i * 5 + 4], t.Path[i * 5 + 3], 0);

    // everyone on the first frame, loadouts of the demo, 3 s to look around, then it plays
    void Place()
    {
        if (cur == null) return;
        foreach (var (slot, t) in bots)
        {
            var c = Utilities.GetPlayerFromSlot(slot);
            if (c == null || !c.IsValid) continue;
            if (!c.PawnIsAlive) c.Respawn();
            Loadout(c, t);
            c.PlayerPawn.Value?.Teleport(Pos(t, 0), Ang(t, 0), Vector3.Zero);
        }
        var me = cur.Players.FirstOrDefault(t => t.Me);
        if (mode == "actor" && me != null)
            foreach (var h in Humans())
            {
                if ((int)h.Team != me.Team) continue;
                if (!h.PawnIsAlive) h.Respawn();
                Loadout(h, me);
                var pawn = h.PlayerPawn.Value;
                if (pawn == null) continue;
                pawn.Teleport(Pos(me, 0), Ang(me, 0), Vector3.Zero);
                Freeze(pawn, true);
            }
        kills = dmg = 0; devSum = 0; devN = 0;
        SessionPlaced();
        phase = "countdown";
        countdownEnd = Server.TickCount + 3 * 64;
        var g = generation;
        for (int s = 3; s >= 1; s--)
        {
            var n = s;
            AddTimer(3 - n, () => { if (g == generation && !SessionCount(n)) foreach (var h in Humans()) h.PrintToCenter($"{cur?.Title}   {n}"); });
        }
    }

    void Go()
    {
        phase = "live";
        t0 = Server.TickCount;
        nextNade = 0;
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
        var now = Server.TickCount;
        if (now - lastBeat >= 64 || now < lastBeat) { lastBeat = now; Beat(); }   // the tick count starts over with each map
        if (cur == null || (phase != "countdown" && phase != "live")) return;
        if (phase == "countdown" && now >= countdownEnd) Go();
        var f = phase == "live" ? (now - t0) / (float)cur.Step : 0f;
        var mePawn = Humans().Select(h => h.PlayerPawn.Value).FirstOrDefault(p => p != null && p.IsValid && p.LifeState == (byte)LifeState_t.LIFE_ALIVE);
        uint[]? seen = null;
        if (mePawn != null && mode == "actor") { var m = mePawn.EntitySpottedState.SpottedByMask; seen = new[] { m[0], m[1] }; }
        var meSid = cur.Players.FirstOrDefault(t => t.Me)?.Sid ?? "";
        int maxFrames = 0;
        foreach (var (slot, t) in bots)
        {
            maxFrames = Math.Max(maxFrames, t.Frames);
            if (free.Contains(slot) || gone.Contains(t.Sid)) continue;
            var c = Utilities.GetPlayerFromSlot(slot);
            var pawn = c?.PlayerPawn.Value;
            if (c == null || pawn == null || !c.PawnIsAlive) { gone.Add(t.Sid); Logger.LogInformation("gone {n} at {f}", t.Name, (int)f); continue; }
            if (t.Hold) { pawn.Teleport(Pos(t, 0), null, Vector3.Zero); continue; }   // an aim target: its spot, its own aim
            var i = (int)f;
            if (i >= t.Frames - 1)
            {
                // the end of its recorded path: a death in the demo (by a player still alive here, or the world), or the
                // window is over / you were the killer: the bot plays on from there
                if (t.Death >= 0 && t.Killer != meSid && (t.Killer == "" || !cur.Players.Any(q => q.Sid == t.Killer) || Alive(t.Killer)))
                { pawn.CommitSuicide(false, true); gone.Add(t.Sid); Logger.LogInformation("demo kill {n} at {f}", t.Name, (int)f); }
                else { free.Add(slot); Logger.LogInformation("free {n} at {f} (death {d}, killer {k})", t.Name, (int)f, t.Death, t.Killer); }
                continue;
            }
            var a = f - i;
            var p0 = Pos(t, i); var p1 = Pos(t, i + 1);
            var pos = Vector3.Lerp(p0, p1, a);
            if (phase == "live" && mode == "spec" && pawn.AbsOrigin != null)
            { var o = pawn.AbsOrigin; devSum += Vector3.Distance(new Vector3(o.X, o.Y, o.Z), pos); devN++; }
            var y0 = t.Path[i * 5 + 3]; var dy = ((t.Path[i * 5 + 8] - y0 + 540f) % 360f) - 180f;
            Vector3? ang = new Vector3(t.Path[i * 5 + 4] + (t.Path[i * 5 + 9] - t.Path[i * 5 + 4]) * a, y0 + dy * a, 0);
            if (seen != null && (seen[slot / 32] & (1u << (slot % 32))) != 0) ang = null;   // it sees you: its own aim
            var vel = phase == "live" ? (p1 - p0) * (cur.Rate / (float)cur.Step) : Vector3.Zero;
            pawn.Teleport(pos, ang, vel);
        }
        if (phase != "live") return;
        SessionTick();
        if (cur == null || phase != "live" || cur.Kind is "aim" or "nade") return;   // their end is the session's
        while (nextNade < cur.Nades.Count && cur.Nades[nextNade].F <= f) Throw(cur.Nades[nextNade++]);
        if (mode == "spec" && devN > 0 && (now - t0) % 320 == 0)
            Logger.LogInformation($"drift {devSum / devN:F1} u over {devN} samples");
        var foes = bots.Where(b => b.Value.Team != cur.Team).ToList();
        if (mode == "actor" && foes.Count > 0 && foes.All(b => gone.Contains(b.Value.Sid))) { Finish("won"); return; }
        var endF = cur.Kind == "clutch" ? maxFrames + 64 * 10 / cur.Step : maxFrames + 64 * 2 / cur.Step;
        if (f >= endF) Finish(mode == "spec" ? "watched" : "survived");
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
        SessionDeath(e, v);
        if (mode == "actor" && v is { IsValid: true, IsBot: false }) AddTimer(0.1f, () => Finish("dead"));
        return HookResult.Continue;
    }

    HookResult OnHurt(EventPlayerHurt e, GameEventInfo i)
    {
        if (phase == "live" && e.Attacker is { IsValid: true, IsBot: false } && e.Userid is { IsBot: true }) dmg += e.DmgHealth;
        return HookResult.Continue;
    }

    // bots never hurt each other: only the demo (a recorded death) or you kill a bot
    HookResult OnTakeDamage(CEntityInstance victim, CTakeDamageInfo info)
    {
        if (cur == null) return HookResult.Continue;
        try
        {
            var att = info.Attacker.Value;
            if (victim.DesignerName != "player" || att == null || att.DesignerName != "player") return HookResult.Continue;
            var vc = new CCSPlayerPawn(victim.Handle).OriginalController.Value;
            var ac = new CCSPlayerPawn(att.Handle).OriginalController.Value;
            if (vc is { IsBot: true } && ac is { IsBot: true } && vc.Slot != ac.Slot) return HookResult.Handled;   // a demo death is the bot on itself
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
        var line = JsonSerializer.Serialize(new Dictionary<string, object> {
            ["id"] = cur.Id, ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["outcome"] = outcome, ["mode"] = mode,
            ["kills"] = kills, ["dmg"] = dmg, ["alive_s"] = Math.Round(alive, 1), ["difficulty"] = difficulty,
            ["drift"] = devN > 0 ? Math.Round(devSum / devN, 1) : -1 });
        try { File.AppendAllText(System.IO.Path.Combine(Dir, "results.jsonl"), line + "\n"); } catch (Exception e) { Logger.LogInformation($"{e.Message}"); }
        var msg = outcome switch { "won" => "\x04WON\x01", "survived" => "\x04SURVIVED\x01", "dead" => "\x02DEAD\x01", _ => outcome };
        All($"{msg} · {kills} kill(s) · {dmg} dmg · {alive:F1} s — again in 3 s (!n next · !p previous · !spec · !stop)");
        var g = generation;
        AddTimer(3f, () => { if (g == generation && phase == "done" && cur != null) Setup(); });
    }

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
