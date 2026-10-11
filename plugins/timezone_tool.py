PLUGIN_NAME = "timezone_tool"
PLUGIN_DESCRIPTION = "Convert times between world timezones; show current time in any city or timezone"

async def run(query: str) -> str:
    import re
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    CITY_TZ = {
        "berlin": "Europe/Berlin", "munich": "Europe/Berlin", "münchen": "Europe/Berlin",
        "hamburg": "Europe/Berlin", "frankfurt": "Europe/Berlin", "vienna": "Europe/Vienna",
        "wien": "Europe/Vienna", "zurich": "Europe/Zurich", "zürich": "Europe/Zurich",
        "london": "Europe/London", "paris": "Europe/Paris", "madrid": "Europe/Madrid",
        "rome": "Europe/Rome", "amsterdam": "Europe/Amsterdam", "brussels": "Europe/Brussels",
        "new york": "America/New_York", "nyc": "America/New_York", "boston": "America/New_York",
        "chicago": "America/Chicago", "denver": "America/Denver",
        "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
        "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
        "toronto": "America/Toronto", "vancouver": "America/Vancouver",
        "tokyo": "Asia/Tokyo", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
        "hong kong": "Asia/Hong_Kong", "singapore": "Asia/Singapore",
        "dubai": "Asia/Dubai", "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata",
        "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
        "auckland": "Pacific/Auckland", "moscow": "Europe/Moscow",
        "istanbul": "Europe/Istanbul", "cairo": "Africa/Cairo",
        "utc": "UTC", "gmt": "GMT",
    }

    q = query.lower().strip()
    now = datetime.now(ZoneInfo("UTC"))

    # Find time in query
    time_match = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?', q)
    # Find "from" timezone
    from_tz_name = "Europe/Berlin"
    to_tz_name   = "UTC"

    # Find cities/timezones in query
    found_tzs = []
    for city, tz in CITY_TZ.items():
        if city in q:
            found_tzs.append(tz)

    # Also match raw timezone names like "America/New_York"
    raw_tz = re.findall(r'[A-Z][a-z]+/[A-Z][a-z_]+', query)
    found_tzs.extend(raw_tz)
    found_tzs = list(dict.fromkeys(found_tzs))

    if time_match and len(found_tzs) >= 2:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        s = int(time_match.group(3) or 0)
        ap = time_match.group(4)
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0

        from_tz = ZoneInfo(found_tzs[0])
        dt = now.replace(hour=h, minute=m, second=s).astimezone(from_tz)
        lines = [f"⏰ **Zeitkonvertierung** von `{found_tzs[0]}`:\n"]
        lines.append(f"`{dt.strftime('%H:%M')}` in `{found_tzs[0]}`")
        for tz_name in found_tzs[1:]:
            try:
                converted = dt.astimezone(ZoneInfo(tz_name))
                lines.append(f"→ `{converted.strftime('%H:%M')}` in `{tz_name}`")
            except ZoneInfoNotFoundError:
                pass
        return "\n".join(lines)

    # Just show current time in found timezones (or default set)
    tz_list = found_tzs or [
        "Europe/Berlin", "Europe/London", "America/New_York",
        "America/Los_Angeles", "Asia/Tokyo", "Asia/Singapore", "UTC"
    ]
    lines = [f"🌍 **Aktuelle Weltzeit:**\n"]
    for tz_name in tz_list[:8]:
        try:
            dt = now.astimezone(ZoneInfo(tz_name))
            city = next((c.title() for c, t in CITY_TZ.items() if t == tz_name), tz_name)
            lines.append(f"🕐 `{dt.strftime('%H:%M')}` — {city} ({tz_name})")
        except ZoneInfoNotFoundError:
            pass
    return "\n".join(lines)
