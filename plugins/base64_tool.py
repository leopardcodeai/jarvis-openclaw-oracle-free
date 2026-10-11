PLUGIN_NAME = "base64_tool"
PLUGIN_DESCRIPTION = "Encode text to Base64 or decode Base64 back to text; also handles URL-safe base64"

async def run(query: str) -> str:
    import base64, re

    q = query.strip()
    q_lower = q.lower()

    decode = any(w in q_lower for w in ["decode", "dekodier", "entschlüssel", "decodier"])

    # Extract the actual content (strip command words)
    content = re.sub(
        r'\b(base64|encode|decode|kodier|dekodier|entschlüssel|decodier|encodier|url.safe|urlsafe)\b',
        '', q, flags=re.I
    ).strip()

    if not content:
        return "❓ Format: `base64 encode <text>` oder `base64 decode <base64string>`"

    url_safe = "url" in q_lower or "urlsafe" in q_lower

    try:
        if decode:
            # Try standard then url-safe
            try:
                result = base64.b64decode(content + '==').decode('utf-8')
            except Exception:
                result = base64.urlsafe_b64decode(content + '==').decode('utf-8')
            return f"🔓 **Base64 Decoded:**\n`{result}`"
        else:
            if url_safe:
                encoded = base64.urlsafe_b64encode(content.encode()).decode()
            else:
                encoded = base64.b64encode(content.encode()).decode()
            return (f"🔒 **Base64 Encoded{' (URL-safe)' if url_safe else ''}:**\n"
                    f"`{encoded}`\n\n"
                    f"Original: `{content[:80]}`\n"
                    f"Länge: {len(content)} → {len(encoded)} Zeichen")
    except Exception as e:
        return f"❌ Fehler: {e}"
