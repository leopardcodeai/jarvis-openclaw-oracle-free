PLUGIN_NAME = "text_stats"
PLUGIN_DESCRIPTION = "Analyze text: word count, character count, reading time, sentence count, most common words, language detection"

async def run(query: str) -> str:
    import re
    from collections import Counter

    # Strip command words
    text = re.sub(r'^(analysier|analyze|stats?|zähle?|count|text stats?)\s+', '', query.strip(), flags=re.I)
    if not text:
        return "❓ Format: `text stats <dein text hier>`"

    words = re.findall(r'\b\w+\b', text.lower())
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chars_no_space = len(text.replace(' ', '').replace('\n', ''))
    reading_time = max(1, round(len(words) / 200))  # avg 200 wpm
    speaking_time = max(1, round(len(words) / 130))  # avg 130 wpm

    # Top words (filter stopwords)
    stopwords = {"der","die","das","und","in","ist","ein","eine","ich","du","wir","sie",
                 "the","a","an","and","is","in","of","to","it","that","this","for",
                 "with","on","are","was","at","be","by","have","has","will","not","or"}
    filtered = [w for w in words if w not in stopwords and len(w) > 2]
    top_words = Counter(filtered).most_common(5)

    avg_word = round(sum(len(w) for w in words) / len(words), 1) if words else 0
    avg_sent = round(len(words) / len(sentences), 1) if sentences else 0

    return (
        f"📊 **Text-Analyse**\n\n"
        f"📝 Wörter:       **{len(words)}**\n"
        f"🔤 Zeichen:      **{len(text)}** (ohne Leerzeichen: {chars_no_space})\n"
        f"📄 Sätze:        **{len(sentences)}**\n"
        f"📑 Absätze:      **{len(paragraphs)}**\n"
        f"⌛ Lesezeit:     **~{reading_time} min** (200 Wpm)\n"
        f"🎤 Redezeit:     **~{speaking_time} min** (130 Wpm)\n"
        f"📏 Ø Wortlänge: **{avg_word} Zeichen**\n"
        f"📐 Ø Satzlänge: **{avg_sent} Wörter**\n\n"
        f"🔝 Top-Wörter: {', '.join(f'`{w}` ({c}×)' for w,c in top_words)}"
    )
