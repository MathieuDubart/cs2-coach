"""Download (and keep) the demos of the cached match list, 3 at a time."""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from coach import CACHE, decompress, download


def get(m):
    dem = os.path.join(CACHE, f"{m['match_id']}.dem")
    if os.path.exists(dem):
        return f"{m['match_id']} already there"
    bz = dem + ".bz2"
    download(m["url"], bz)
    decompress(bz, dem)
    os.remove(bz)
    return f"{m['match_id']} OK"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ms = [m for m in json.load(open(os.path.join(CACHE, "matchlist.json"))) if m.get("url")]
    with ThreadPoolExecutor(3) as ex:
        for f in [ex.submit(get, m) for m in ms]:
            try:
                print(f.result(), flush=True)
            except Exception as e:
                print("ERROR", e, flush=True)
    print("FINI", flush=True)
