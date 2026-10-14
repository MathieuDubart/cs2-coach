"""Wily's launcher: python serve.py (the app at http://127.0.0.1:8765; --no-browser starts it without opening it).

The app is the package wily/ (its web server: wily/app/serve.py). This file stays at the root for everything that starts
serve.py: the installer's shortcuts, Wily.bat, wily.sh, and the relaunch after an update by the version before it."""
import runpy

if __name__ == "__main__":
    runpy.run_module("wily.app.serve", run_name="__main__", alter_sys=True)
