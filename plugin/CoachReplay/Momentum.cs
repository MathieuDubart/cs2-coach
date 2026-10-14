// Momentum (14/10, rework_entrainement.md section 9; the user: "Momentum: a dedicated movement training mode built to
// improve your map mobility, pathing, and jump precision using real map assets"): moving on the real maps, from the
// base's real rounds (momentum.py builds the drills). No bot: you, the map, and what is measured. A drill is a series of
// reps, each one from its start, still:
// - route: a real way against the clock (a spawn to a site, a CT rotation), knife out. Its checkpoints in order (rings
//   on the ground, the gold line until you ran it once); at each one your time against the base's pace, at the end
//   against the base's runs of that way, its fastest ones and the pros'. A checkpoint missed: off the way, that run
//   counts for nothing. Three runs;
// - jump: a jump the base's players make onto something: from the green ring, land in the blue one, on top. A jump far
//   from the green ring is no try; a landing below says why (short, or not crouched in the air where the base's jumpers
//   crouch). Three landings, five tries at most;
// - stop: counter-strafing: run left and right at full speed, STOP comes on the screen. Measured: the time from your
//   speed's drop to an accurate stop (34 % of your top speed: Leetify's moving shot), and whether you then went the
//   other way (the other key held too long). Eight stops;
// - silent: the last stretch of a real way into a site, walked in the time given: each footstep and each jump heard.
using System.Globalization;
using System.Numerics;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace CoachReplay;

public partial class CoachReplay
{
    bool MoOn => drill is { Mode: "momentum" };
    const float CpR = 120f, EndR = 140f;   // how near a checkpoint and a way's end count (momentum.py: CP_R, END_R)
    const float StopShare = 0.34f;   // an accurate stop: under 34 % of your top speed
    const double BrakeOk = 0.12;   // s from the drop to the stop: a counter-strafe (about 0.08), a key let go (about 0.2)
    int moRep, moRepAt, moNext, moMissed, moSteps, moHops;
    string moStage = "";   // ready, run, jump, air, strafe, brake, over, after, dead
    readonly List<(bool valid, double time, int missed)> moRuns = new();
    readonly List<(bool ok, double time, int steps, int hops, int missed)> moWalks = new();
    readonly List<(bool ok, string why, float off, bool duck)> moJumps = new();
    readonly List<(double react, double brake, bool over, string why)> moStops = new();
    int moAirAt;   // a jump: when it left the ground
    bool moAirDuck, moHinted;   // crouched in the air; the jump's reminder said
    // a stop: at full speed since, the STOP due at, said at, the speed's drop, the stop; the top speed and the way then
    int moFastSince = -1, moStopDue = -1, moStopAt = -1, moDropAt = -1, moStillAt = -1;
    float moTop;
    Vector2 moWay;

    void RegisterMomentum()
    {
        RegisterEventHandler<EventPlayerJump>((e, _) => { MoJump(e.Userid); return HookResult.Continue; });
        RegisterEventHandler<EventPlayerFootstep>((e, _) => { MoStep(e.Userid); return HookResult.Continue; });
    }

    static string Sec(double s, int d = 2) => s.ToString(d == 1 ? "F1" : "F2", CultureInfo.InvariantCulture);
    static float Flat(Vector3 a, float[] b) => new Vector2(a.X - b[0], a.Y - b[1]).Length();

