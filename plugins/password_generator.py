PLUGIN_NAME = "password_generator"
PLUGIN_DESCRIPTION = "Generate secure passwords with custom length, complexity, and count"

async def run(query: str) -> str:
    import secrets, string, re

    q = query.lower()
    length = int(m.group(1)) if (m := re.search(r'(\d+)\s*(?:zeichen|char|lang|länge|length)', q)) else 16
    count  = int(m.group(1)) if (m := re.search(r'(\d+)\s*(?:stück|passw|pw)', q)) else 1
    length = max(8, min(128, length))
    count  = max(1, min(10, count))

    use_symbols = not any(w in q for w in ["ohne symbol", "no symbol", "simple", "einfach", "nur buchstaben"])
    use_digits  = not any(w in q for w in ["ohne zahlen", "no digit"])

    charset = string.ascii_letters
    if use_digits:   charset += string.digits
    if use_symbols:  charset += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    def gen():
        while True:
            pw = ''.join(secrets.choice(charset) for _ in range(length))
            if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and (not use_digits or any(c.isdigit() for c in pw))
                and (not use_symbols or any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in pw))):
                return pw

    passwords = [gen() for _ in range(count)]
    strength = "💪 Sehr stark" if length >= 20 and use_symbols else "✅ Stark" if length >= 12 else "⚠️ Mittel"
    result = f"🔐 **Passwort{'er' if count > 1 else ''} ({length} Zeichen, {strength}):**\n\n"
    result += "\n".join(f"`{pw}`" for pw in passwords)
    return result
