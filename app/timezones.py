"""Which country a time zone belongs to, read from the system's tz tables."""
import os

ZONEINFO = "/usr/share/zoneinfo"

_zones = None

def _load():
    zones, links = {}, {}
    try:
        with open(os.path.join(ZONEINFO, "zone.tab"), encoding="utf-8") as handle:
            for line in handle:
                parts = line.split("\t")
                if len(parts) >= 3 and not line.startswith("#"):
                    zones[parts[2].strip()] = parts[0].strip()
        with open(os.path.join(ZONEINFO, "tzdata.zi"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("L "):
                    parts = line.split()
                    if len(parts) == 3:
                        links[parts[2]] = parts[1]
    except OSError:
        return {}
    for old, new in links.items():
        if old not in zones and new in zones:
            zones[old] = zones[new]
    return zones

def country_for(zone):
    global _zones
    if _zones is None:
        _zones = _load()
    code = _zones.get((zone or "").strip()[:64])
    return code if code and len(code) == 2 and code.isalpha() else None
