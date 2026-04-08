PLUGIN_NAME = "barcode_generator"
PLUGIN_DESCRIPTION = "Generate barcode images: EAN-13, Code128, Code39, ISBN, UPC from numbers or text"

import io

async def run(query: str) -> dict:
    import re

    q = query.strip()
    q_lower = q.lower()

    # Detect barcode type
    barcode_type = "code128"  # default, accepts any text
    if re.search(r'\bean.?13\b', q_lower): barcode_type = "ean13"
    elif re.search(r'\bean.?8\b', q_lower): barcode_type = "ean8"
    elif re.search(r'\bisbn\b', q_lower): barcode_type = "isbn13"
    elif re.search(r'\bupc\b', q_lower): barcode_type = "upca"
    elif re.search(r'\bcode.?39\b', q_lower): barcode_type = "code39"

    # Extract content
    content = re.sub(
        r'\b(barcode|generate|erstell|generier|ean\d*|code\d+|isbn|upc|für|for|von)\b',
        '', q, flags=re.I
    ).strip()
    if not content:
        content = q.strip()

    try:
        import barcode
        from barcode.writer import ImageWriter

        bc_class = barcode.get_barcode_class(barcode_type)
        buf = io.BytesIO()
        bc = bc_class(content, writer=ImageWriter())
        bc.write(buf)
        return {
            "type": "photo",
            "bytes": buf.getvalue(),
            "caption": f"📊 Barcode ({barcode_type.upper()}): {content}"
        }
    except ImportError:
        return {"type": "error", "message": "❌ `python-barcode` nicht installiert. Verwende `/install python-barcode[images]`"}
    except Exception as e:
        # Fallback: try code128 if specific type fails
        try:
            import barcode
            from barcode.writer import ImageWriter
            buf = io.BytesIO()
            bc = barcode.get('code128', content, writer=ImageWriter())
            bc.write(buf)
            return {
                "type": "photo",
                "bytes": buf.getvalue(),
                "caption": f"📊 Barcode (Code128): {content}"
            }
        except Exception as e2:
            return {"type": "error", "message": f"❌ Barcode-Fehler: {e2}"}
