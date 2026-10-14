"""A player's public Steam profile (Steam's XML page, no key) and the names of CS2's Competitive ranks."""
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SKILL = ["", "Silver I", "Silver II", "Silver III", "Silver IV", "Silver Elite", "Silver Elite Master", "Gold Nova I",
         "Gold Nova II", "Gold Nova III", "Gold Nova Master", "Master Guardian I", "Master Guardian II",
         "Master Guardian Elite", "Distinguished Master Guardian", "Legendary Eagle", "Legendary Eagle Master",
         "Supreme Master First Class", "Global Elite"]


def steam_profile(steamid):
    """Public Steam profile (XML, no key)."""
    try:
        req = urllib.request.Request(f"https://steamcommunity.com/profiles/{steamid}/?xml=1", headers={"User-Agent": UA})
        x = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception:
        return None
    g = lambda tag: (re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", x, re.S) or [None, None])[1]
    return {"name": g("steamID"), "avatar": g("avatarFull"), "privacy": g("privacyState"), "vac_banned": g("vacBanned") == "1",
            "trade_ban": g("tradeBanState"), "member_since": g("memberSince"), "location": g("location"),
            "url": f"https://steamcommunity.com/profiles/{steamid}"}
