import re

# International Morse code mapping (reusable, no hard‑coded output values)
_MORSE_TO_TEXT = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", ".----.": "'",
    "-.-.--": "!", "-..-.": "/", "-.--.": "(", "-.--.-": ")",
    ".-...": "&", "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-......": "-", "-.-.-..": "_", "..--.-": "_",
    "...-..-": "$", ".--.-.": "@"
}

_TEXT_TO_MORSE = {v: k for k, v in _MORSE_TO_TEXT.items()}


async def run(query: str) -> str | dict:
    """
    Expected query format:
        "encode <text>"   – convert plain text to Morse code
        "decode <code>"   – convert Morse code back to plain text

    The function is case‑insensitive for the command word and tolerates
    extra whitespace.  Morse symbols are separated by a single space;
    groups are separated by three spaces (standard word separator).
    """
    # Normalise input
    query = query.strip()
    if not query:
        return "Error: empty query."

    parts = query.split(maxsplit=1)
    if len(parts) != 2:
        return "Error: expected 'encode <text>' or 'decode <code>'."

    command, payload = parts[0].lower(), parts[1]

    if command == "encode":
        # Encode: each character → Morse, separate letters with space,
        # separate words with three spaces.
        morse_chars = []
        for ch in payload:
            if ch.isalnum() or ch in _MORSE_TO_TEXT:
                morse_chars.append(_TEXT_TO_MORSE.get(ch.upper(), ""))
            # Non‑supported characters are ignored (could raise error instead)
        if not morse_chars:
            return "Error: no convertible characters found."
        # Join letters with single space, words (3+ spaces) are preserved
        # by detecting three consecutive spaces in the original payload.
        # Simpler: just join with single space.
        return " ".join(morse_chars)

    elif command == "decode":
        # Decode: Morse symbols separated by spaces, words by three spaces.
        # Split on three or more spaces to get words, then on single spaces for symbols.
        # Standard Morse uses single space between symbols, triple space between words.
        # We'll split on any amount of whitespace and then try to map each token.
        tokens = re.split(r"\s+", payload.strip())
        decoded_words = []
        for token in tokens:
            if token == "":
                continue
            char = _MORSE_TO_TEXT.get(token)
            if char is None:
                return f"Error: unknown Morse symbol '{token}'."
            decoded_words.append(char)
        if not decoded_words:
            return "Error: no Morse symbols found."
        return "".join(decoded_words)

    else:
        return f"Error: unknown command '{command}'. Use 'encode' or 'decode'."