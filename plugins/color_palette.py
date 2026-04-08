PLUGIN_NAME = "color_palette"
PLUGIN_DESCRIPTION = "Generate a color swatch image from hex codes, RGB values, or color names; also show color info"

import io, base64

NAMED_COLORS = {
    "red": "#FF0000", "green": "#00FF00", "blue": "#0000FF", "white": "#FFFFFF",
    "black": "#000000", "yellow": "#FFFF00", "orange": "#FF8000", "purple": "#800080",
    "pink": "#FFC0CB", "cyan": "#00FFFF", "magenta": "#FF00FF", "brown": "#A52A2A",
    "gold": "#FFD700", "silver": "#C0C0C0", "navy": "#000080", "teal": "#008080",
    "coral": "#FF6347", "salmon": "#FA8072", "violet": "#EE82EE", "indigo": "#4B0082",
    "lime": "#00FF00", "mint": "#98FF98", "rose": "#FF007F", "sky": "#87CEEB",
}

async def run(query: str) -> dict:
    import re
    from PIL import Image, ImageDraw, ImageFont

    q = query.strip().lower()

    # Extract colors (hex or names)
    hex_colors = re.findall(r'#[0-9a-f]{3,8}', q, re.I)
    named = [NAMED_COLORS[n] for n in NAMED_COLORS if n in q]
    colors = list(dict.fromkeys(hex_colors + named)) or ["#3A86FF", "#FF006E", "#FFBE0B", "#FB5607", "#8338EC"]

    # Normalize hex
    def norm(h):
        h = h.lstrip('#')
        if len(h) == 3: h = ''.join(c*2 for c in h)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    sw = 200
    h_swatch = 200
    padding = 10
    label_h = 60
    img_w = len(colors) * (sw + padding) + padding
    img_h = h_swatch + label_h + padding * 2

    img = Image.new("RGB", (img_w, img_h), (245, 245, 245))
    draw = ImageDraw.Draw(img)

    for i, color in enumerate(colors):
        rgb = norm(color)
        x = padding + i * (sw + padding)
        # Swatch
        draw.rectangle([x, padding, x + sw, padding + h_swatch], fill=rgb)
        # Border
        draw.rectangle([x, padding, x + sw, padding + h_swatch], outline=(200,200,200), width=1)
        # Hex label
        luma = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        txt_color = (255,255,255) if luma < 128 else (0,0,0)
        hex_label = color if color.startswith('#') else f"#{color}"
        draw.text((x + sw//2, padding + h_swatch//2), hex_label.upper(),
                  fill=txt_color, anchor="mm")
        # RGB below
        draw.text((x + sw//2, padding + h_swatch + 15),
                  f"R{rgb[0]} G{rgb[1]} B{rgb[2]}",
                  fill=(80,80,80), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {
        "type": "photo",
        "bytes": buf.getvalue(),
        "caption": f"🎨 Farbpalette: {' | '.join(colors)}"
    }
