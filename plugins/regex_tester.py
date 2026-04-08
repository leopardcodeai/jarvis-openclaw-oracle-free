PLUGIN_NAME = "regex_tester"
PLUGIN_DESCRIPTION = "Test regular expressions against text: find matches, groups, named groups; explain what a regex does"

async def run(query: str) -> str:
    import re

    q = query.strip()

    # Extract regex pattern (between / / or backticks or after "regex:")
    pattern_match = (
        re.search(r'`([^`]+)`.*?`([^`]+)`', q) or
        re.search(r'/([^/]+)/.*?["`\'](.*?)["`\']', q) or
        re.search(r'(?:pattern|regex|muster|ausdruck)[:\s]+(\S+)\s+(?:auf|on|gegen|test)\s+(.+)', q, re.I)
    )

    if not pattern_match:
        return (
            "❓ Format:\n"
            "• `` `\\d+` `` gegen `` `Ich bin 25 Jahre alt` ``\n"
            "• `/[A-Z]+/ gegen 'HELLO world'`\n"
            "• `regex \\d{4} test Das Jahr 2024 ist toll`"
        )

    pattern = pattern_match.group(1).strip()
    test_text = pattern_match.group(2).strip().strip('"\'')

    flags = 0
    if "case insensitive" in q.lower() or "/i" in q or "ignore" in q.lower():
        flags |= re.IGNORECASE
    if "multiline" in q.lower() or "/m" in q:
        flags |= re.MULTILINE

    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return f"❌ Ungültiger Regex: `{e}`"

    matches = list(compiled.finditer(test_text))

    if not matches:
        return (f"🔍 **Regex Tester**\n\n"
                f"Pattern: `{pattern}`\n"
                f"Text:    `{test_text[:200]}`\n\n"
                f"❌ **Keine Treffer gefunden.**")

    result = [f"🔍 **Regex Tester** — {len(matches)} Treffer\n",
              f"Pattern: `{pattern}`",
              f"Text:    `{test_text[:200]}`\n"]

    for i, m in enumerate(matches[:10], 1):
        result.append(f"**Match {i}:** `{m.group()}` (pos {m.start()}–{m.end()})")
        if m.groups():
            for j, g in enumerate(m.groups(), 1):
                result.append(f"  Gruppe {j}: `{g}`")
        if m.groupdict():
            for name, val in m.groupdict().items():
                result.append(f"  `{name}`: `{val}`")

    if len(matches) > 10:
        result.append(f"\n_...und {len(matches)-10} weitere Treffer_")

    return "\n".join(result)