    Scenario MomentumScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "momentum", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Armor = d.Armor, Helmet = d.Helmet, Weapons = d.Weapons,
            Active = d.Weapons.LastOrDefault(), Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], me.Ang[1], me.Ang[0] } });
        // the doors and the vents on the way open, as they were for the base's players (a point every 48 u of its line)
        for (int i = 0; i + 1 < d.Line.Count; i++)
        {
            var a = new Vector3(d.Line[i][0], d.Line[i][1], d.Line[i][2]);
            var b = new Vector3(d.Line[i + 1][0], d.Line[i + 1][1], d.Line[i + 1][2]);
            var n = Math.Max(1, (int)(Vector3.Distance(a, b) / 48));
            for (int k = 0; k < n; k++) { var p = Vector3.Lerp(a, b, k / (float)n); s.Trail.Add(new[] { p.X, p.Y, p.Z }); }
        }
        if (d.From is { Length: >= 3 } f) s.Trail.Add(f);
        if (d.Target is { Length: >= 3 } tg) s.Trail.Add(tg);
        return s;
    }

    // Place() is done: the counters from zero, the marks on the ground
    void MoPlaced()
    {
        moRep = 0; moStage = "";
        moRuns.Clear(); moWalks.Clear(); moJumps.Clear(); moStops.Clear(); drillExtra.Clear();
        if (drill == null) return;
        ClearLine();
        var teal = System.Drawing.Color.FromArgb(255, 86, 212, 200);
        var blue = System.Drawing.Color.FromArgb(255, 90, 180, 255);
        var green = System.Drawing.Color.FromArgb(255, 90, 230, 90);
        if (drill.Variant is "route" or "silent")
        {   // the gold line until you ran it once (the training's boxes: level 1), the checkpoints, the end
            if (drill.Line.Count > 1 && (drill.Variant == "silent" || drill.Level == 0)) DrawLine(drill.Line);
            for (int k = 0; k < drill.Marks.Count; k++)
            {
                var m = drill.Marks[k];
                var last = k == drill.Marks.Count - 1;
                Ring(new Vector3(m[0], m[1], m[2]), last ? 60f : 36f, last ? blue : teal, last ? 3f : 2f);
                Beam(new Vector3(m[0], m[1], m[2] + 4), new Vector3(m[0], m[1], m[2] + (last ? 140 : 70)), last ? blue : teal, last ? 3f : 2f);
            }
        }
        else if (drill.Variant == "jump" && drill.Target is { Length: >= 3 } tg)
        {   // where to jump from, where to land (a post over it: seen from below the box)
            if (drill.From is { Length: >= 3 } f) Ring(new Vector3(f[0], f[1], f[2]), 20f, green, 1.5f);
            Ring(new Vector3(tg[0], tg[1], tg[2]), 36f, blue, 2.5f);
            Beam(new Vector3(tg[0], tg[1], tg[2] + 4), new Vector3(tg[0], tg[1], tg[2] + 110), blue, 3f);
        }
    }

    void Ring(Vector3 c, float r, System.Drawing.Color col, float w)
    {
        for (int i = 0; i < 12; i++)
        {
            float a0 = i * MathF.PI / 6, a1 = (i + 1) * MathF.PI / 6;
            Beam(c + new Vector3(r * MathF.Cos(a0), r * MathF.Sin(a0), 4), c + new Vector3(r * MathF.Cos(a1), r * MathF.Sin(a1), 4), col, w);
        }
    }

    void MoGo() => MoNext();

    bool MoEnough()
    {
        if (drill == null) return true;
        var n = Math.Max(1, drill.Count);
        return drill.Variant switch
        {
            "route" => moRuns.Count >= n,
            "silent" => moWalks.Count >= n || moWalks.Any(w => w.ok),
            "jump" => moJumps.Count(j => j.ok) >= Math.Max(1, drill.Goal) || moJumps.Count >= n,
            _ => moStops.Count >= n,
        };
    }

    // the next rep, or the drill's end
    void MoNext()
    {
        if (drill == null || cur == null || phase != "live") return;
        if (MoEnough() || (Server.TickCount - t0) / 64f >= drill.Seconds * 1.5f) { Finish("done"); return; }
        moRep++;
        moRepAt = Server.TickCount;
        moHinted = false;
        if (drill.Variant is "route" or "silent")
        {   // on the start, still a moment, then the clock (the first one right at GO)
            MoBack(true);
            if (moRep == 1) { MoRun(); return; }
            moStage = "ready";
            foreach (var h in Humans()) if (h.PlayerPawn.Value is { } pw) Freeze(pw, true);
            Html($"<font color='#56d4c8'>{T("READY")}</font> · {F("run {i}/{n}", "i", moRep, "n", Math.Max(1, drill.Count))}", 2);
            var g = generation;
            AddTimer(1.5f, () => { if (g == generation && phase == "live" && moStage == "ready") MoRun(); });
        }
        else if (drill.Variant == "jump") { MoBack(true); moStage = "jump"; }
        else
        {   // a stop: you stay where you strafe (back on the spot only when far from it)
            MoBack(moRep == 1);
            moStage = "strafe";
            moFastSince = moStopDue = moStopAt = moDropAt = moStillAt = -1;
        }
    }

    void MoRun()
    {
        moStage = "run";
        moRepAt = Server.TickCount;
        moNext = moMissed = moSteps = moHops = 0;
        foreach (var h in Humans()) if (h.PlayerPawn.Value is { } pw) Freeze(pw, false);
        Html($"<font color='#56d4c8'>{T("GO")}</font>", 1);
    }

    // you on the drill's start, alive, still (always: a new rep; else only when far from it)
    void MoBack(bool always)
    {
        var me = cur?.Players.FirstOrDefault(p => p.Me);
        if (me == null) return;
        foreach (var h in Humans())
        {
            var fresh = !h.PawnIsAlive;
            if (fresh) { h.Respawn(); Loadout(h, me, 100); }
            var pw = h.PlayerPawn.Value;
            if (pw == null) continue;
            if (!always && !fresh && pw.AbsOrigin is { } o && Vector3.Distance(new Vector3(o.X, o.Y, o.Z), Pos(me, 0)) < 400) continue;
            pw.Teleport(Pos(me, 0), Upright(Ang(me, 0)), Vector3.Zero);
        }
    }

    CCSPlayerPawn? MoPawn() => Humans().Select(h => h.PlayerPawn.Value)
        .FirstOrDefault(p => p != null && p.IsValid && p.LifeState == (byte)LifeState_t.LIFE_ALIVE);

    // each tick of a momentum drill: its rep, the screen
    void MoTick(float el)
    {
        if (drill == null || cur == null) return;
        if (el > drill.Seconds * 2 + 60) { Finish("timeout"); return; }   // never stuck
        var now = Server.TickCount;
        var pw = MoPawn();
        if (pw?.AbsOrigin == null)
        {   // dead (a fall off the map): that rep missed, back on the start
            if (moStage is not ("dead" or "after"))
            {
                MoMiss(T("fell"));
                moStage = "dead";
            }
        }
        else
        {
            var at = new Vector3(pw.AbsOrigin.X, pw.AbsOrigin.Y, pw.AbsOrigin.Z);
            switch (moStage)
            {
                case "run": MoRunTick(at, now); break;
                case "jump": MoJumpWait(at, now); break;
                case "air": MoAirTick(pw, at, now); break;
                case "strafe" or "brake" or "over": MoStopTick(pw, now); break;
            }
        }
        SetMain($"<font color='#56d4c8'>{drill.Title}</font> · {MoLine(now)}<br><font class='fontSize-s'>{drill.Tip}</font>");
    }

    string MoLine(int now)
    {
        if (drill == null) return "";
        var n = Math.Max(1, drill.Count);
        var t = moStage == "run" ? (now - moRepAt) / 64.0 : 0;
        return drill.Variant switch
        {
            "route" => $"{F("run {i}/{n}", "i", Math.Max(1, moRep), "n", n)} · ⏱ {Sec(t, 1)} s · {F("checkpoint {i}/{n}", "i", Math.Min(moNext + 1, drill.Marks.Count), "n", drill.Marks.Count)}"
                       + (drill.Par > 0 ? $" · {F("base {s} s", "s", Sec(drill.Par, 1))}" : ""),
            "silent" => $"👣 {moSteps} · ⏱ {Sec(t, 1)} / {Sec(drill.Par, 1)} s",
            "jump" => $"{F("{a}/{b} landed", "a", moJumps.Count(j => j.ok), "b", Math.Max(1, drill.Goal))} · {F("try {i}/{n}", "i", Math.Min(n, moJumps.Count + 1), "n", n)}",
            _ => $"{F("stop {i}/{n}", "i", Math.Max(1, moRep), "n", n)} · ✔ {moStops.Count(s => s.why == "")}"
                 + (moStage == "strafe" ? $" · {T("run left and right (A, D)")}" : ""),
        };
    }

    // a run or a walk: the checkpoints in order (one reached past another: that one missed), the end
    void MoRunTick(Vector3 at, int now)
    {
        if (drill == null) return;
        var t = (now - moRepAt) / 64.0;
        var M = drill.Marks;
        for (int k = moNext; k < M.Count; k++)
        {
            var m = M[k];
            var last = k == M.Count - 1;
            if (Flat(at, m) > (last ? EndR : CpR) || MathF.Abs(at.Z - m[2]) > 110) continue;
            moMissed += k - moNext;
            moNext = k + 1;
            if (last) { MoArrive(t); return; }
            if (drill.Variant == "route" && drill.Par > 0)
            {   // the base's pace there
                var dv = t - drill.Par * (m.Length > 3 ? m[3] : (k + 1f) / M.Count);
                Html($"<font color='{(dv <= 0 ? "#5ad15a" : "#e0a030")}'>{k + 1}/{M.Count} · {Sec(t, 1)} s · {dv.ToString("+0.0;-0.0;0.0", CultureInfo.InvariantCulture)} s</font>", 1);
            }
            break;
        }
        var limit = drill.Variant == "silent" ? drill.Par + 6 : Math.Max(20, drill.Par * 2 + 8);
        if (t > limit) MoArrive(-1);
    }

    // the way's end (time -1: too slow)
    void MoArrive(double time)
    {
        if (drill == null || moStage != "run") return;
        moStage = "after";
        if (drill.Variant == "route")
        {
            var valid = time >= 0 && moMissed == 0;
            moRuns.Add((valid, time, moMissed));
            Html(time < 0 ? $"<font color='#ff5a5a'>✘ {T("TOO SLOW")}</font>"
                : !valid ? $"<font color='#ff5a5a'>✘ {T("OFF THE WAY")}</font> · {Tn(moMissed, "{n} checkpoint missed", "{n} checkpoints missed")} · {Sec(time)} s"
                : $"<font color='{(drill.Par <= 0 || time <= drill.Par ? "#5ad15a" : "#e0a030")}'>⏱ {Sec(time)} s</font> · {F("base {s} s", "s", Sec(drill.Par, 1))}"
                  + (drill.Best > 0 ? $" · {F("its fastest {s} s", "s", Sec(drill.Best, 1))}" : "") + (drill.Pro > 0 ? $" · {F("pros {s} s", "s", Sec(drill.Pro, 1))}" : ""), 2);
        }
        else
        {
            var ok = time >= 0 && time <= drill.Par && moSteps == 0 && moHops == 0 && moMissed == 0;
            moWalks.Add((ok, time, moSteps, moHops, moMissed));
            Html(ok ? $"<font color='#5ad15a'>✔ {T("NOT HEARD")}</font> · {Sec(time, 1)} s"
                : time < 0 || time > drill.Par ? $"<font color='#ff5a5a'>✘ {T("TOO SLOW")}</font>{(time >= 0 ? $" · {Sec(time, 1)} / {Sec(drill.Par, 1)} s" : "")}"
                : moMissed > 0 ? $"<font color='#ff5a5a'>✘ {T("OFF THE WAY")}</font>"
                : $"<font color='#ff5a5a'>✘ {T("HEARD")}</font> · {Tn(moSteps, "{n} footstep", "{n} footsteps")}{(moHops > 0 ? $" · {Tn(moHops, "{n} jump", "{n} jumps")}" : "")}", 2);
        }
        var g = generation;
        AddTimer(2f, () => { if (g == generation && phase == "live") MoNext(); });
    }

    // a rep lost to a death (a fall off the map)
    void MoMiss(string why)
    {
        if (drill == null) return;
        if (drill.Variant == "route") moRuns.Add((false, -1, 0));
        else if (drill.Variant == "silent") moWalks.Add((false, -1, 0, 0, 0));
        else if (drill.Variant == "jump") moJumps.Add((false, why, -1, false));
        Html($"<font color='#ff5a5a'>✘ {why}</font>", 1);
        var g = generation;
        AddTimer(1f, () => { if (g == generation && phase == "live") MoNext(); });
    }

    // the game's footsteps and jumps: heard on a silent walk; a jump's takeoff
    void MoStep(CCSPlayerController? p)
    {
        if (!MoOn || drill!.Variant != "silent" || moStage != "run" || p is not { IsValid: true, IsBot: false } || phase != "live") return;
        moSteps++;
        Html($"<font color='#ff5a5a'>👣 {T("heard")}</font>", 1);
    }

    void MoJump(CCSPlayerController? p)
    {
        if (!MoOn || p is not { IsValid: true, IsBot: false } || phase != "live") return;
        if (drill!.Variant == "silent" && moStage == "run") { moHops++; Html($"<font color='#ff5a5a'>{T("jump heard")}</font>", 1); return; }
        if (drill.Variant != "jump" || moStage != "jump" || drill.From is not { Length: >= 3 } f) return;
        var o = p.PlayerPawn.Value?.AbsOrigin;
        if (o == null) return;
        if (Flat(new Vector3(o.X, o.Y, o.Z), f) > 120 || MathF.Abs(o.Z - f[2]) > 48)
        {   // a hop anywhere else is no try
            Html($"<font color='#e0a030'>{T("from the green ring")}</font>", 1);
            return;
        }
        moStage = "air";
        moAirAt = Server.TickCount;
        moAirDuck = false;
    }

    // waiting for the jump: back on the start when you went far, a reminder after 12 s
    void MoJumpWait(Vector3 at, int now)
    {
        if (drill?.From is not { Length: >= 3 } f) return;
        if (Flat(at, f) > 700) { MoBack(true); return; }
        if (!moHinted && now - moRepAt > 12 * 64) { moHinted = true; Html($"<font color='#e0a030'>{T("from the green ring, land in the blue one")}</font>", 2); }
    }

    // in the air: crouched or not; landed (on the ground again): on top or not, and why
    void MoAirTick(CCSPlayerPawn pw, Vector3 at, int now)
    {
        if (drill?.Target is not { Length: >= 3 } tg) return;
        var duck = pw.MovementServices == null ? 0f : new CCSPlayer_MovementServices(pw.MovementServices.Handle).DuckAmount;
        if (duck > 0.5f) moAirDuck = true;
        if (now - moAirAt < 6) return;
        var ground = (pw.Flags & (uint)PlayerFlags.FL_ONGROUND) != 0;
        if (!ground && now - moAirAt < 3 * 64) return;
        moStage = "after";
        var dz = at.Z - tg[2];
        var off = Flat(at, tg);
        var ok = ground && dz >= -18 && dz <= 24 && off <= 140;
        var crouch = drill.How.Contains("duck");
        var why = ok ? "" : dz < -18 ? (crouch && !moAirDuck ? T("crouch in the air: the base's jumpers do") : T("short of the top: jump at the edge of the green ring"))
            : T("on top, but off the blue ring");
        moJumps.Add((ok, why, off, moAirDuck));
        Html(ok ? $"<font color='#5ad15a'>✔ {T("LANDED")}</font> · {F("{a}/{b} landed", "a", moJumps.Count(j => j.ok), "b", Math.Max(1, drill.Goal))}"
                : $"<font color='#ff5a5a'>✘ {T("MISSED")}</font> · {why}", 2);
        var g = generation;
        AddTimer(ok ? 1.2f : 1.6f, () => { if (g == generation && phase == "live") MoNext(); });
    }

    // a stop: at full speed 0.25 s, STOP 0.2 to 0.8 s later (still at full speed then); the drop, the stop, the way back
    void MoStopTick(CCSPlayerPawn pw, int now)
    {
        var v = pw.AbsVelocity;
        var vel = new Vector2(v?.X ?? 0f, v?.Y ?? 0f);
        var sp = vel.Length();
        switch (moStage)
        {
            case "strafe":
                if (sp >= 180f) { if (moFastSince < 0) moFastSince = now; }
                else moFastSince = -1;
                if (moFastSince >= 0 && moStopDue < 0 && now - moFastSince >= 16) moStopDue = now + Rng.Next(12, 52);
                if (moStopDue >= 0 && now >= moStopDue)
                {
                    if (sp < 180f) { moStopDue = -1; break; }   // slowed down on its own: full speed again first
                    moStage = "brake";
                    moStopAt = now; moTop = sp; moWay = Vector2.Normalize(vel); moDropAt = moStillAt = -1;
                    Html($"<font color='#ff5a5a' class='fontSize-xl'>■ {T("STOP")}</font>", 1);
                }
                break;
            case "brake":
                if (moDropAt < 0 && sp < 0.92f * moTop) moDropAt = now;
                if (sp <= StopShare * moTop) { moStillAt = now; moStage = "over"; }
                else if (now - moStopAt > 96) MoStopDone(false);   // 1.5 s: no stop
                break;
            case "over":
                if (Vector2.Dot(vel, moWay) < -StopShare * moTop) MoStopDone(true);   // off again the other way
                else if (now - moStillAt >= 20) MoStopDone(false);
                break;
        }
    }

    void MoStopDone(bool over)
    {
        if (drill == null) return;
        moStage = "after";
        var drop = moDropAt >= 0 ? moDropAt : moStopAt;
        var react = (drop - moStopAt) / 64.0;
        var brake = moStillAt >= 0 ? (moStillAt - drop) / 64.0 : -1;
        var why = moStillAt < 0 ? T("no stop") : over ? T("the other key held too long: you went the other way")
            : brake > BrakeOk ? T("a key let go only: tap the other one") : "";
        moStops.Add((react, brake, over, why));
        var ms = brake >= 0 ? $"{Math.Round(brake * 1000)} ms" : "";
        Html(why == "" ? $"<font color='#5ad15a'>✔ {T("DEAD STOP")}</font> · {ms}" : $"<font color='#ff5a5a'>✘ {why}</font>{(ms != "" ? $" · {ms}" : "")}", 1);
        var g = generation;
        AddTimer(0.8f, () => { if (g == generation && phase == "live") MoNext(); });
    }

    // the drill's result: ok, points, the line said (and the measures written with it)
    (bool ok, int pts, string detail) MoResult()
    {
        if (drill == null) return (false, 0, "");
        switch (drill.Variant)
        {
            case "route":
            {
                drillExtra["runs"] = moRuns.Select(r => new Dictionary<string, object> { ["valid"] = r.valid, ["time"] = Math.Round(r.time, 2), ["missed"] = r.missed }).ToList();
                drillExtra["par"] = drill.Par;
                var valid = moRuns.Where(r => r.valid).Select(r => r.time).ToList();
                var off = moRuns.Count(r => !r.valid && r.time >= 0);
                if (valid.Count == 0)
                    return (false, 0, moRuns.Count > 0 ? T("no run through every ring, in order") : T("no run"));
                var best = valid.Min();
                var ok = drill.Par <= 0 || best <= drill.Par;
                var pts = 30 * valid.Count + (ok ? 100 : 0) + (drill.Best > 0 && best <= drill.Best ? 60 : 0) + (drill.Pro > 0 && best <= drill.Pro ? 40 : 0)
                          + (int)Math.Max(0, (drill.Par - best) * 20);
                return (ok, pts, F("best run {s} s", "s", Sec(best)) + $" · {F("base {s} s", "s", Sec(drill.Par, 1))}"
                                 + (drill.Best > 0 ? $" · {F("its fastest {s} s", "s", Sec(drill.Best, 1))}" : "")
                                 + (drill.Pro > 0 ? $" · {F("pros {s} s", "s", Sec(drill.Pro, 1))}" : "")
                                 + (off > 0 ? $" · {Tn(off, "{n} run off the way", "{n} runs off the way")}" : ""));
            }
            case "jump":
            {
                drillExtra["jumps"] = moJumps.Select(j => new Dictionary<string, object> { ["ok"] = j.ok, ["off"] = Math.Round(j.off), ["duck"] = j.duck }).ToList();
                var n = moJumps.Count;
                var landed = moJumps.Count(j => j.ok);
                var ok = landed >= Math.Max(1, drill.Goal);
                var pts = 50 * landed + (ok ? 100 : 0) + (n > 0 && moJumps[0].ok ? 30 : 0);
                var why = moJumps.Where(j => !j.ok).GroupBy(j => j.why).Select(g => $" · {g.Key} ×{g.Count()}");
                return (ok, pts, n == 0 ? T("no jump from the green ring") : F("{a}/{b} landed", "a", landed, "b", n) + string.Concat(why));
            }
            case "stop":
            {
                drillExtra["stops"] = moStops.Select(s => new Dictionary<string, object> { ["react"] = Math.Round(s.react, 3), ["brake"] = Math.Round(s.brake, 3), ["over"] = s.over }).ToList();
                var n = moStops.Count;
                var clean = moStops.Count(s => s.why == "");
                var ok = n > 0 && clean * 4 >= n * 3;   // 6 of 8
                var br = moStops.Where(s => s.brake >= 0).Select(s => s.brake).ToList();
                var rc = moStops.Where(s => s.brake >= 0).Select(s => s.react).ToList();
                var why = moStops.Where(s => s.why != "").GroupBy(s => s.why).Select(g => $" · {g.Key} ×{g.Count()}");
                return (ok, 25 * clean + (ok ? 100 : 0), n == 0 ? T("no stop") : F("{a}/{b} dead stops", "a", clean, "b", n)
                    + (br.Count > 0 ? $" · {F("{ms} ms to stop", "ms", Math.Round(br.Average() * 1000))}" : "")
                    + (rc.Count > 0 ? $" · {F("{ms} ms to react", "ms", Math.Round(rc.Average() * 1000))}" : "") + string.Concat(why));
            }
            default:
            {
                drillExtra["walks"] = moWalks.Select(w => new Dictionary<string, object> { ["ok"] = w.ok, ["time"] = Math.Round(w.time, 2), ["steps"] = w.steps, ["jumps"] = w.hops }).ToList();
                drillExtra["par"] = drill.Par;
                var ok = moWalks.Any(w => w.ok);
                var w0 = moWalks.Where(w => w.ok).Concat(moWalks).FirstOrDefault();
                if (moWalks.Count == 0) return (false, 0, T("no walk"));
                return (ok, ok ? 150 + (moWalks[0].ok ? 50 : 0) : 0, ok ? $"{T("not heard")} · {Sec(w0.time, 1)} / {Sec(drill.Par, 1)} s"
                    : string.Join(" · ", moWalks.Select(w => w.time < 0 || w.time > drill.Par ? T("too slow") : w.missed > 0 ? T("off the way")
                        : Tn(w.steps + w.hops, "{n} sound heard", "{n} sounds heard"))));
            }
        }
    }
}
