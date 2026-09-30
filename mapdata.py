"""Radar configuration per map: coordinates, levels and radar images."""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(HERE, "maps")
RADAR_URL = "https://raw.githubusercontent.com/akiver/cs-demo-manager/main/static/images/maps/cs2/radars/{}.png"


def _download(name):
    path = os.path.join(MAPS, f"{name}.png")
    if not os.path.exists(path):
        try:
            urllib.request.urlretrieve(RADAR_URL.format(name), path)
        except Exception:
            return None
    return f"maps/{name}.png"


def get(map_name):
    path = os.path.join(MAPS, f"{map_name}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        with open(os.path.join(MAPS, "overviews.json"), encoding="utf-8") as f:
            ov = json.load(f).get(map_name)
        if not ov:
            # maps missing from the local install: coordinates published by CS Demo Manager
            with open(os.path.join(MAPS, "csdm_maps.json"), encoding="utf-8") as f:
                cs = json.load(f).get(map_name)
            if not cs:
                raise KeyError(f"no radar data for {map_name}")
            ov = {**cs, "split": []}
            if cs["threshold_z"]:
                t = cs["threshold_z"]
                ov["split"] = [20000, t, t, -10000]
        cfg = {"pos_x": float(ov["pos_x"]), "pos_y": float(ov["pos_y"]), "scale": float(ov["scale"])}
        split = [float(x) for x in ov.get("split", [])]
        if len(split) == 4:  # default max/min, lower max/min
            z = split[1]
            cfg["levels"] = [{"key": "upper", "name": "Main level", "image": _download(map_name), "z_min": z},
                             {"key": "lower", "name": "Lower level", "image": _download(f"{map_name}_lower"), "z_max": z}]
        else:
            cfg["levels"] = [{"key": "main", "name": "Map", "image": _download(map_name)}]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    for lv in cfg["levels"]:
        if lv.get("image") and not os.path.isabs(lv["image"]):
            lv["image_path"] = os.path.join(HERE, lv["image"])
            if not os.path.exists(lv["image_path"]):  # radars are not versioned: download on first use
                _download(os.path.splitext(os.path.basename(lv["image"]))[0])
    # all radar pixel coordinates are expressed on a 1024px image
    cfg.setdefault("px_factor", 1.0)
    first = cfg["levels"][0].get("image_path")
    if first and os.path.exists(first):
        from PIL import Image
        cfg["px_factor"] = 1024 / Image.open(first).size[0]
    return cfg


def level_of(cfg, z):
    for lv in cfg["levels"]:
        if "z_min" in lv and z < lv["z_min"]:
            continue
        if "z_max" in lv and z >= lv["z_max"]:
            continue
        return lv["key"]
    return cfg["levels"][0]["key"]
