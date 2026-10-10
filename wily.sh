#!/bin/sh
# Wily on Linux: starts the app from its folder with its own Python (venv made by wily-linux.sh).
# The page opens in your browser at http://127.0.0.1:8765/ ; "--no-browser" starts it without opening it.
cd "$(dirname "$0")" || exit 1
if [ ! -x venv/bin/python ]; then
  echo "Wily: its Python environment is missing. Run wily-linux.sh again to repair the install."
  exit 1
fi
PYTHONNOUSERSITE=1 exec venv/bin/python -s serve.py "$@"
