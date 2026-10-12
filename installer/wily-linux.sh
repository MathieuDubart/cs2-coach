#!/bin/sh
# Wily for Linux (10/10): installs the app into ~/.local/share/wily (no root) from the same release as Windows: the
# code and the base, checked against the release's signature, and a Python environment of its own (venv) with the
# libraries the code asks for. Run it again to repair or update the install. Usage: sh wily-linux.sh
# Works on Linux: the match review and Live (second screen). Not yet: the training server.
set -e
RELEASES="${WILY_RELEASES:-https://wily.valentingassend.com/releases/}"
DEST="${WILY_HOME:-$HOME/.local/share/wily}"
PUBKEY="@@PUBKEY@@"

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY=$(command -v "$c"); break
  fi
done
if [ -z "$PY" ]; then
  echo "Wily needs Python 3.11 or newer. Debian/Ubuntu: sudo apt install python3 python3-venv ; Fedora: sudo dnf install python3 ; Arch: sudo pacman -S python"
  exit 1
fi
if ! "$PY" -c 'import venv, ensurepip' 2>/dev/null; then
  echo "Python's venv module is missing. Debian/Ubuntu: sudo apt install python3-venv"
  exit 1
fi

mkdir -p "$DEST/out"
cd "$DEST"
echo "Wily: Python environment ($("$PY" --version))..."
[ -x venv/bin/python ] || "$PY" -m venv venv
venv/bin/python -m pip install -q --upgrade pip
venv/bin/python -m pip install -q cryptography

echo "Wily: downloading the release (about 500 MB the first time)..."
venv/bin/python - "$RELEASES" "$PUBKEY" <<'PYEOF'
import base64, hashlib, io, json, os, sys, urllib.request, zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
url, pub = sys.argv[1], sys.argv[2]
get = lambda name: urllib.request.urlopen(urllib.request.Request(url + name, headers={"User-Agent": "Wily-linux-installer"}), timeout=120).read()
raw, sig = get("latest.json"), get("latest.json.sig").decode().strip()
Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub)).verify(base64.b64decode(sig), raw)   # raises if not signed by the coach
man = json.loads(raw)
have = {}
try:
    have = json.load(open("VERSION.json"))
except (OSError, ValueError):
    pass
base_have = ""
try:
    base_have = json.load(open(os.path.join("out", "base_pack.json"))).get("version") or ""
except (OSError, ValueError):
    pass

def fetch(part):
    e = man[part]
    data = get(e["file"])
    if hashlib.sha256(data).hexdigest() != e["sha256"]:
        sys.exit(f"{e['file']}: damaged download, run the installer again")
    return zipfile.ZipFile(io.BytesIO(data))

def extract(z, dest, code=False):
    root = os.path.realpath(dest)
    for n in z.namelist():   # never outside the folder; the code never over out/, python/ or cache/
        p = os.path.realpath(os.path.join(root, n))
        if (p != root and not p.startswith(root + os.sep)) or (code and n.replace("\\", "/").split("/")[0] in ("out", "python", "cache")):
            sys.exit(f"refused: {n}")
    z.extractall(dest)

if have.get("build") != (man["code"].get("build") or man["app"]):
    print("  code", man["app"], man["code"].get("build", ""))
    extract(fetch("code"), ".", code=True)
if not base_have:   # a first install only: later, the app updates its base itself and keeps the player's own files
    print("  base", man["base"].get("version"), f"({man['base'].get('matches')} matches)")
    extract(fetch("base"), "out")
print("  release", man["app"], "checked and installed")
PYEOF

echo "Wily: libraries..."
venv/bin/python -m pip install -q -r requirements.txt
[ -f out/settings.json ] || printf '{"role": "client"}\n' > out/settings.json
chmod +x wily.sh

mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/wily.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Wily
Comment=Wily, your CS2 coach
Exec=sh "$DEST/wily.sh"
Icon=$DEST/wily.png
Terminal=false
Categories=Game;
EOF

MIC=$(venv/bin/python -c 'import voice; ok, why = voice.available(); print("" if ok else why)' 2>/dev/null || true)
if [ -n "$MIC" ]; then   # the app itself says which sound library it found, so this note can never drift from the code
  echo "Note: $MIC"
  echo "      Everything else works without it: only your calls would be missing."
fi
# The coach's voice at the buy time is spoken by your browser, which on Linux speaks through speech-dispatcher with a
# synthesiser behind it. Those are system packages: this installer asks for no root, so it names them instead (10/10,
# a Linux tester went looking for an hour). Everything else works without them.
miss=""
command -v speech-dispatcher >/dev/null 2>&1 || miss="speech-dispatcher"
command -v espeak-ng >/dev/null 2>&1 || miss="${miss:+$miss }espeak-ng"
if [ -n "$miss" ]; then
  echo "Note: the coach's voice needs $miss. Debian/Ubuntu: sudo apt install speech-dispatcher espeak-ng ; Fedora: sudo dnf install speech-dispatcher espeak-ng ; Arch: sudo pacman -S speech-dispatcher espeak-ng"
elif command -v systemctl >/dev/null 2>&1 && ! systemctl --user is-enabled speech-dispatcher.socket >/dev/null 2>&1; then
  # a browser in a sandbox cannot start the service itself, it can only connect to a socket already there
  echo "Note: for the coach's voice, let the speech service start on demand: systemctl --user enable --now speech-dispatcher.socket"
  echo "      A browser installed as a Flatpak or a Snap also needs the socket opened to it, for example:"
  echo "      flatpak override --user --filesystem=xdg-run/speech-dispatcher <its application id>"
fi
echo "Wily is installed in $DEST. Start it from your applications menu (Wily) or with: sh \"$DEST/wily.sh\""
echo "Then in CS2: the app installs its Game State Integration file for Live from its Settings page."
