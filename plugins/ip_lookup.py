PLUGIN_NAME = "ip_lookup"
PLUGIN_DESCRIPTION = "Look up IP address geolocation, ISP, country, city, timezone (uses ipinfo.io free API)"

async def run(query: str) -> str:
    import re, httpx

    q = query.strip()
    ip_match = re.search(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b', q)

    url = f"https://ipinfo.io/{ip_match.group(1) if ip_match else ''}/json"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return f"❌ API-Fehler {resp.status_code}"
        d = resp.json()

        if "error" in d:
            return f"❌ {d['error'].get('message', 'Unbekannte IP')}"

        loc = d.get("loc", "?").split(",")
        lat, lon = (loc[0], loc[1]) if len(loc) == 2 else ("?", "?")
        maps_url = f"https://maps.google.com/?q={lat},{lon}" if lat != "?" else ""

        return (
            f"🌍 **IP: `{d.get('ip', '?')}`**\n\n"
            f"🏳 Land:      {d.get('country', '?')}\n"
            f"🏙 Stadt:     {d.get('city', '?')}, {d.get('region', '?')}\n"
            f"📮 ZIP:       {d.get('postal', '?')}\n"
            f"🏢 ISP/Org:  {d.get('org', '?')}\n"
            f"⏰ Timezone: {d.get('timezone', '?')}\n"
            f"📍 Koordinaten: {lat}, {lon}\n"
            + (f"🗺 Maps: {maps_url}" if maps_url else "")
        )
    except Exception as e:
        return f"❌ Fehler: {e}"
