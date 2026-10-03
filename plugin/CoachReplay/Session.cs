// The training session: one Play in the app, then everything follows on its own, block after block (aim on the map,
// stuff, situations), in the time chosen. The screen says what to do; each drill scores points, a streak multiplies
// them, a miss is tried once more right away (repetition), and each drill is written to coach/results.jsonl for the app
// (Leitner boxes: what you missed comes back next session).
//
// Commands during a session: !n skips the drill, !stop ends the session.
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
    [JsonPropertyName("click")] public string Click { get; set; } = "";
    [JsonPropertyName("target")] public float[]? Target { get; set; }
    [JsonPropertyName("level")] public int Level { get; set; }
    [JsonPropertyName("scenario")] public string? Scenario { get; set; }
    [JsonPropertyName("mode")] public string Mode { get; set; } = "";   // aim: prefire, defend, or "" (your duel spots)
    [JsonPropertyName("seconds")] public int Seconds { get; set; } = 75;
    [JsonPropertyName("alive")] public int Alive { get; set; } = 3;
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
    // stuff: three throws
    int attempts;
    bool nadeWait;
    DateTime attemptEnd;
    static readonly Random Rng = new();
    string introHtml = "";
    static readonly Dictionary<string, string> KindName = new() { ["aim"] = "AIM", ["nade"] = "STUFF", ["situation"] = "SITUATION" };
    static readonly Dictionary<string, string> KindColor = new() { ["aim"] = "#ff8a3d", ["nade"] = "#5ab4ff", ["situation"] = "#e0a030" };

    void RegisterSession()
    {
        AddCommand("css_session", "start a training session: css_session <id>", (p, c) => CmdSession(p, c));
        RegisterEventHandler<EventSmokegrenadeDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventFlashbangDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventHegrenadeDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventMolotovDetonate>((e, _) => { NadeHit(e.Userid, e.X, e.Y); return HookResult.Continue; });
        RegisterEventHandler<EventBombPlanted>((e, _) => { BombPlanted(); return HookResult.Continue; });
    }

    static string MapName(string m) { var n = m.Replace("de_", "").Replace("cs_", ""); return n.Length > 0 ? char.ToUpper(n[0]) + n[1..] : m; }

    void Html(string html, int secs = 3) { foreach (var h in Humans()) h.PrintToCenterHtml(html, secs); }

    void CmdSession(CCSPlayerController? p, CommandInfo c)
    {
        var f = System.IO.Path.Combine(Dir, "sessions", c.GetArg(1) + ".json");
        if (!File.Exists(f)) { Say(p, $"no session {c.GetArg(1)}"); return; }
        try { sess = JsonSerializer.Deserialize<Session>(File.ReadAllText(f)); } catch (Exception e) { Say(p, e.Message); return; }
        if (sess == null || sess.Blocks.Count == 0) { sess = null; return; }
        difficulty = Math.Clamp(sess.Difficulty, 0, 3);
        mode = "actor";
        blockIdx = -1; points = streak = okN = doneN = drillNo = 0; drill = null; queue.Clear(); cur = null;
        Logger.LogInformation("session {id}: {n} blocks", sess.Id, sess.Blocks.Count);
        if (!Humans().Any()) { phase = "waiting"; return; }   // starts when you join
        Welcome();
        AddTimer(4f, NextBlock);
    }

    void Welcome()
    {
        if (sess == null) return;
        var order = string.Join(" → ", sess.Blocks.Select(b => KindName[b.Kind]).Distinct());
        Html($"<font color='#e0a030'>TRAINING · {sess.Minutes} MIN</font><br><font class='fontSize-l'>{string.Join(" · ", sess.Maps.Select(MapName))}</font><br>{order}", 4);
        All($"Training {sess.Minutes} min · {string.Join(", ", sess.Maps.Select(MapName))} · {order}. !n skips a drill, !stop ends.");
    }

    // after a map change, or when you join the server
    void SessionResume()
    {
        if (sess == null || !Humans().Any()) return;
        if (blockIdx < 0) { Welcome(); AddTimer(4f, NextBlock); return; }
        var b = sess.Blocks[blockIdx];
        if (Server.MapName != b.Map) { Server.ExecuteCommand($"changelevel {b.Map}"); return; }
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
            Html($"<font color='#e0a030'>NEXT MAP</font><br><font class='fontSize-l'>{MapName(b.Map)}</font>", 4);
            AddTimer(2f, () => Server.ExecuteCommand($"changelevel {b.Map}"));
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
        var s = d.Kind switch { "situation" => d.Scenario != null ? Peek(d.Scenario) : null, "aim" => AimScenario(d), "nade" => NadeScenario(d), _ => null };
        if (s == null && d.Kind == "situation" && waitFile++ < 20)   // the app is still building it from the demo
        {
            Html($"<font color='#e0a030'>SITUATION</font><br>loading {d.Title}…", 2);
            var g = sessGen;
            AddTimer(2f, () => { if (g == sessGen && drill == d) RunDrill(d); });
            return;
        }
        waitFile = 0;
        if (s == null) { Logger.LogInformation("drill {id}: nothing to play", d.Id); NextDrill(); return; }
        cur = s;
        mode = "actor";
        aimOrder.Clear(); reacts.Clear(); aimHs = 0; aimNext = 0; attempts = 0; nadeWait = false; frags = deaths = plants = 0;
        Intro(d);
        Setup();
    }

    string Left() { var l = blockEnd - DateTime.UtcNow; return l.TotalSeconds > 0 ? $"{(int)l.TotalMinutes}:{l.Seconds:D2}" : "last"; }

    void Intro(Drill d)
    {
        var how = d.Kind == "situation" && cur != null ? SituationText() : d.Kind != "nade" ? d.Tip : d.Level switch
        {
            0 => $"{d.How} · {d.Click} — your aim is set: just throw",
            1 => $"{d.How} · {d.Click} — find the aim",
            _ => "find the aim and the throw",
        };
        var again = tries > 0 ? " · AGAIN" : "";
        introHtml = $"<font color='{KindColor[d.Kind]}'>{KindName[d.Kind]}{again}</font> · {Left()} · ⭐ {points}<br><font class='fontSize-l'>{d.Title}</font><br>{how}";
        Html(introHtml, 5);
        All($"\x10{KindName[d.Kind]}{again}\x01 {d.Title} — {how}");
    }

    Scenario AimScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "aim", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Armor = 100, Helmet = true, Weapons = d.Weapons,
            Active = d.Weapons.LastOrDefault(), Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], me.Ang[1], me.Ang[0] } });
        if (d.Mode == "defend")   // a few attackers at a time, played by the game's AI (they carry the bomb: they come to the site)
        {
            for (int k = 0; k < Math.Min(d.Alive, d.Bots.Count); k++)
            {
                var b = d.Bots[Rng.Next(d.Bots.Count)];
                s.Players.Add(new Track { Sid = $"att{k}", Name = b.Zone ?? $"Attacker {k + 1}", Team = 5 - d.Team, Hp = 100, Armor = 100, Helmet = true,
                    Weapons = d.BotWeapons, Active = d.BotWeapons.FirstOrDefault(w => w.Contains("ak47") || w.Contains("m4")) ?? d.BotWeapons.LastOrDefault(),
                    Path = new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] } });
            }
            return s;
        }
        for (int k = 0; k < d.Bots.Count; k++)
        {
            var b = d.Bots[k];
            s.Players.Add(new Track { Sid = $"target{k}", Name = b.Zone ?? $"Target {k + 1}", Team = 5 - d.Team, Hp = 100, Armor = 100, Helmet = true,
                Weapons = d.BotWeapons, Active = d.BotWeapons.LastOrDefault(), Path = new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] }, Hold = true });
        }
        return s;
    }

    // a situation: what to do, your route in the match, who got you and from where
    string SituationText()
    {
        var me = cur?.Players.FirstOrDefault(p => p.Me);
        var route = me == null ? "" : string.Join(" → ", me.Places.Select(p => p[1].GetString()).Where(x => !string.IsNullOrEmpty(x)));
        var lines = new List<string> { $"goal: {(string.IsNullOrEmpty(cur?.Goal) ? "survive" : cur!.Goal)}" };
        if (route != "") lines.Add($"your route: {route}");
        if (!string.IsNullOrEmpty(cur?.Danger)) lines.Add($"⚠ {cur!.Danger}");
        return string.Join("<br>", lines);
    }

    Scenario NadeScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "nade", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        float pitch = me.Ang[0], yaw = me.Ang[1];
        if (d.Level >= 1) { yaw += (float)(Rng.NextDouble() * 120 - 60); pitch = 0; }   // the spot, not the aim
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Weapons = new() { "weapon_knife", d.Item },
            Active = d.Item, Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], yaw, pitch } });
        return s;
    }

    // Place() is done: the aim targets but the first wait (dead) for their turn
    void SessionPlaced()
    {
        if (sess == null || cur == null) return;
        if (cur.Kind == "aim" && drill?.Mode is "prefire" or "defend")
        {
            aimOrder.Clear();
            aimOrder.AddRange(bots.Keys);
            peekAt.Clear();
            if (drill.Mode == "prefire")   // the ones that peek later wait, hidden, for their timing
                foreach (var (slot, t) in bots)
                {
                    var k = int.TryParse(t.Sid.Replace("target", ""), out var i) ? i : -1;
                    var at = k >= 0 && k < drill.Bots.Count ? drill.Bots[k].At : 0f;
                    if (at > 0.3f) { peekAt[slot] = at; Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.CommitSuicide(false, true); }
                }
        }
        else if (cur.Kind == "aim")
        {
            aimOrder.Clear();
            aimOrder.AddRange(bots.Keys.OrderBy(_ => Rng.Next()));
            for (int k = 1; k < aimOrder.Count; k++) Utilities.GetPlayerFromSlot(aimOrder[k])?.PlayerPawn.Value?.CommitSuicide(false, true);
            aimNext = 1;
            // you start turned to the first target
            if (aimOrder.Count > 0 && bots.TryGetValue(aimOrder[0], out var first))
            {
                var me = cur.Players.First(p => p.Me);
                var d = Pos(first, 0) - Pos(me, 0);
                var yaw = MathF.Atan2(d.Y, d.X) * 180 / MathF.PI;
                var pitch = -MathF.Atan2(d.Z, MathF.Sqrt(d.X * d.X + d.Y * d.Y)) * 180 / MathF.PI;
                foreach (var h in Humans()) h.PlayerPawn.Value?.Teleport(Pos(me, 0), new Vector3(pitch, yaw, 0), Vector3.Zero);
            }
        }
        if (cur.Kind == "nade") { nadeWait = true; attemptEnd = DateTime.UtcNow.AddSeconds(30); }   // a throw during the countdown counts
    }

    // the countdown of a drill keeps its card on screen; false: not in a session
    bool SessionCount(int n)
    {
        if (sess == null || drill == null) return false;
        Html($"{introHtml}<br><font class='fontSize-xl'>{n}</font>", 1);
        return true;
    }

    void SessionGo()
    {
        if (sess == null || cur == null) return;
        aimSpawn = Server.TickCount;
        lastHud = Server.TickCount;
        if (cur.Kind == "aim" && string.IsNullOrEmpty(drill?.Mode)) AimCard();
        if (drill?.Mode == "prefire") Html($"<font color='#ff8a3d'>GO</font> · clear {aimOrder.Count} · {drill.Seconds} s", 2);
        if (drill?.Mode == "defend") Html($"<font color='#ff8a3d'>HOLD</font> · {drill.Seconds} s · they are coming", 2);
    }

    void SessionTick()
    {
        if (sess == null || cur == null || phase != "live") return;
        var el = (Server.TickCount - t0) / 64f;
        if (drill?.Mode is "prefire" or "defend")
        {
            if (el >= drill.Seconds) { Finish(drill.Mode == "prefire" ? "timeout" : "done"); return; }
            foreach (var slot in peekAt.Where(kv => kv.Value <= el).Select(kv => kv.Key).ToList())
            {   // its timing: it peeks
                peekAt.Remove(slot);
                if (!bots.TryGetValue(slot, out var t)) continue;
                var c = Utilities.GetPlayerFromSlot(slot);
                if (c == null || !c.IsValid) continue;
                c.Respawn();
                Loadout(c, t);
                c.PlayerPawn.Value?.Teleport(Pos(t, 0), Ang(t, 0), Vector3.Zero);
                gone.Remove(t.Sid);
            }
            if (Server.TickCount - lastHud >= 3 * 64)
            {
                lastHud = Server.TickCount;
                var left = (int)(drill.Seconds - el);
                Html(drill.Mode == "prefire"
                    ? $"<font color='#ff8a3d'>PREFIRE</font> · {aimOrder.Count - frags} left · {left} s"
                    : $"<font color='#ff8a3d'>DEFEND</font> · {left} s · ⚔ {frags} · ☠ {deaths}", 2);
            }
            return;
        }
        if (cur.Kind is "death" or "clutch" && Server.TickCount - lastHud >= 3 * 64)   // the next place of your route in the match
        {
            lastHud = Server.TickCount;
            var me = cur.Players.FirstOrDefault(p => p.Me);
            var fr = (Server.TickCount - t0) / (float)cur.Step;
            var next = me?.Places.Select(p => (at: p[0].GetInt32(), nm: p[1].GetString())).Where(p => p.at > fr + 8).Select(p => p.nm).FirstOrDefault();
            if (next != null) Html($"<font color='#e0a030'>→ {next}</font> <font class='fontSize-s'>(your route in the match)</font>", 2);
        }
        // a target not found in 12 s goes away (missed), the next one comes
        if (cur.Kind == "aim" && aimSpawn > 0 && Server.TickCount - aimSpawn > 12 * 64)
        {
            aimSpawn = 0;
            var slot = aimOrder.ElementAtOrDefault(aimNext - 1);
            Html("<font color='#ff5a5a'>MISSED</font> · next one", 1);
            Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.CommitSuicide(false, true);
        }
        if (cur.Kind == "aim" && Server.TickCount - t0 > 120 * 64) Finish("timeout");
        if (cur.Kind == "nade" && nadeWait && DateTime.UtcNow > attemptEnd) NadeResult(double.NaN);
    }

    // true: handled here (a defense: you come back instead of the drill ending)
    bool SessionDeath(EventPlayerDeath e, CCSPlayerController? v)
    {
        if (sess == null || cur?.Kind != "aim" || drill == null || v == null) return false;
        if (drill.Mode == "prefire")
        {
            if (!v.IsBot) return false;
            if (e.Attacker is { IsValid: true, IsBot: false }) { frags++; if (e.Headshot) aimHs++; }
            if (peekAt.ContainsKey(v.Slot)) return false;   // a hidden one going to wait for its timing
            var left = bots.Count(b => !gone.Contains(b.Value.Sid) && b.Key != v.Slot) + peekAt.Count;
            if (left == 0) AddTimer(0.3f, () => Finish("cleared"));
            else Html($"<font color='#ff8a3d'>{left} left</font>{(e.Headshot ? " · HS" : "")}", 1);
            return false;
        }
        if (drill.Mode == "defend")
        {
            var g = generation;
            if (!v.IsBot)   // you: back on the spot in 1.5 s
            {
                deaths++;
                AddTimer(1.5f, () =>
                {
                    if (g != generation || phase != "live" || cur == null) return;
                    var me = cur.Players.First(p => p.Me);
                    foreach (var h in Humans()) { h.Respawn(); Loadout(h, me); h.PlayerPawn.Value?.Teleport(Pos(me, 0), Ang(me, 0), Vector3.Zero); }
                });
                return true;
            }
            if (e.Attacker is { IsValid: true, IsBot: false }) { frags++; if (e.Headshot) aimHs++; }
            var slot = v.Slot;
            AddTimer(1f + (float)Rng.NextDouble() * 1.5f, () =>   // another one comes, from a real entrance not right next to you
            {
                if (g != generation || phase != "live" || cur == null || drill == null || !bots.TryGetValue(slot, out var t)) return;
                var c = Utilities.GetPlayerFromSlot(slot);
                if (c == null || !c.IsValid) return;
                var me = Pos(cur.Players.First(p => p.Me), 0);
                var far = drill.Bots.Where(b => Vector3.Distance(new Vector3(b.Pos[0], b.Pos[1], b.Pos[2]), me) > 600).ToList();
                if (far.Count == 0) far = drill.Bots;
                var sp = far[Rng.Next(far.Count)];
                c.Respawn();
                Loadout(c, t);
                c.PlayerPawn.Value?.Teleport(new Vector3(sp.Pos[0], sp.Pos[1], sp.Pos[2]), new Vector3(sp.Ang[0], sp.Ang[1], 0), Vector3.Zero);
                if (sp.Zone != null) { c.PlayerName = sp.Zone; Utilities.SetStateChanged(c, "CBasePlayerController", "m_iszPlayerName"); }
                gone.Remove(t.Sid);
            });
            return false;
        }
        if (!v.IsBot) return false;
        if (e.Attacker is { IsValid: true, IsBot: false } && aimSpawn > 0)
        {
            reacts.Add((Server.TickCount - aimSpawn) / 64.0);
            if (e.Headshot) aimHs++;
            Html($"<font color='#ff8a3d'>HIT</font> {reacts[^1]:F2} s{(e.Headshot ? " · HS" : "")} · {reacts.Count}/{aimOrder.Count}", 1);
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
                c.PlayerPawn.Value?.Teleport(Pos(t, 0), Ang(t, 0), Vector3.Zero);
                gone.Remove(t.Sid);
                aimSpawn = Server.TickCount;
                AimCard();
            });
        }
        else AddTimer(0.4f, () => Finish(reacts.Count == aimOrder.Count ? "cleared" : "done"));
        return false;
    }

    // a defense: a bomb planted is taken away (and costs points)
    void BombPlanted()
    {
        if (sess == null || drill?.Mode != "defend" || phase != "live") return;
        plants++;
        Html("<font color='#ff5a5a'>PLANTED</font> · −60", 2);
        AddTimer(0.2f, () => { foreach (var c4 in Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4")) c4.Remove(); });
    }

    // which target, where to look
    void AimCard()
    {
        var slot = aimOrder.ElementAtOrDefault(aimNext - 1);
        var where = bots.TryGetValue(slot, out var t) ? t.Name : "";
        Html($"<font color='#ff8a3d'>TARGET {aimNext}/{aimOrder.Count}</font> → <font class='fontSize-l'>{where}</font>", 2);
    }

    void NadeHit(CCSPlayerController? u, float x, float y)
    {
        if (sess == null || drill == null || cur?.Kind != "nade" || phase is not ("live" or "countdown") || !nadeWait || u == null || !u.IsValid || u.IsBot) return;
        var tg = drill.Target;
        if (tg == null || tg.Length < 2) return;
        NadeResult(Math.Sqrt((x - tg[0]) * (x - tg[0]) + (y - tg[1]) * (y - tg[1])));
    }

    // a throw landed (dist from the spot of the pros' throws) or 25 s without one (NaN)
    void NadeResult(double dist)
    {
        if (drill == null) return;
        attempts++;
        var air = drill.Type is "flash" or "he";
        var q = double.IsNaN(dist) ? "NO THROW" : dist <= (air ? 120 : 80) ? "PERFECT" : dist <= (air ? 260 : 180) ? "GOOD" : "MISS";
        var away = double.IsNaN(dist) ? "" : $"{dist:F0} u from the spot";
        if (q is "PERFECT" or "GOOD")
        {
            nadeWait = false;
            var pts = (int)((q == "PERFECT" ? 150 : 100) * (attempts == 1 ? 1 : attempts == 2 ? 0.6 : 0.35) * (1 + 0.25 * drill.Level));
            DrillDone(true, q.ToLower(), pts, $"{away} · throw {attempts}");
            return;
        }
        if (attempts >= 3) { nadeWait = false; DrillDone(false, "miss", 0, away); return; }
        // once more: back on the spot with a new grenade; after two misses the aim is shown
        var show = attempts >= 2 && drill.Level >= 1;
        Html($"<font color='#ff5a5a'>{q}</font> {away}<br>throw {attempts + 1}/3{(show ? " · here is the aim" : "")}", 2);
        nadeWait = false;
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
                h.PlayerPawn.Value?.Teleport(new Vector3(me.Pos[0], me.Pos[1], me.Pos[2]), ang, Vector3.Zero);
            }
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
        if (cur.Kind == "aim" && drill?.Mode == "prefire")
        {
            ok = outcome == "cleared";
            var el = (Server.TickCount - t0) / 64.0;
            pts = frags * 30 + aimHs * 15 + (ok ? 100 + (int)Math.Max(0, (drill.Seconds - el) * 4) : 0);
            detail = $"{frags}/{aimOrder.Count}{(ok ? $" in {el:F1} s" : "")} · {aimHs} HS";
        }
        else if (cur.Kind == "aim" && drill?.Mode == "defend")
        {
            ok = frags >= 6 && frags >= 2 * deaths;
            pts = Math.Max(0, frags * 40 + aimHs * 15 - deaths * 50 - plants * 60);
            detail = $"{frags} frags · {deaths} death(s) · {aimHs} HS{(plants > 0 ? $" · {plants} planted" : "")}";
        }
        else if (cur.Kind == "aim")
        {
            var n = Math.Max(1, aimOrder.Count);
            ok = outcome != "dead" && (reacts.Count == n || (n >= 3 && reacts.Count >= n - 1));
            foreach (var r in reacts) pts += 50 + (int)Math.Max(0, 50 * (1.2 - r) / 1.2);
            pts += aimHs * 20 + (ok ? 100 : 0);
            detail = reacts.Count > 0 ? $"{reacts.Count}/{aimOrder.Count} · {reacts.Average():F2} s avg · {aimHs} HS" : "no kill";
        }
        else
        {
            ok = outcome is "won" or "survived";
            pts = (outcome == "won" ? 300 : outcome == "survived" ? 200 : 0) + 25 * kills;
            detail = $"{kills} kill(s) · {dmg} dmg · {alive:F1} s";
        }
        DrillDone(ok, outcome, pts, detail);
    }

    void DrillDone(bool ok, string outcome, int pts, string detail)
    {
        if (sess == null || drill == null) return;
        phase = "done";
        if (ok) { streak++; okN++; } else streak = 0;
        var mult = ok ? 1 + 0.1 * Math.Min(5, streak - 1) : 1.0;
        pts = (int)Math.Round(pts * mult);
        points += pts;
        doneN++;
        Write(new Dictionary<string, object> { ["session"] = sess.Id, ["drill"] = drill.Id, ["kind"] = drill.Kind, ["map"] = drill.Map, ["ok"] = ok,
            ["outcome"] = outcome, ["points"] = pts, ["detail"] = detail, ["try"] = tries + 1, ["level"] = drill.Level, ["t"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds() });
        var st = streak >= 2 ? $" · 🔥 x{mult:F1}" : "";
        Html(ok ? $"<font color='#5ad15a'>✔ {outcome.ToUpper()}</font> +{pts}{st}<br>{detail}<br>⭐ {points}"
                : $"<font color='#ff5a5a'>✘ {outcome.ToUpper()}</font><br>{detail}<br>⭐ {points}", 3);
        All($"{(ok ? "\x04✔" : "\x02✘")} {drill.Title}\x01 · {outcome} · {detail} · +{pts} (total {points}){st}");
        tries++;
        var again = !ok && outcome != "skipped" && tries < 2 && DateTime.UtcNow < blockEnd;   // a miss: once more right away
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
        Html($"<font color='#e0a030'>🏁 SESSION DONE</font><br><font class='fontSize-l'>{points} pts</font><br>{okN}/{doneN} drills ✔", 8);
        All($"Session done: {points} pts · {okN}/{doneN} drills ✔ — your progress is in the app.");
        sess = null; drill = null; cur = null; phase = "idle"; bots.Clear(); builtFor = null; sessGen++;
        Server.ExecuteCommand("bot_kick");
    }

    void Write(Dictionary<string, object> o)
    {
        try { File.AppendAllText(System.IO.Path.Combine(Dir, "results.jsonl"), JsonSerializer.Serialize(o) + "\n"); }
        catch (Exception e) { Logger.LogInformation("{m}", e.Message); }
    }

    Dictionary<string, object?> SessionBeat() => sess == null ? new() : new()
    {
        ["session"] = sess.Id, ["block"] = blockIdx >= 0 && blockIdx < sess.Blocks.Count ? sess.Blocks[blockIdx].Kind : null,
        ["drill"] = drill?.Title, ["points"] = points, ["ok"] = okN, ["done"] = doneN, ["streak"] = streak,
        ["left"] = blockEnd > DateTime.UtcNow ? (int)(blockEnd - DateTime.UtcNow).TotalSeconds : 0,
    };
}
