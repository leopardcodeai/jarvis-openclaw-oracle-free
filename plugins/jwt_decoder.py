PLUGIN_NAME = "jwt_decoder"
PLUGIN_DESCRIPTION = "Decode and inspect JWT tokens (header, payload, expiry) without verifying signature"

async def run(query: str) -> str:
    import base64, json, re
    from datetime import datetime, timezone

    # Extract JWT (3 parts separated by dots)
    token_match = re.search(r'(ey[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*)', query.strip())
    if not token_match:
        return "❓ Kein JWT-Token gefunden. Format: `jwt <token>`"

    token = token_match.group(1)
    parts = token.split('.')
    if len(parts) != 3:
        return "❌ Ungültiges JWT-Format (benötigt 3 Teile: header.payload.signature)"

    def decode_part(part):
        # Add padding
        padding = 4 - len(part) % 4
        part += '=' * (padding % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(part))
        except Exception as e:
            return {"error": str(e)}

    header  = decode_part(parts[0])
    payload = decode_part(parts[1])

    # Check expiry
    exp_info = ""
    if "exp" in payload:
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        if exp_dt < now:
            diff = now - exp_dt
            exp_info = f"\n⚠️ **ABGELAUFEN** seit {_fmt_diff(diff)}"
        else:
            diff = exp_dt - now
            exp_info = f"\n✅ Gültig noch: {_fmt_diff(diff)}"

    iat_info = ""
    if "iat" in payload:
        iat_dt = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        iat_info = f"\n🕐 Ausgestellt: {iat_dt.strftime('%Y-%m-%d %H:%M UTC')}"

    h_fmt = json.dumps(header, indent=2, ensure_ascii=False)
    p_fmt = json.dumps(payload, indent=2, ensure_ascii=False)

    return (
        f"🔑 **JWT Decoder**\n\n"
        f"**Header:**\n```json\n{h_fmt}\n```\n\n"
        f"**Payload:**\n```json\n{p_fmt[:1500]}\n```"
        + ("\n_(Payload gekürzt)_" if len(p_fmt) > 1500 else "")
        + exp_info + iat_info +
        f"\n\n⚠️ Signatur nicht verifiziert – nur Inspektion!"
    )

def _fmt_diff(diff):
    s = int(diff.total_seconds())
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}min"
    if s < 86400: return f"{s//3600}h {(s%3600)//60}min"
    return f"{s//86400}d {(s%86400)//3600}h"
