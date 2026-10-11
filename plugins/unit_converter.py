PLUGIN_NAME = "unit_converter"
PLUGIN_DESCRIPTION = "Convert between units: length, weight, temperature, volume, speed, data size"

async def run(query: str) -> str:
    import re
    q = query.lower().strip()

    UNITS = {
        # length (base: meter)
        "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
        "mile": 1609.344, "miles": 1609.344, "yard": 0.9144, "yards": 0.9144,
        "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
        "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
        # weight (base: kg)
        "kg": 1, "g": 0.001, "mg": 0.000001, "t": 1000,
        "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
        "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
        # speed (base: m/s)
        "kmh": 1/3.6, "km/h": 1/3.6, "mph": 0.44704, "m/s": 1, "knot": 0.514444,
        # data (base: byte)
        "byte": 1, "bytes": 1, "kb": 1024, "mb": 1048576, "gb": 1073741824, "tb": 1099511627776,
        # volume (base: liter)
        "l": 1, "liter": 1, "liters": 1, "ml": 0.001,
        "gallon": 3.78541, "gallons": 3.78541, "pint": 0.473176, "pints": 0.473176,
        "cup": 0.236588, "cups": 0.236588, "fl oz": 0.0295735,
    }

    GROUPS = {
        frozenset(["km","m","cm","mm","mile","miles","yard","yards","foot","feet","ft","inch","inches","in"]): "length",
        frozenset(["kg","g","mg","t","lb","lbs","pound","pounds","oz","ounce","ounces"]): "weight",
        frozenset(["kmh","km/h","mph","m/s","knot"]): "speed",
        frozenset(["byte","bytes","kb","mb","gb","tb"]): "data",
        frozenset(["l","liter","liters","ml","gallon","gallons","pint","pints","cup","cups","fl oz"]): "volume",
    }

    # Temperature: handle separately
    temp_match = re.search(r'(-?\d+(?:\.\d+)?)\s*(°?c|celsius|°?f|fahrenheit|°?k|kelvin)\s+(?:to|in|nach|zu)\s*(°?c|celsius|°?f|fahrenheit|°?k|kelvin)', q)
    if temp_match:
        val = float(temp_match.group(1))
        frm = temp_match.group(2).replace("°","").replace("elsius","").replace("ahrenheit","").replace("elvin","").lower()
        to  = temp_match.group(3).replace("°","").replace("elsius","").replace("ahrenheit","").replace("elvin","").lower()
        def to_k(v, u):
            if u in ("c","celsius"): return v + 273.15
            if u in ("f","fahrenheit"): return (v + 459.67) * 5/9
            return v
        def from_k(v, u):
            if u in ("c","celsius"): return v - 273.15
            if u in ("f","fahrenheit"): return v * 9/5 - 459.67
            return v
        result = from_k(to_k(val, frm), to)
        return f"🌡 {val} {frm.upper()} = **{result:.4g} {to.upper()}**"

    # General units
    match = re.search(r'(-?\d+(?:\.\d+)?)\s*([a-z/² ]+?)\s+(?:to|in|nach|zu)\s+([a-z/² ]+)', q)
    if not match:
        return ("❓ Format: `<wert> <einheit> in <einheit>`\nBeispiele:\n"
                "• `5 km in miles`\n• `100 lbs in kg`\n• `37 C in F`\n• `1 GB in MB`")

    val = float(match.group(1))
    u_from = match.group(2).strip().rstrip("s").lower()
    u_to   = match.group(3).strip().rstrip("s").lower()

    # Normalize
    def norm(u):
        aliases = {"kilometre": "km", "metre": "m", "centimetre": "cm",
                   "kilogram": "kg", "gram": "g", "pound": "lb",
                   "megabyte": "mb", "gigabyte": "gb", "kilobyte": "kb"}
        return aliases.get(u, u)
    u_from, u_to = norm(u_from), norm(u_to)

    if u_from not in UNITS or u_to not in UNITS:
        return f"❓ Einheit `{u_from}` oder `{u_to}` nicht erkannt."

    # Check same group
    grp_from = next((g for g, k in GROUPS.items() if u_from in k or u_from+"s" in k), None)
    grp_to   = next((g for g, k in GROUPS.items() if u_to in k or u_to+"s" in k), None)
    if grp_from != grp_to:
        return f"❌ Kann `{u_from}` nicht in `{u_to}` umrechnen (verschiedene Einheitentypen)."

    result = val * UNITS[u_from] / UNITS[u_to]
    return f"📐 {val} {u_from} = **{result:.6g} {u_to}**"
