// Crossfire (13/10, the user: "simule de vrais duels avec des bots utilisant des mouvements réalistes pour travailler le
// counter-strafing et la tenue d'angles + spray practice: two bots picking the same angle at 2 different positions and
// 2 different timings, kill the first and the second with one and only spray, 30 bullets at most without stop
// shooting"). It replaces the aim map at the warm-up's start, on the session's real map (crossfire.py builds the drills
// from the base's duels). A drill is a series of reps:
// - hold: you on a spot the base holds, crosshair on its angle; an enemy comes out with a real player's peek (his way,
//   his speed, his stops, every 2 ticks), after a wait that changes each time, and fights you once it has seen you a
//   player's reaction time (the bots' level);
// - peek: the other way round: you start where a real peek started, the enemy holds the angle; your shots fired while
//   moving are counted (counter-strafe);
// - spray: two enemies come out nearly on one line from your spot, one deeper, each with the real peek that brought a
//   player there, the second 0.3 to 0.9 s after the first; they don't shoot. Both must die in one spray: no gap
//   between two bullets longer than the gun's rate, 30 bullets (the magazine; it is not refilled).
// 14/10, his test on Inferno: an enemy off its way (its peek over, hit, or close to you) stops where it is and fights you
// there, never roams away on the game's AI ("le bot il s'en va"); at each rep of a hold or a peek, the enemy glows
// through the walls a moment first, where it is ("pour savoir quel angle je dois regarder").
// Measured: duels won, headshots, how far your crosshair was from the enemy's head when he came into your sight, the
// time to kill from then, the shots fired while moving; for the spray: the clean sprays, their bullets, why one failed.
using System.Globalization;
using System.Numerics;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace CoachReplay;

public partial class CoachReplay
{
    bool CfSpray => drill is { Mode: "crossfire", Variant: "spray" };

    int cfRep, cfWon, cfLost, cfNone, cfHs, cfRepAt, cfSeenAt, cfShots, cfMoving;
    float cfOff = -1;
    bool cfResolved = true;
    readonly HashSet<int> cfHiding = new();   // bots taken away between two reps: their deaths count for nothing
    readonly List<(bool won, float off, double ttk)> cfLog = new();
    // the spray: when each enemy comes out, the spray's first and last bullet (ticks), its bullets, the kills
    int spAppear1, spAppear2, spFirst, spLast, spBullets, spKills, spKill1At, spMag = 30;
    readonly List<CBaseModelEntity> cfGlow = new();   // the enemy's glow at a rep's start (two props: a relay and the glow)
    int cfGlowN, cfGlowSlot = -1, cfGlowUntil;   // whose glow, until when (it is on your radar meanwhile)
    readonly List<(string outcome, int bullets, double transfer)> spLog = new();
    const int SprayGap = 12;   // ticks between two bullets beyond which the spray stopped (a rifle fires every 6 to 7)
    const float MovingShot = 75f;   // u/s: over 34 % of a rifle's speed the shot is inaccurate (Leetify's measure)
    readonly Dictionary<string, object> drillExtra = new();   // a drill's measures, written with its result

    void RegisterCrossfire()
    {
        RegisterEventHandler<EventWeaponFire>((e, _) => { CfShot(e.Userid, e.Weapon ?? ""); return HookResult.Continue; });
    }

