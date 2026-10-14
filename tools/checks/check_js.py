"""The built page's scripts parse (node --check), or this exits with an error: run before copying
app_template_next.html over app_template.html (the server reads the page on each request)."""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
page = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "templates", "app_template_next.html")
html = open(page, encoding="utf-8").read()
js = "\n;\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, re.S))
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
os.remove(f.name)
if r.returncode:
    sys.exit("JS does not parse:\n" + r.stderr[-1500:])
print("JS parses")
