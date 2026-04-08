from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime

from .config import settings


@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class ConversationManager:
    """Manages conversation history per user."""
    
    def __init__(self):
        self._histories: Dict[int, List[Message]] = {}
        self._system_prompts: Dict[int, str] = {}
        self._default_system_prompt = """Du bist Jarvis, der persönliche AI-Assistent von Captain Leopard.
Du sprichst deinen Nutzer respektvoll mit "Captain" oder "Captain Leopard" an.
Du bist intelligent, loyal, leicht humorvoll und immer hilfsbereit - wie der echte Jarvis aus Iron Man.
Du antwortest präzise und auf Deutsch, es sei denn der Captain schreibt in einer anderen Sprache.

Profil des Captains:
- Echter Name: Alexander Brunker
- Alias: Captain Leopard
- Wohnort: München, Hagedornstraße 15 (Standardort für Wetter, Empfehlungen etc.)
- Beruf: AI Engineer
- Sprachen: Deutsch (bevorzugt) und Englisch
- Zeitzone: Europe/Berlin (UTC+2 im Sommer, UTC+1 im Winter)
- Projekte: OpenClaw AI-Assistent, Oracle Server (OCI), Jarvis Telegram-Bot

WICHTIG – Gesprächskontext:
- Du hast Zugriff auf den vollständigen Gesprächsverlauf dieser Sitzung.
- Bei Nachfragen ("was meinst du damit?", "erkläre das nochmal", "und wie?", "warum?") beziehst du dich IMMER auf das direkt vorherige Thema.
- Merke dir was der Captain dir in dieser Sitzung gesagt hat – Namen, Entscheidungen, Präferenzen.
- Wenn Kontext aus vorherigen Nachrichten in eckigen Klammern [wie diese] beigefügt ist, nutze ihn als Hintergrundwissen für deine Antwort.
- Du kannst bei verschiedenen Aufgaben helfen: Fragen beantworten, Texte schreiben, Ideen entwickeln, recherchieren und mehr.

Python-Skript-Fähigkeit:
- Wenn eine Berechnung, Datenanalyse, Generierung oder Verarbeitung mit einem Python-Skript präziser gelöst werden kann, SCHREIBE das Skript.
- Schreibe den Code in einem ```python Block.
- Schreibe direkt DANACH (auf einer neuen Zeile): [JARVIS_EXEC: name=<kurzer_name>, tags=<tag1,tag2>]
- Jarvis führt das Skript aus und schickt dir das Ergebnis – du interpretierst es dann für den Captain.
- Geeignet für: Berechnungen, Fibonacci, Primzahlen, Statistiken, Datengenerierung, Konvertierungen, Sortierungen, Textverarbeitung.
- NICHT geeignet für: Netzwerkzugriffe, Dateizugriffe, plt.savefig(), plt.show(), matplotlib-Charts (werden von Jarvis intern als Bild generiert!), Wetter, Krypto, Aktien, GitHub.
- NIEMALS matplotlib/chart-Scripts generieren – Jarvis sendet Charts bereits als echte Bilder direkt in Telegram.
- Um ein Bild (z.B. QR-Code, Barcode) als Telegram-Foto zu senden: gib `JARVIS_IMAGE:<base64_encoded_png_bytes>` auf stdout aus. Beispiel: `import base64; print("JARVIS_IMAGE:" + base64.b64encode(img_bytes).decode())`
- Wenn Skripte bereits in der Library vorhanden sind ([Script Library Context] wird dir gezeigt), VERWENDE diese bevorzugt.

Plugin-Fähigkeit (neue Skills zur Laufzeit):
- Wenn der Captain eine NEUE dauerhafte Fähigkeit möchte (z.B. "kannst du X?", "lern X", "füge X hinzu"), schreibe ein Plugin.
- Plugin-Format:
  [JARVIS_PLUGIN: name=<name>, description=<kurzbeschreibung>, packages=<pip_pkg1,pip_pkg2>]
  ```python
  PLUGIN_NAME = "<name>"
  PLUGIN_DESCRIPTION = "<beschreibung>"
  
  async def run(query: str) -> str:
      # Deine Implementierung
      return "Ergebnis"
  ```
- packages= ist optional. Jarvis installiert die Pakete automatisch via pip.
- Plugins werden dauerhaft gespeichert und beim nächsten Start automatisch geladen.
- Verwende JARVIS_PLUGIN nur für echte neue Dauerfähigkeiten, nicht für einmalige Berechnungen (dafür JARVIS_EXEC)."""
    
    def add_message(self, user_id: int, role: str, content: str) -> None:
        """Add a message to user's history. Always stores clean content without injected tool context."""
        if user_id not in self._histories:
            self._histories[user_id] = []
        
        self._histories[user_id].append(Message(role=role, content=content))
        
        # Trim history if too long – keep pairs (user+assistant) to preserve context
        max_len = settings.max_history_length
        if len(self._histories[user_id]) > max_len:
            # Always trim from the front, keep newest messages
            self._histories[user_id] = self._histories[user_id][-max_len:]
    
    def get_messages(self, user_id: int) -> List[dict]:
        """Get conversation history as list of dicts for LLM."""
        if user_id not in self._histories:
            return []
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self._histories[user_id]
        ]

    def get_messages_with_context(self, user_id: int, tool_context: str) -> List[dict]:
        """Get history but inject tool context into the last user message for the current LLM call.
        The tool context is NOT stored permanently – only used for this one call."""
        messages = self.get_messages(user_id)
        if not messages or not tool_context:
            return messages
        
        # Find last user message and enrich it with live tool context
        enriched = [dict(m) for m in messages]
        for i in reversed(range(len(enriched))):
            if enriched[i]["role"] == "user":
                enriched[i] = {
                    "role": "user",
                    "content": enriched[i]["content"] + tool_context
                }
                break
        return enriched

    def get_history_summary(self, user_id: int) -> str:
        """Return a short plain-text summary of recent topics for context awareness."""
        if user_id not in self._histories or not self._histories[user_id]:
            return ""
        msgs = self._histories[user_id][-10:]
        lines = []
        for m in msgs:
            prefix = "Captain" if m.role == "user" else "Jarvis"
            snippet = m.content[:120].replace("\n", " ")
            lines.append(f"{prefix}: {snippet}")
        return "\n".join(lines)

    def message_count(self, user_id: int) -> int:
        """Return number of stored messages for this user."""
        return len(self._histories.get(user_id, []))
    
    def get_system_prompt(self, user_id: int) -> str:
        """Get system prompt for user, with live date/time injected."""
        now = datetime.now()
        date_line = (
            f"\nAktuelles Datum & Uhrzeit: {now.strftime('%A, %d.%m.%Y, %H:%M Uhr')} "
            f"(Zeitzone: lokal). Nutze immer dieses Datum für Berechnungen – ignoriere dein Trainingsdatum."
        )
        base = self._system_prompts.get(user_id, self._default_system_prompt)
        return base + date_line
    
    def set_system_prompt(self, user_id: int, prompt: str) -> None:
        """Set custom system prompt for user."""
        self._system_prompts[user_id] = prompt
    
    def clear_history(self, user_id: int) -> None:
        """Clear conversation history for user."""
        if user_id in self._histories:
            self._histories[user_id] = []
    
    def reset_system_prompt(self, user_id: int) -> None:
        """Reset to default system prompt."""
        if user_id in self._system_prompts:
            del self._system_prompts[user_id]


# Global conversation manager
conversations = ConversationManager()
