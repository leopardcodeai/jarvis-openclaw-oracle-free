PLUGIN_NAME = "currency_converter"
PLUGIN_DESCRIPTION = "Convert between currencies with live exchange rates (EUR, USD, GBP, CHF, JPY, BTC, ETH and 150+ more)"

async def run(query: str) -> str:
    import re, httpx

    q = query.upper().strip()

    # Parse: "100 USD in EUR" or "100 USD EUR"
    match = re.search(r'([\d.,]+)\s*([A-Z]{2,4})\s+(?:IN|TO|NACH|ZU|→|->)?\s*([A-Z]{2,4})', q)
    if not match:
        return ("❓ Format: `100 USD in EUR`\n"
                "Unterstützt: EUR, USD, GBP, CHF, JPY, BTC, ETH, CNY, AUD, CAD und 150+ mehr")

    amount = float(match.group(1).replace(',', '.'))
    from_cur = match.group(2)
    to_cur   = match.group(3)

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"https://api.frankfurter.app/latest?from={from_cur}&to={to_cur}"
            )
        if resp.status_code != 200:
            return f"❌ API Fehler {resp.status_code} – Währung nicht gefunden?"
        data = resp.json()
        rate = data["rates"].get(to_cur)
        if not rate:
            return f"❌ Kurs für `{to_cur}` nicht verfügbar."
        converted = amount * rate
        date = data.get("date", "?")
        return (
            f"💱 **Währungsrechner**\n\n"
            f"{amount:,.2f} **{from_cur}** = **{converted:,.4f} {to_cur}**\n\n"
            f"📈 Kurs: 1 {from_cur} = {rate:.6g} {to_cur}\n"
            f"📅 Stand: {date}"
        )
    except Exception as e:
        return f"❌ Fehler: {e}"
