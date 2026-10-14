// The training server in the player's language (13/10, the user: "traduis l'app en russe, pour toucher la population de
// l'est, pareil pour l'Amérique du Sud et l'Asie"). The app writes coach/ui.json when it builds a session or a situation:
// {"lang": "fr", "ui": {English sentence: its translation, or its plural forms}}. T() says a sentence in it, F() fills its
// {placeholders} after the translation (a language may move them), Tn() takes the form that fits a number; a sentence
// the file lacks stays English. N() marks a sentence of a table for tools/i18n_extract.py, said later with T().
// The drills' own texts (titles, tips, a situation's goal) come translated in the session and scenario files.
using System.Globalization;
using System.Text.Json;

namespace CoachReplay;

public partial class CoachReplay
{
    string uiLang = "en";
    Dictionary<string, JsonElement> ui = new();
    DateTime uiAt = DateTime.MinValue;

    // what coach/ui.json says, read again only when it changed; (null, null) when it did not or cannot be read. Safe off
    // the game's thread (it only reads)
    (string? lang, Dictionary<string, JsonElement>? map) ReadUi()
    {
        try
        {
            var f = System.IO.Path.Combine(Dir, "ui.json");
            if (!File.Exists(f)) return (null, null);
            var m = File.GetLastWriteTimeUtc(f);
            if (m == uiAt) return (null, null);
            using var doc = JsonDocument.Parse(File.ReadAllText(f));
            var lang = doc.RootElement.TryGetProperty("lang", out var l) && l.ValueKind == JsonValueKind.String ? l.GetString() : "en";
            var map = new Dictionary<string, JsonElement>();
            if (doc.RootElement.TryGetProperty("ui", out var u) && u.ValueKind == JsonValueKind.Object)
                foreach (var p in u.EnumerateObject()) map[p.Name] = p.Value.Clone();
            uiAt = m;
            return (lang ?? "en", map);
        }
        catch (Exception e) { Log("ui.json: {m}", e.Message); return (null, null); }
    }

    void UseUi((string? lang, Dictionary<string, JsonElement>? map) u)
    {
        if (u.lang == null || u.map == null) return;
        uiLang = u.lang;
        ui = u.map;
        Log("training server language: {l} ({n} sentences)", uiLang, ui.Count);
    }

    static string N(string en) => en;

    string T(string en)
    {
        if (!ui.TryGetValue(en, out var v)) return en;
        if (v.ValueKind == JsonValueKind.String) return v.GetString() is { Length: > 0 } s ? s : en;
        if (v.ValueKind == JsonValueKind.Object && v.TryGetProperty("other", out var o) && o.ValueKind == JsonValueKind.String) return o.GetString() ?? en;
        return en;
    }

    string F(string en, params object?[] kv) => Fill(T(en), kv);

    // the form of a sentence that fits n ({n} filled too): the file's forms, else English's
    string Tn(double n, string one, string other, params object?[] kv)
    {
        var all = new object?[kv.Length + 2];
        all[0] = "n"; all[1] = n;
        kv.CopyTo(all, 2);
        if (ui.TryGetValue(other, out var v))
        {
            if (v.ValueKind == JsonValueKind.String && v.GetString() is { Length: > 0 } s) return Fill(s, all);
            if (v.ValueKind == JsonValueKind.Object)
            {
                if (v.TryGetProperty(Plural(uiLang, n), out var f) && f.GetString() is { Length: > 0 } fs) return Fill(fs, all);
                if (v.TryGetProperty("other", out var o) && o.GetString() is { Length: > 0 } os) return Fill(os, all);
            }
        }
        return Fill(Plural("en", n) == "one" ? one : other, all);
    }

    // a number's plural form in a language, as Intl.PluralRules names it (the app's i18n.plural)
    static string Plural(string lang, double n)
    {
        if (n != Math.Floor(n)) return "other";
        var i = (long)Math.Abs(n);
        return lang switch
        {
            "ru" => i % 10 == 1 && i % 100 != 11 ? "one" : i % 10 >= 2 && i % 10 <= 4 && !(i % 100 >= 12 && i % 100 <= 14) ? "few" : "many",
            "fr" or "pt" => i is 0 or 1 ? "one" : "other",
            "zh" => "other",
            _ => i == 1 ? "one" : "other",
        };
    }

    // {name} -> its value (names and values in turn); numbers as the game's culture-free text
    static string Fill(string s, object?[] kv)
    {
        for (int i = 0; i + 1 < kv.Length; i += 2)
        {
            var val = kv[i + 1] switch { null => "", IFormattable x => x.ToString(null, CultureInfo.InvariantCulture), var x => x.ToString() ?? "" };
            s = s.Replace("{" + kv[i] + "}", val);
        }
        return s;
    }

    // a grenade's throw as the app names it ("forward + jumpthrow + crouching"): its longest known parts, from the left
    string How(string how)
    {
        if (how == "" || ui.ContainsKey(how)) return T(how);
        var parts = how.Split(" + ");
        var said = new List<string>();
        for (int i = 0; i < parts.Length;)
        {
            var j = parts.Length;
            while (j > i + 1 && !ui.ContainsKey(string.Join(" + ", parts[i..j]))) j--;
            said.Add(T(string.Join(" + ", parts[i..j])));
            i = j;
        }
        return string.Join(" + ", said);
    }

    // the ways and clicks of the lineups, for the extractor (the app writes them in English: the plugin reads them)
    internal static readonly string[] HowWords = { N("standing still"), N("jumpthrow"), N("crouching"), N("running"), N("walking"), N("forward + jumpthrow"),
        N("run-throw (moving forward)"), N("left click"), N("right click"), N("left + right click") };
}
