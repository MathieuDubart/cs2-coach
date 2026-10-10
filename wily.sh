#!/bin/sh
# Wily on Linux: starts the app from its folder with its own Python (venv made by wily-linux.sh).
# The page opens in your browser at http://127.0.0.1:8765/ ; "--no-browser" starts it without opening it.
# Its output goes to cache/serve.log (what a bug report sends); "--console" keeps it in this terminal instead.
cd "$(dirname "$0")" || exit 1
if [ ! -x venv/bin/python ]; then
  echo "Wily: its Python environment is missing. Run wily-linux.sh again to repair the install."
  exit 1
fi
export PYTHONNOUSERSITE=1
if [ "$1" = "--console" ]; then
  shift
  exec venv/bin/python -s serve.py "$@"
fi
mkdir -p cache
exec venv/bin/python -s serve.py "$@" >> cache/serve.log 2>&1
