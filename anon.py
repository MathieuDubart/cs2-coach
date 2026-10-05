"""Players made unrecognizable in the base's tables (05/10): every SteamID in a table becomes a made-up one in a range
no Steam account uses, every player name goes blank.

Two ways:
- Pseudo(key): a stable made-up id per player (HMAC-SHA256 with a key kept on the coach's PC): the packages of the
  base, where the same player keeps one id across matches (make_beta.py);
- Pseudo(): a random key for one match, never kept: the matches players share with the base (contrib.py), where
  nobody, not even the coach, can go back to the accounts.

fingerprint(): the same match shared by two players (or already in the base) is recognized by its rounds, not by its
Valve id, which a shared match no longer carries."""
import hashlib
import hmac
import os
import re
import secrets

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

LO, HI = 76561197960265728, 76561202255233023   # every Steam account (account ids up to 2^32)
FAKE_LO, FAKE_N = 76561190000000000, LO - 76561190000000000   # just below: no Steam account has one of these
NAME_COLS = {"name", "killer_name", "victim_name", "thrower_name", "attacker_name", "assister_name", "player_name"}
SID_RE = re.compile(r"(?<!\d)765611(?:979[6-9]|98\d\d|99\d\d|2[0-2]\d\d)\d{9}(?!\d)")


class Pseudo:
    """Real SteamID -> a made-up one, the same within this Pseudo's key."""
    def __init__(self, key=None):
        self.key = key or secrets.token_bytes(32)
        self.memo = {}

    @classmethod
    def from_file(cls, path):
        """The coach's key: created once, never leaves his PC (the same player keeps one id in every package)."""
        if not os.path.exists(path):
            open(path, "w").write(secrets.token_hex(32))
        return cls(bytes.fromhex(open(path).read().strip()))

    def __call__(self, sid):
        sid = int(sid)
        if sid not in self.memo:
            h = hmac.new(self.key, str(sid).encode(), hashlib.sha256).digest()
            self.memo[sid] = FAKE_LO + int.from_bytes(h[:8], "big") % FAKE_N
        return self.memo[sid]


def ids_column(col, pseudo, keep=None):
    """A column with SteamIDs in it, every one replaced (keep: a mask of rows left as they are). None when it has none."""
    t = col.type
    if pa.types.is_dictionary(t):
        raise ValueError(f"dictionary column {t}: not handled")   # none in the base (05/10); refused rather than missed
    if pa.types.is_integer(t) or pa.types.is_floating(t):
        null = col.is_null().to_numpy(zero_copy_only=False) if col.null_count else None
        v = (col.fill_null(0) if col.null_count else col).to_numpy(zero_copy_only=False)
        with np.errstate(invalid="ignore"):
            real = (v >= LO) & (v <= HI)
        if null is not None:
            real &= ~null
        if keep is not None:
            real &= ~keep
        if not real.any():
            return None
        new = v.copy()
        new[real] = np.array([pseudo(x) for x in v[real].astype(np.int64)], dtype=v.dtype)
        return pa.array(new, type=t, mask=null)
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        vals = col.to_pylist()
        out, hit = [], False
        for i, x in enumerate(vals):
            if x is not None and x.isdigit() and LO <= int(x) <= HI and not (keep is not None and keep[i]):
                out.append(str(pseudo(x)))
                hit = True
            else:
                out.append(x)
        return pa.array(out, type=t) if hit else None
    return None


def table(tb, pseudo, keep_match=None, replace=None):
    """One table: SteamIDs made up, names blank. keep_match: the match ids whose rows stay real (a player's own
    matches in a table of every match). replace: {old value: new value} for whole cells (a shared match's Valve id)."""
    keep = None
    if keep_match and "match" in tb.column_names:
        keep = np.isin(np.array([str(x) for x in tb.column("match").to_pylist()]), list(keep_match))
    cols = []
    for name in tb.column_names:
        col = tb.column(name).combine_chunks()
        if replace and (pa.types.is_string(col.type) or pa.types.is_integer(col.type)):
            vals = col.to_pylist()
            if any(str(x) in replace for x in vals if x is not None):
                col = pa.array([type(x)(replace[str(x)]) if x is not None and str(x) in replace else x for x in vals], type=col.type)
        if name in NAME_COLS:
            v = col.to_pylist()
            new = pa.array([x if (keep is not None and keep[i]) or x is None else "" for i, x in enumerate(v)], type=col.type)
        else:
            new = ids_column(col, pseudo, keep)
        cols.append(new if new is not None else col)
    return pa.Table.from_arrays(cols, schema=tb.schema)


def pseudonymize(src, dst, pseudo, keep_match=None, replace=None):
    tb = table(pq.read_table(src), pseudo, keep_match, replace)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    pq.write_table(tb, dst)


def leftovers(tb, keep=None):
    """Real SteamIDs or names left in a table (outside the rows kept): [] when it is clean."""
    bad = []
    for c in tb.column_names:
        if c in NAME_COLS:
            if any(x for i, x in enumerate(tb.column(c).to_pylist()) if keep is None or not keep[i]):
                bad.append(f"names in {c}")
        elif ids_column(tb.column(c).combine_chunks(), lambda x: 0, keep) is not None:
            bad.append(f"SteamIDs in {c}")
    return bad


def fingerprint(deep_dir):
    """One match, whoever shared it: its map and the ticks and winners of its rounds."""
    import json
    try:
        mp = json.load(open(os.path.join(deep_dir, "meta.json"), encoding="utf-8")).get("map")
        R = pq.read_table(os.path.join(deep_dir, "rounds.parquet")).to_pandas()
    except (OSError, ValueError):
        return None
    cols = [c for c in ("round", "start_tick", "end_tick", "winner") if c in R.columns]
    if len(cols) < 3 or not len(R):
        return None
    key = f"{mp}|" + "|".join(",".join(str(v) for v in row) for row in R[cols].itertuples(index=False))
    return hashlib.sha256(key.encode()).hexdigest()[:32]
