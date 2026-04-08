PLUGIN_NAME = "timestamp_tool"
PLUGIN_DESCRIPTION = "Convert Unix timestamps to human-readable dates, or dates to Unix timestamps; calculate time differences"

async def run(query: str) -> str:
    import re
    from datetime import datetime, timezone, timedelta

    q = query.strip()
    q_lower = q.lower()

    # Current timestamp
    if any(w in q_lower for w in ["jetzt", "now", "aktuell", "current"]):
        now = datetime.now(timezone.utc)
        return (f"🕐 **Aktuell:**\n"
                f"Unix:    `{int(now.timestamp())}`\n"
                f"UTC:     `{now.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
                f"Berlin:  `{(now + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S CET')}`\n"
                f"ISO8601: `{now.isoformat()}`")

    # Unix → datetime
    ts_match = re.search(r'\b(\d{9,13})\b', q)
    if ts_match:
        ts = int(ts_match.group(1))
        if ts > 1e12: ts //= 1000  # milliseconds
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        berlin = dt + timedelta(hours=2)
        return (f"📅 **Timestamp `{ts}`:**\n"
                f"UTC:    `{dt.strftime('%A, %d.%m.%Y %H:%M:%S UTC')}`\n"
                f"Berlin: `{berlin.strftime('%A, %d.%m.%Y %H:%M:%S')}`\n"
                f"Vor:    `{_relative(dt)}`")

    # Date → Unix
    date_match = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', q)
    if date_match:
        d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        dt = datetime(y, m, d, tzinfo=timezone.utc)
        return (f"🔢 **{d:02d}.{m:02d}.{y} → Unix:**\n"
                f"`{int(dt.timestamp())}`\n"
                f"Wochentag: `{dt.strftime('%A')}`")

    return ("❓ Format:\n"
            "• `timestamp now` – aktueller Timestamp\n"
            "• `timestamp 1700000000` – Unix zu Datum\n"
            "• `timestamp 25.12.2024` – Datum zu Unix")

def _relative(dt):
    from datetime import datetime, timezone
    diff = datetime.now(timezone.utc) - dt
    s = int(diff.total_seconds())
    if s < 0: return f"in {_relative_future(-s)}"
    if s < 60: return f"vor {s}s"
    if s < 3600: return f"vor {s//60}min"
    if s < 86400: return f"vor {s//3600}h"
    return f"vor {s//86400} Tagen"

def _relative_future(s):
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}min"
    if s < 86400: return f"{s//3600}h"
    return f"{s//86400} Tagen"
