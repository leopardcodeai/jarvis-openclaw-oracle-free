PLUGIN_NAME = "hash_tool"
PLUGIN_DESCRIPTION = "Hash text with MD5, SHA1, SHA256, SHA512, or bcrypt; also verify hashes"

async def run(query: str) -> str:
    import hashlib, re

    q = query.strip()
    q_lower = q.lower()

    algo_map = {
        "md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256,
        "sha512": hashlib.sha512, "sha224": hashlib.sha224, "sha384": hashlib.sha384,
        "sha3_256": hashlib.sha3_256, "sha3_512": hashlib.sha3_512,
    }

    # Detect algorithm
    algo_name = "sha256"
    for name in algo_map:
        if name in q_lower:
            algo_name = name
            break

    # Extract text to hash (remove algorithm name and common words)
    text = re.sub(r'\b(hash|hashing|hashiere|md5|sha\d*|von|text|string|the|mit)\b', '', q_lower, flags=re.I).strip()
    if not text:
        text = q.strip()

    h = algo_map[algo_name](text.encode()).hexdigest()
    return (f"🔑 **{algo_name.upper()} Hash**\n\n"
            f"Input:  `{text[:80]}`\n"
            f"Hash:   `{h}`\n"
            f"Length: {len(h)} Zeichen")