    Scenario CrossfireScenario(Drill d)
    {
        var s = new Scenario { Id = d.Id, Map = d.Map, Kind = "aim", Title = d.Title, Team = d.Team };
        var me = d.Me ?? new Spot();
        s.Players.Add(new Track { Sid = "me", Name = "you", Team = d.Team, Me = true, Hp = 100, Armor = d.Armor, Helmet = d.Helmet, Weapons = d.Weapons,
            Active = d.Weapons.LastOrDefault(), Path = new[] { me.Pos[0], me.Pos[1], me.Pos[2], me.Ang[1], me.Ang[0] } });
        var foe = 5 - d.Team;
        var w = d.BotWeapons;
        Track Bot(int k, string name, float[] path, bool hold, bool still) => new()
        {
            Sid = $"cf{k}", Name = name, Team = foe, Hp = 100, Armor = 100, Helmet = true, Weapons = w, Active = w.LastOrDefault(),
            Path = path, Hold = hold, Still = still,
        };
        float[] At(Spot b) => new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] };
        if (d.Variant == "hold" && d.Tracks.Count > 0)
        {
            var tr = d.Tracks[Rng.Next(d.Tracks.Count)];
            s.Players.Add(Bot(0, tr.Zone, tr.Path, false, false));
        }
        else if (d.Variant == "peek" && d.Bots.Count > 0)
            s.Players.Add(Bot(0, d.Bots[0].Zone ?? "?", At(d.Bots[0]), true, false));
        else if (d.Variant == "spray" && d.Bots.Count >= 2)
            for (int k = 0; k < 2; k++) s.Players.Add(Bot(k, d.Bots[k].Zone ?? "?", d.Tracks.Count > k ? d.Tracks[k].Path : At(d.Bots[k]), false, false));
        // the doors on every real peek's way open, as in their matches (a rep takes any of them)
        foreach (var tr in d.Tracks)
            for (int i = 0; i + 2 < tr.Path.Length; i += 20) s.Trail.Add(new[] { tr.Path[i], tr.Path[i + 1], tr.Path[i + 2] });
        return s;
    }

    // Place() is done: the counters from zero; the spray's enemies wait (dead) for their moment
    void CfPlaced()
    {
        cfRep = cfWon = cfLost = cfNone = cfHs = cfShots = cfMoving = 0;
        cfLog.Clear(); spLog.Clear(); cfHiding.Clear(); drillExtra.Clear();
        cfResolved = true;
        aimOrder.Clear();
        aimOrder.AddRange(bots.Keys);
        CfGlowOff();
        if (!CfSpray && bots.FirstOrDefault(b => b.Value.Sid == "cf0") is { Value: not null } kv && Utilities.GetPlayerFromSlot(kv.Key) is { IsValid: true } c0)
            CfGlowOn(c0, 3.2f);   // the countdown's 3 s: where the first one waits
    }

    void CfGo() => CfNext();

    // the next rep, or the drill's end
    void CfNext()
    {
        if (drill == null || cur == null || phase != "live") return;
        if (cfRep >= Math.Max(1, drill.Count) || (Server.TickCount - t0) / 64f >= drill.Seconds) { Finish("done"); return; }
        cfRep++;
        cfResolved = false;
        CfGlowOff();
        cfRepAt = Server.TickCount;
        cfSeenAt = -1;
        cfOff = -1;
        var me = cur.Players.First(p => p.Me);
        var at = Pos(me, 0);
        var face = Upright(Ang(me, 0));
        if (drill.Variant == "peek" && drill.Tracks.Count > 0 && cfRep > 1)
        {   // where a real peek started, turned the way it went
            var tr = drill.Tracks[Rng.Next(drill.Tracks.Count)];
            at = new Vector3(tr.Path[0], tr.Path[1], tr.Path[2]);
            face = new Vector3(0, tr.Path[3], 0);
        }
        foreach (var h in Humans())
        {
            var fresh = !h.PawnIsAlive;
            if (fresh) { h.Respawn(); Loadout(h, me, 100); }
            var pw = h.PlayerPawn.Value;
            if (pw == null) continue;
            pw.Teleport(at, face, Vector3.Zero);
            if (!fresh)
            {   // alive: the same guns (no draw time), full again
                pw.Health = 100;
                Utilities.SetStateChanged(pw, "CBaseEntity", "m_iHealth");
                FullMag(h);
            }
        }
        protectUntil = Server.TickCount + 32;
        if (drill.Variant == "hold") CfPeeker();
        else if (drill.Variant == "peek") CfHolder();
        else CfSprayArm();
    }

    // hold: the enemy comes out with one of the real peeks, after a wait of its own
    void CfPeeker()
    {
        if (drill == null || cur == null || drill.Tracks.Count == 0) return;
        var (sl, t) = bots.FirstOrDefault(b => b.Value.Sid == "cf0");
        var c = t == null ? null : Utilities.GetPlayerFromSlot(sl);
        if (t == null || c == null || !c.IsValid) return;
        var first = cfRep == 1;   // the countdown showed this one where it waits: the same way
        var tr = first ? drill.Tracks.FirstOrDefault(x => x.Path == t.Path) ?? drill.Tracks[0] : drill.Tracks[Rng.Next(drill.Tracks.Count)];
        t.Path = tr.Path;
        t.Hold = t.Still = false;   // planted at the last rep's end: on its way again
        t.TrackNades = new();
        t.NadeNext = 0;
        var wait = first ? 0.3f + (float)Rng.NextDouble() * 1.0f : 1.7f + (float)Rng.NextDouble() * 1.0f;   // it glows 1.5 s first: then it comes, when it wants
        t.Start = (Server.TickCount - t0) / (float)cur.Step + wait * 64f / cur.Step;
        if (!c.PawnIsAlive) c.Respawn();
        Loadout(c, t);
        free.Remove(sl); contact.Remove(sl); engaged.Remove(sl); sawYou.Remove(sl); gone.Remove(t.Sid);
        if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, false); }   // it waits on its start, then walks its way
        c.PlayerName = tr.Zone;
        Utilities.SetStateChanged(c, "CBasePlayerController", "m_iszPlayerName");
        if (!first) CfGlowOn(c, 1.5f);
    }

    // peek: the enemy back on the angle it holds, its reaction from zero
    void CfHolder()
    {
        var (sl, t) = bots.FirstOrDefault(b => b.Value.Sid == "cf0");
        var c = t == null ? null : Utilities.GetPlayerFromSlot(sl);
        if (t == null || c == null || !c.IsValid) return;
        if (!c.PawnIsAlive) c.Respawn();
        Loadout(c, t);
        if (drill?.Bots.Count > 0) { var b = drill.Bots[0]; t.Path = new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] }; }
        t.Hold = true; t.Still = false;
        contact.Remove(sl); sawYou.Remove(sl); gone.Remove(t.Sid); free.Remove(sl);
        if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, true); }
        if (cfRep > 1) CfGlowOn(c, 1.5f);   // the first: the countdown showed it
    }

    // spray: a pair of spots, each enemy on the real peek that brought a player there, the moments they come out
    void CfSprayArm()
    {
        if (drill == null || cur == null) return;
        var pairs = drill.Bots.Count / 2;
        var p = Rng.Next(Math.Max(1, pairs));
        var deep = Rng.Next(2);   // the near one first, or the deep one
        var now = Server.TickCount;
        var d1 = 0.2 + Rng.NextDouble() * 0.6;
        var d2 = d1 + 0.3 + Rng.NextDouble() * 0.6;   // 14/10: "à des timings différents"
        foreach (var (sl, t) in bots)
        {
            var k = t.Sid == "cf1" ? 1 : 0;
            var idx = 2 * p + (k ^ deep);
            if (idx >= drill.Bots.Count) continue;
            var b = drill.Bots[idx];
            t.Path = idx < drill.Tracks.Count && drill.Tracks[idx].Path.Length >= 10 ? drill.Tracks[idx].Path : new[] { b.Pos[0], b.Pos[1], b.Pos[2], b.Ang[1], b.Ang[0] };
            t.Hold = t.Still = false;
            var delay = k == 0 ? d1 : d2;
            t.Start = (now - t0) / (float)cur.Step + (float)delay * 64f / cur.Step;
            // seen about 1.25 s after it sets off (its peek starts 40 frames before the other team saw it)
            var seen = now + (int)(delay * 64) + Math.Min(80, Math.Max(0, t.Frames - 1) * cur.Step);
            if (k == 0) spAppear1 = seen; else spAppear2 = seen;
            var c = Utilities.GetPlayerFromSlot(sl);
            if (c == null || !c.IsValid) continue;
            if (!c.PawnIsAlive) c.Respawn();
            Loadout(c, t);
            free.Remove(sl); contact.Remove(sl); engaged.Remove(sl); sawYou.Remove(sl); gone.Remove(t.Sid);
            if (c.PlayerPawn.Value is { } pw) { pw.Teleport(Pos(t, 0), Upright(Ang(t, 0)), Vector3.Zero); Freeze(pw, false); }
        }
        if (spAppear2 < spAppear1) (spAppear1, spAppear2) = (spAppear2, spAppear1);
        spFirst = spLast = spKill1At = -1;
        spBullets = spKills = 0;
        var w = Humans().FirstOrDefault(x => x.PawnIsAlive)?.PlayerPawn.Value?.WeaponServices?.ActiveWeapon.Value;
        spMag = w is { IsValid: true } && (w.VData?.MaxClip1 ?? 0) > 0 ? w.VData!.MaxClip1 : 30;   // an M4A1-S: 20
    }

    // an enemy off its way (its peek over, hit, close to you, fighting off it): it stops there and fights you, turned to
    // you; the spray's stands still (it never fires). Never the game's AI: it went away (14/10)
    bool CfPlant(CCSPlayerController c, Track t)
    {
        var pw = c.PlayerPawn.Value;
        if (pw?.AbsOrigin == null) return false;
        var me = Humans().Select(h => h.PlayerPawn.Value?.AbsOrigin).FirstOrDefault(o => o != null);
        var at = new Vector3(pw.AbsOrigin.X, pw.AbsOrigin.Y, pw.AbsOrigin.Z);
        var yaw = me == null ? pw.EyeAngles?.Y ?? 0f : MathF.Atan2(me.Y - at.Y, me.X - at.X) * 180 / MathF.PI;
        t.Path = new[] { at.X, at.Y, at.Z, yaw, 0f };
        t.Hold = true;
        t.Still = CfSpray;
        Freeze(pw, true);
        Log("plant {n}", t.Name);
        return true;
    }

    // the enemy through the walls a moment, where it is (a copy of its model that follows it and glows; 14/10: "mettre
    // en surbrillance à travers le mur où est le bot au tout début du round")
    void CfGlowOn(CCSPlayerController c, float secs)
    {
        CfGlowOff();
        var n = ++cfGlowN;
        cfGlowSlot = c.Slot;
        cfGlowUntil = Server.TickCount + (int)(secs * 64);
        // 14/10: made at once after the respawn of a bot killed the rep before, it had no model yet: nothing glowed
        AddTimer(0.15f, () => { if (n == cfGlowN && c.IsValid) CfGlowMake(c, n, secs - 0.15f); });
    }

    void CfGlowMake(CCSPlayerController c, int n, float secs)
    {
        try
        {
            var pw = c.PlayerPawn.Value;
            if (pw == null || !pw.IsValid) return;
            var model = pw.CBodyComponent?.SceneNode?.GetSkeletonInstance()?.ModelState.ModelName;
            if (string.IsNullOrEmpty(model))
                model = c.Team == CsTeam.Terrorist ? "characters/models/tm_phoenix/tm_phoenix.vmdl" : "characters/models/ctm_sas/ctm_sas.vmdl";
            var relay = Utilities.CreateEntityByName<CBaseModelEntity>("prop_dynamic");
            var glow = Utilities.CreateEntityByName<CBaseModelEntity>("prop_dynamic");
            if (relay == null || glow == null) return;
            relay.SetModel(model);
            relay.Spawnflags = 256u;
            relay.RenderMode = RenderMode_t.kRenderNone;
            relay.DispatchSpawn();
            glow.SetModel(model);
            glow.Spawnflags = 256u;
            glow.DispatchSpawn();
            glow.Glow.GlowColorOverride = System.Drawing.Color.FromArgb(255, 255, 80, 60);
            glow.Glow.GlowRange = 5000;
            glow.Glow.GlowRangeMin = 0;
            glow.Glow.GlowTeam = -1;
            glow.Glow.GlowType = 3;
            relay.AcceptInput("FollowEntity", pw, relay, "!activator");
            glow.AcceptInput("FollowEntity", relay, glow, "!activator");
            cfGlow.Add(relay);
            cfGlow.Add(glow);
            Log("glow {n} ({m}) {s} s", c.PlayerName, model, Math.Round(secs, 1));
            AddTimer(Math.Max(0.1f, secs), () => { if (n == cfGlowN) CfGlowOff(); });
        }
        catch (Exception e) { Log("glow: {m}", e.Message); }
    }

    void CfGlowOff()
    {
        foreach (var e in cfGlow) if (e.IsValid) e.Remove();
        cfGlow.Clear();
        cfGlowUntil = 0;
        cfGlowN++;   // one still to be made: not any more
    }

    // while it glows, the enemy is on your radar too (the game's own spotting, set each tick)
    void CfRadar()
    {
        if (cfGlowSlot < 0 || Server.TickCount > cfGlowUntil) return;
        var pw = Utilities.GetPlayerFromSlot(cfGlowSlot)?.PlayerPawn.Value;
        var h = Humans().FirstOrDefault();
        if (pw == null || !pw.IsValid || h == null) return;
        pw.EntitySpottedState.Spotted = true;
        pw.EntitySpottedState.SpottedByMask[h.Slot / 32] |= 1u << (h.Slot % 32);
        Utilities.SetStateChanged(pw, "CCSPlayerPawn", "m_entitySpottedState");
    }

    // each tick of a crossfire drill: the moments, the first sight, the spray's rules, the screen
    void CfTick(float el)
    {
        if (drill == null || cur == null) return;
        var now = Server.TickCount;
        if (!cfResolved)
        {
            if (CfSpray)
            {
                if (spFirst >= 0 && spKills < 2 && Clip() == 0) CfSprayEnd("out of ammo");
                else if (spFirst >= 0 && spKills < 2 && now - spLast > SprayGap) CfSprayEnd("released");
                else if (now - spAppear2 > 3 * 64) CfSprayEnd("too slow");
            }
            else
            {
                CfSight();
                if (now - cfRepAt > (drill.Variant == "peek" ? 12 : 10) * 64) CfEnd(null, false);   // no duel came of it
            }
        }
        var left = Math.Max(0, (int)(drill.Seconds - el));
        var n = Math.Max(1, drill.Count);
        var line = CfSpray
            ? $"{F("spray {i}/{n}", "i", Math.Max(1, cfRep), "n", n)} · ✔ {spLog.Count(x => x.outcome == "clean")} · {spBullets}/{spMag}"
            : $"{F("duel {i}/{n}", "i", Math.Max(1, cfRep), "n", n)} · ✔ {cfWon} · ✘ {cfLost}";
        SetMain($"<font color='#ff8a3d'>{drill.Title}</font> · {line} · {left} s<br><font class='fontSize-s'>{drill.Tip}</font>");
        if (el > drill.Seconds * 2 + 30) Finish("timeout");   // never stuck
    }

    // the enemy came into your sight: where your crosshair was (degrees from its head), when
    void CfSight()
    {
        if (cfSeenAt >= 0) return;
        var h = Humans().FirstOrDefault(x => x.PawnIsAlive);
        var me = h?.PlayerPawn.Value;
        if (h == null || me?.AbsOrigin == null || me.EyeAngles == null) return;
        foreach (var (sl, t) in bots)
        {
            if (gone.Contains(t.Sid)) continue;
            var pw = Utilities.GetPlayerFromSlot(sl)?.PlayerPawn.Value;
            if (pw?.AbsOrigin == null || pw.LifeState != (byte)LifeState_t.LIFE_ALIVE) continue;
            var m = pw.EntitySpottedState.SpottedByMask;
            if ((m[h.Slot / 32] & (1u << (h.Slot % 32))) == 0) continue;
            var duck = me.MovementServices == null ? 0f : new CCSPlayer_MovementServices(me.MovementServices.Handle).DuckAmount;
            var eye = new Vector3(me.AbsOrigin.X, me.AbsOrigin.Y, me.AbsOrigin.Z + 64 - 18 * duck);
            var head = new Vector3(pw.AbsOrigin.X, pw.AbsOrigin.Y, pw.AbsOrigin.Z + 62);
            cfSeenAt = Server.TickCount;
            cfOff = AngleOff(eye, me.EyeAngles.X, me.EyeAngles.Y, head);
            return;
        }
    }

    // your gun's magazine now (-1: none)
    int Clip()
    {
        var w = Humans().FirstOrDefault(x => x.PawnIsAlive)?.PlayerPawn.Value?.WeaponServices?.ActiveWeapon.Value;
        return w == null || !w.IsValid ? -1 : w.Clip1;
    }

    static float AngleOff(Vector3 eye, float pitch, float yaw, Vector3 at)
    {
        float p = pitch * MathF.PI / 180, y = yaw * MathF.PI / 180;
        var fw = new Vector3(MathF.Cos(p) * MathF.Cos(y), MathF.Cos(p) * MathF.Sin(y), -MathF.Sin(p));
        var to = at - eye;
        if (to.Length() < 1) return 0;
        return MathF.Acos(Math.Clamp(Vector3.Dot(fw, Vector3.Normalize(to)), -1f, 1f)) * 180 / MathF.PI;
    }

    // a shot of yours: moving or stopped; the spray's bullets and its gaps
    void CfShot(CCSPlayerController? p, string weapon)
    {
        if (drill?.Mode != "crossfire" || phase != "live" || p is not { IsValid: true, IsBot: false }) return;
        if (weapon.Contains("knife") || weapon.Contains("grenade") || weapon.Contains("flashbang") || weapon.Contains("molotov") || weapon.Contains("decoy")) return;
        var v = p.PlayerPawn.Value?.AbsVelocity;
        var speed = v == null ? 0f : MathF.Sqrt(v.X * v.X + v.Y * v.Y);
        cfShots++;
        if (speed > MovingShot) cfMoving++;
        if (!CfSpray || cfResolved) return;
        var now = Server.TickCount;
        if (spFirst >= 0 && now - spLast > SprayGap) { CfSprayEnd("released"); return; }
        if (spFirst < 0) spFirst = now;
        spLast = now;
        spBullets++;
    }

    // a death in a crossfire drill; true: handled (yours: back on your spot at the next rep)
    bool CfDeath(EventPlayerDeath e, CCSPlayerController v)
    {
        if (v.IsBot && cfHiding.Remove(v.Slot)) return false;   // taken away between two reps
        var byYou = e.Attacker is { IsValid: true, IsBot: false };
        if (CfSpray)
        {
            if (v.IsBot && byYou && !cfResolved)
            {
                spKills++;
                if (spKills == 1) spKill1At = Server.TickCount;
                else CfSprayEnd("clean");
            }
            return !v.IsBot;
        }
        if (cfResolved) return !v.IsBot;
        if (v.IsBot) { CfEnd(byYou ? true : null, byYou && e.Headshot); return false; }
        CfEnd(false, false);
        return true;
    }

    // a duel's end: won, lost, or none (it never came)
    void CfEnd(bool? won, bool hs)
    {
        if (cfResolved) return;
        cfResolved = true;
        var ttk = cfSeenAt >= 0 ? (Server.TickCount - cfSeenAt) / 64.0 : -1;
        if (won == true) { cfWon++; if (hs) cfHs++; }
        else if (won == false) cfLost++;
        else cfNone++;
        if (won != null) cfLog.Add((won.Value, cfOff, ttk));
        var off = cfOff >= 0 ? $" · {Math.Round(cfOff)}°" : "";
        Html(won == true ? $"<font color='#5ad15a'>✔ {T("WON")}</font>{(ttk >= 0 ? $" · {ttk.ToString("F2", CultureInfo.InvariantCulture)} s" : "")}{off}{(hs ? " · HS" : "")}"
            : won == false ? $"<font color='#ff5a5a'>✘ {T("LOST")}</font>{off}" : $"<font color='#e0a030'>{T("NO DUEL")}</font>", 1);
        var g = generation;
        AddTimer(won == false ? 1.4f : 0.9f, () => { if (g == generation && phase == "live") CfNext(); });
    }

    void CfSprayEnd(string outcome)
    {
        if (cfResolved) return;
        cfResolved = true;
        var transfer = outcome == "clean" && spKill1At >= 0 ? (Server.TickCount - spKill1At) / 64.0 : -1;
        spLog.Add((outcome, spBullets, transfer));
        Html(outcome == "clean"
            ? $"<font color='#5ad15a'>✔ {T("CLEAN SPRAY")}</font> · {Tn(spBullets, "{n} bullet", "{n} bullets")}{(transfer >= 0 ? $" · {T("transfer")} {transfer.ToString("F2", CultureInfo.InvariantCulture)} s" : "")}"
            : $"<font color='#ff5a5a'>✘ {T(outcome switch { "released" => N("YOU LET GO"), "out of ammo" => N("OUT OF AMMO"), _ => N("TOO SLOW") })}</font> · {Tn(spBullets, "{n} bullet", "{n} bullets")}", 1);
        var g = generation;
        AddTimer(1.3f, () => { if (g == generation && phase == "live") CfNext(); });
    }

    // the drill's result: ok, points, the line said (and the measures written with it)
    (bool ok, int pts, string detail) CfResult()
    {
        if (drill == null) return (false, 0, "");
        if (CfSpray)
        {
            var n = spLog.Count;
            var clean = spLog.Where(x => x.outcome == "clean").ToList();
            var ok = n > 0 && clean.Count * 5 >= n * 3;   // 3 clean of 5
            var pts = clean.Count * 80 + (ok ? 100 : 0);
            var why = spLog.Where(x => x.outcome != "clean").GroupBy(x => x.outcome)
                .Select(g => $"{T(g.Key switch { "released" => N("let go"), "out of ammo" => N("out of ammo"), _ => N("too slow") })} ×{g.Count()}");
            drillExtra["sprays"] = spLog.Select(x => new Dictionary<string, object> { ["outcome"] = x.outcome, ["bullets"] = x.bullets, ["transfer"] = Math.Round(x.transfer, 2) }).ToList();
            var detail = F("{a}/{b} clean sprays", "a", clean.Count, "b", n)
                         + (clean.Count > 0 ? $" · {F("{n} bullets on average", "n", Math.Round(clean.Average(x => x.bullets)))}" : "")
                         + string.Concat(why.Select(w => $" · {w}"));
            return (ok, pts, detail);
        }
        var duels = cfWon + cfLost;
        var won = duels > 0 && cfWon * 3 >= duels * 2;   // 2 of 3 (4 of 6)
        var offs = cfLog.Where(x => x.off >= 0).Select(x => x.off).ToList();
        var ttks = cfLog.Where(x => x.won && x.ttk >= 0).Select(x => x.ttk).ToList();
        var points = Math.Max(0, cfWon * 40 + cfHs * 15 - cfLost * 10 + 10 * offs.Count(o => o <= 5)) + (won ? 100 : 0);
        drillExtra["duels"] = cfLog.Select(x => new Dictionary<string, object> { ["won"] = x.won, ["off"] = Math.Round(x.off, 1), ["ttk"] = Math.Round(x.ttk, 2) }).ToList();
        drillExtra["shots"] = cfShots;
        drillExtra["moving_shots"] = cfMoving;
        var text = F("{a}/{b} duels won", "a", cfWon, "b", duels) + $" · {cfHs} HS"
                   + (offs.Count > 0 ? $" · {F("crosshair {a}° from their heads when they came", "a", Math.Round(offs.Average()))}" : "")
                   + (ttks.Count > 0 ? $" · {F("{s} s to kill", "s", ttks.Average().ToString("F2", CultureInfo.InvariantCulture))}" : "")
                   + (drill.Variant == "peek" && cfShots > 0 ? $" · {F("{p}% of your shots while moving", "p", 100 * cfMoving / cfShots)}" : "")
                   + (cfNone > 0 ? $" · {Tn(cfNone, "{n} without a duel", "{n} without a duel")}" : "");
        return (won, points, text);
    }
}
