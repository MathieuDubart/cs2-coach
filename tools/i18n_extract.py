"""Every sentence of the app a player can read, from the code (13/10): tl() / tln() / tlv() / tlvn() in ui/*.js,
data-t in ui/p2_shell.html, tr() / trn() / N_() in the Python modules, T() / F() / N() / Tn() in the training server's
plugin (plugin/CoachReplay/*.cs). Writes i18n/_source.json ({English: {where, voice, one}}) and
says, for each catalog, what is missing, what is no longer used, and the translations whose {placeholders} or HTML
tags differ from the English (a moved tag is fine, a lost one is not).

    python tools/i18n_extract.py            the report
    python tools/i18n_extract.py --strict   exit code 1 when a catalog has a broken entry (missing ones are fine)"""
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from wily.core import i18n  # noqa: E402

SKIP_PY = re.compile(r"^(test_|farm_|fix_|patch|scratch|inject_|process_|save_html|update_review)")
CALL = re.compile(r"(?<![\w$.])(tl|tln|tlv|tlvn)\(\s*")
STR = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\$]|\\.|\$(?!\{))*`')


def js_unquote(lit):
    """A JavaScript string literal (no ${} in a template) -> its text."""
    body, out, i = lit[1:-1], [], 0
    esc = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = body[i + 1]
        if n == "u" and body[i + 2] == "{":
            j = body.index("}", i)
            out.append(chr(int(body[i + 3:j], 16)))
            i = j + 1
        elif n == "u":
            out.append(chr(int(body[i + 2:i + 6], 16)))
            i += 6
        elif n == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
        elif n == "\n":
            i += 2
        else:
            out.append(esc.get(n, n))
            i += 2
    return "".join(out)


def js_args(src, pos, count):
    """Up to `count` string literal arguments from pos (after "t("): the first one that is not a literal ends it."""
    args = []
    while len(args) < count:
        m = STR.match(src, pos)
        if not m:
            break
        args.append(js_unquote(m.group(0)))
        pos = m.end()
        m2 = re.compile(r"\s*,\s*").match(src, pos)
        if not m2:
            break
        pos = m2.end()
    return args


def norm_html(s):
    return re.sub(r"\s+", " ", s).strip()


def scan_js(found):
    ui = os.path.join(HERE, "ui")
    for f in sorted(os.listdir(ui)):
        if not f.endswith(".js"):
            continue
        src = open(os.path.join(ui, f), encoding="utf-8").read()
        for m in CALL.finditer(src):
            fn, line = m.group(1), src.count("\n", 0, m.start()) + 1
            if fn in ("tln", "tlvn"):   # tln(n, one, other, p): skip the first argument (an expression)
                depth, i = 0, m.end()
                while i < len(src):
                    c = src[i]
                    if c in "([{":
                        depth += 1
                    elif c in ")]}":
                        if depth == 0:
                            break
                        depth -= 1
                    elif c == "," and depth == 0:
                        break
                    i += 1
                a = js_args(src, i + 1 + len(re.match(r"\s*", src[i + 1:]).group(0)), 2)
                if len(a) == 2:
                    add(found, a[1], f"{f}:{line}", one=a[0], voice=fn == "tlvn")
            else:
                a = js_args(src, m.end(), 1)
                if a:
                    add(found, a[0], f"{f}:{line}", voice=fn == "tlv")
    shell = open(os.path.join(ui, "p2_shell.html"), encoding="utf-8").read()
    for m in re.finditer(r"<(\w+)([^>]*)\sdata-t(?![-\w])(?:=\"\")?([^>]*)>([\s\S]*?)</\1>", shell):
        add(found, norm_html(m.group(4)), f"p2_shell.html:{shell.count(chr(10), 0, m.start()) + 1}")
    for m in re.finditer(r"data-t-(placeholder|title|aria-label)\b[^>]*?\s\1=\"([^\"]+)\"|\s(placeholder|title|aria-label)=\"([^\"]+)\"[^>]*?data-t-\3\b", shell):
        add(found, m.group(2) or m.group(4), f"p2_shell.html:{shell.count(chr(10), 0, m.start()) + 1}")


def py_files():
    """The app's modules (wily/) and the website's: their paths from the root, with forward slashes."""
    out = []
    for top in ("wily", "website"):
        for r, ds, fs in os.walk(os.path.join(HERE, top)):
            ds[:] = sorted(d for d in ds if d != "__pycache__")
            out += [os.path.relpath(os.path.join(r, f), HERE).replace(os.sep, "/") for f in sorted(fs) if f.endswith(".py") and not SKIP_PY.match(f)]
    return out


def scan_py(found):
    for f in py_files():
        try:
            tree = ast.parse(open(os.path.join(HERE, f), encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
            consts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if name == "tr" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                add(found, node.args[0].value, f"{f}:{node.lineno}")
            elif name == "trn" and len(consts) >= 2:
                add(found, consts[1], f"{f}:{node.lineno}", one=consts[0])
            elif name == "N_" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                add(found, node.args[0].value, f"{f}:{node.lineno}", static=True)


CS_CALL = re.compile(r"(?<![\w.])(T|F|N|Tn)\(\s*")
CS_STR = re.compile(r'"(?:[^"\\\n]|\\.)*"')


def scan_cs(found):
    """The training server's plugin (plugin/CoachReplay/*.cs): T("…"), F("…", …), N("…") and Tn(n, "one", "other");
    its sentences go to coach/ui.json (i18n.plugin_catalog)."""
    d = os.path.join(HERE, "plugin", "CoachReplay")
    for f in sorted(os.listdir(d)):
        if not f.endswith(".cs"):
            continue
        src = open(os.path.join(d, f), encoding="utf-8").read()
        for m in CS_CALL.finditer(src):
            fn, line, pos = m.group(1), src.count("\n", 0, m.start()) + 1, m.end()
            if fn == "Tn":   # skip the number (an expression) up to its comma
                depth = 0
                while pos < len(src):
                    c = src[pos]
                    if c in "([{":
                        depth += 1
                    elif c in ")]}":
                        if depth == 0:
                            break
                        depth -= 1
                    elif c == "," and depth == 0:
                        break
                    pos += 1
                pos = re.compile(r",\s*").match(src, pos).end() if src[pos:pos + 1] == "," else pos
            args = []
            while len(args) < (2 if fn == "Tn" else 1):
                s = CS_STR.match(src, pos)
                if not s:
                    break
                args.append(js_unquote(s.group(0)))
                m2 = re.compile(r"\s*,\s*").match(src, s.end())
                if not m2:
                    break
                pos = m2.end()
            if fn == "Tn" and len(args) == 2:
                add(found, args[1], f"cs/{f}:{line}", one=args[0])
            elif fn != "Tn" and args:
                add(found, args[0], f"cs/{f}:{line}")


def add(found, key, where, voice=False, one=None, static=False):
    if not key.strip():
        return
    e = found.setdefault(key, {"where": []})
    if where not in e["where"]:
        e["where"].append(where)
    if voice:
        e["voice"] = True
    if one is not None:
        e["one"] = one
    if static:
        e["static"] = True


TAG = re.compile(r"</?([a-z][a-z0-9]*)\b")
PH = re.compile(r"\{(\w+)\}")


def problems(key, val):
    """What is wrong with one translation: placeholders or tags not the English ones."""
    out = []
    forms = val.values() if isinstance(val, dict) else [val]
    for v in forms:
        if not isinstance(v, str):
            out.append("not text")
            continue
        if set(PH.findall(v)) - set(PH.findall(key)) - {"n"}:
            out.append(f"unknown placeholder {sorted(set(PH.findall(v)) - set(PH.findall(key)))}")
        if set(PH.findall(key)) - set(PH.findall(v)) - {"n"}:
            out.append(f"placeholder lost {sorted(set(PH.findall(key)) - set(PH.findall(v)))}")
        if sorted(TAG.findall(v)) != sorted(TAG.findall(key)):
            out.append("tags differ")
    return out


def main():
    found = {}
    scan_js(found)
    scan_py(found)
    scan_cs(found)
    src = {k: found[k] for k in sorted(found)}
    os.makedirs(i18n.DIR, exist_ok=True)
    with open(os.path.join(i18n.DIR, "_source.json"), "w", encoding="utf-8") as f:
        json.dump(src, f, ensure_ascii=False, indent=1)
    words = sum(len(k.split()) for k in src)
    print(f"{len(src)} sentences ({words} words): {sum(1 for v in src.values() if v.get('voice'))} spoken, "
          f"{sum(1 for v in src.values() if 'one' in v)} with plurals")
    bad = 0
    for lang in i18n.LANGS:
        if lang == "en":
            continue
        p = os.path.join(i18n.DIR, f"{lang}.json")
        cat = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        cat = {k: v for k, v in cat.items() if not k.startswith("_")}
        miss = [k for k in src if not cat.get(k)]
        old = [k for k in cat if k not in src]
        broken = {k: problems(k, v) for k, v in cat.items() if k in src and v and problems(k, v)}
        bad += len(broken)
        print(f"{lang}: {len(src) - len(miss)}/{len(src)} translated · {len(old)} unused · {len(broken)} broken")
        for k, why in list(broken.items())[:8]:
            print(f"   broken: {k[:70]!r}: {', '.join(why)}")
    if "--strict" in sys.argv and bad:
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
