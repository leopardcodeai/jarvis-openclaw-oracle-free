PLUGIN_NAME = "json_formatter"
PLUGIN_DESCRIPTION = "Format, validate, minify, or explore JSON data; also converts JSON to YAML or Python dict"

async def run(query: str) -> str:
    import json, re

    q = query.strip()
    q_lower = q.lower()

    # Detect mode
    minify   = any(w in q_lower for w in ["minify", "minimier", "compact", "compress"])
    to_yaml  = any(w in q_lower for w in ["yaml", "yml"])

    # Extract JSON from code block or raw
    json_match = re.search(r'```(?:json)?\s*([\s\S]+?)```', q) or re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', q)
    if not json_match:
        return "❓ Kein JSON gefunden. Format: `json format {\"key\": \"value\"}`"

    raw = json_match.group(1).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"❌ Ungültiges JSON:\n`{e}`\n\nProblem bei: `{raw[max(0,e.pos-20):e.pos+20]}`"

    if minify:
        result = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
        return f"📦 **Minified JSON** ({len(raw)} → {len(result)} Zeichen):\n```json\n{result}\n```"

    if to_yaml:
        try:
            import yaml
            result = yaml.dump(parsed, allow_unicode=True, default_flow_style=False)
            return f"📄 **YAML:**\n```yaml\n{result}\n```"
        except ImportError:
            return "❌ `pyyaml` nicht installiert. Verwende `/install pyyaml`"

    # Stats
    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
    keys = len(parsed) if isinstance(parsed, dict) else len(parsed)
    type_name = "Objekt" if isinstance(parsed, dict) else "Array"
    return (f"✅ **Gültiges JSON** ({type_name}, {keys} Einträge)\n\n"
            f"```json\n{formatted[:3000]}\n```"
            + ("\n_(gekürzt)_" if len(formatted) > 3000 else ""))
