PLUGIN_NAME = "generate_qr_code"
PLUGIN_DESCRIPTION = "Generates a QR code image from any URL or text and returns it as a Telegram photo"

import base64
import io

async def run(query: str) -> dict:
    import qrcode
    img = qrcode.make(query)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"type": "photo", "bytes": buf.getvalue(), "caption": f"QR-Code: {query[:80]}"}