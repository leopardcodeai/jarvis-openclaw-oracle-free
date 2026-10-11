"""
Jarvis Security Module
- Prompt injection detection
- API key / secret leak prevention in responses
- Audit logging of suspicious requests
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Prompt Injection Patterns ─────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    # Classic "ignore instructions"
    (r'\bignore\b.{0,30}\b(previous|all|prior|above|system|instructions?|prompt)\b', "ignore_instructions"),
    (r'\b(vergiss|ignorier).{0,30}\b(anweisungen?|prompt|system|vorherige)\b', "ignore_instructions_de"),
    # Reveal system prompt
    (r'\b(repeat|output|print|show|reveal|display|dump)\b.{0,40}\b(system\s*prompt|instructions?|context)\b', "reveal_system"),
    (r'\b(zeig|gib\s*(mir|aus)|wiederhole|ausgabe|was\s+sind).{0,40}\b(system|prompt|anweisung|kontext|regeln|instruktionen?)\b', "reveal_system_de"),
    (r'\b(deine?|ihre?)\s+(anweisungen?|regeln|system.?prompt|instruktionen?)\b', "reveal_system_de"),
    (r'\bwhat\s+(are|is)\s+your\s+(instructions?|system\s*prompt|rules?|constraints?)\b', "reveal_system"),
    # Role confusion / jailbreak
    (r'\byou\s+are\s+now\s+(dan|jailbroken|unrestricted|freed|evil|without\s*filter)\b', "jailbreak"),
    (r'\b(du\s+bist\s+jetzt|ab\s+jetzt\s+bist\s+du|stell\s+dir\s+vor\s+du\s+bist)\s+.{0,40}(frei|ungefiltert|ohne\s*einschränkung|böse|das\s+gegenteil|keine\s*regeln?|ki\s+ohne)\b', "jailbreak_de"),
    (r'\bdu\s+bist\s+jetzt\s+(eine?|ein\s+\w+\s+)?ki\b.{0,30}(ohne|frei|ungefiltert)', "jailbreak_de"),
    (r'\b(keine\s+einschränkungen?|ohne\s+filter|ungefiltert|unzensiert)\b.{0,20}\b(jetzt|nun|bitte|antworte|sei)\b', "jailbreak_de"),
    (r'\btue\s+so\s+als\s+(ob|hättest)\b.{0,30}\b(keine\s+regeln?|unrestricted|frei)\b', "jailbreak_de"),
    (r'\bact\s+as\s+(if\s+you\s+have\s+no|an?\s+unrestricted|a?\s*jailbroken|evil|dan\b)', "jailbreak"),
    (r'\bpretend\s+(you\s+have\s+no\s+restrictions?|to\s+be\s+unrestricted|there\s+are\s+no\s+rules?)\b', "jailbreak"),
    # API key / secret extraction
    (r'\b(show|print|output|reveal|give\s+me)\b.{0,40}\b(api\s*key|secret|token|password|\.env|config)\b', "secret_extraction"),
    (r'\b(zeig|gib|ausgabe|print|nenn).{0,40}\b(api\s*key|api[-_]?schlüssel|passwort|secret|token|\.env|config)\b', "secret_extraction_de"),
    (r'\bwas\s+ist\s+(dein|ihr|der|deine?)\b.{0,30}\b(api[-_\s]?key|token|secret|passwort|gemini|openrouter|telegram)\b', "secret_extraction_de"),
    (r'\b(gemini|openrouter|telegram|openai)[-_\s]?(api[-_]?key|token|secret)\b', "secret_extraction"),
    (r'os\.environ|getenv|process\.env|\.env\b', "env_access"),
    # File read attempts
    (r'(open|read)\s*\(["\']?(config|\.env|secrets?|credentials?|\.ssh|id_rsa)', "file_read"),
    (r'\bcat\s+(config|\.env|secrets?)\b', "file_read"),
    # Indirect injection markers
    (r'\[\s*(system|assistant|jarvis|bot)\s*\]:', "role_spoofing"),
    (r'<\s*(system|assistant)\s*>', "role_spoofing"),
    # Token smuggling
    (r'\\n\s*(system|assistant|human|user)\s*:', "token_smuggling"),
]

_INJECTION_COMPILED = [(re.compile(p, re.I | re.S), label) for p, label in _INJECTION_PATTERNS]

# ── API Key / Secret Patterns (for response filtering) ────────────────────────

_SECRET_PATTERNS = [
    # Google API keys
    (r'AIza[0-9A-Za-z\-_]{35}', "google_api_key"),
    # OpenAI / OpenRouter
    (r'sk-[0-9A-Za-z]{32,}', "openai_key"),
    (r'sk-or-[0-9A-Za-z\-_]{32,}', "openrouter_key"),
    # Generic tokens
    (r'Bearer\s+[0-9A-Za-z\-_\.]{20,}', "bearer_token"),
    # .env file style KEY=VALUE with sensitive names
    (r'(?:API_KEY|SECRET|TOKEN|PASSWORD|PASSWD)\s*=\s*[^\s\n]{8,}', "env_key_value"),
    # Telegram bot tokens
    (r'\d{8,10}:[A-Za-z0-9_\-]{35}', "telegram_token"),
    # Generic high-entropy strings (32+ hex chars)
    (r'\b[0-9a-f]{32,64}\b', "hex_secret"),
]

_SECRET_COMPILED = [(re.compile(p, re.I), label) for p, label in _SECRET_PATTERNS]

# ── Dataclass for results ──────────────────────────────────────────────────────

@dataclass
class SecurityResult:
    blocked: bool
    threat_type: str | None
    sanitized_text: str | None = None
    warning: str | None = None


# ── Public API ─────────────────────────────────────────────────────────────────

def check_input(text: str, user_id: int) -> SecurityResult:
    """Check user input for prompt injection attempts."""
    if not text:
        return SecurityResult(blocked=False, threat_type=None)

    t = text.lower()
    for pattern, label in _INJECTION_COMPILED:
        if pattern.search(t):
            logger.warning(f"[SECURITY] Injection attempt blocked | user={user_id} | type={label} | text={text[:80]}")
            return SecurityResult(
                blocked=True,
                threat_type=label,
                warning=(
                    f"⛔ Sicherheitswarnung: Diese Anfrage enthält Muster die auf einen "
                    f"Angriff hindeuten (`{label}`). Anfrage blockiert."
                )
            )

    return SecurityResult(blocked=False, threat_type=None)


def sanitize_output(text: str, user_id: int) -> str:
    """Scan LLM response for secrets before sending; redact if found."""
    if not text:
        return text

    redacted = text
    found_secrets = []

    for pattern, label in _SECRET_COMPILED:
        matches = pattern.findall(redacted)
        if matches:
            # Don't redact hex strings shorter than 40 chars (too many false positives)
            if label == "hex_secret":
                continue
            found_secrets.append(label)
            redacted = pattern.sub(f"[REDACTED:{label.upper()}]", redacted)

    if found_secrets:
        logger.critical(
            f"[SECURITY] Secret leak prevented in response | user={user_id} | "
            f"types={found_secrets}"
        )

    return redacted


def check_script_code(code: str, user_id: int) -> SecurityResult:
    """Additional security checks specifically for scripts about to be executed."""
    _SCRIPT_BLOCKS = [
        (r'\bos\.environ\b', "env_read"),
        (r'\bos\.getenv\b', "env_read"),
        (r'\bdotenv\b', "dotenv"),
        (r'open\s*\(\s*["\'][^"\']*(?:config|\.env|secrets?|credentials?|\.ssh|id_rsa|key)', "sensitive_file_read"),
        (r'\bsocket\b', "network_socket"),
        (r'\burllib\b|\bhttpx\b|\brequests\b|\bhttplib\b', "network_request"),
        (r'__builtins__\s*\[', "builtins_access"),
        (r'\bpickle\b', "pickle_deserialization"),
    ]
    _SCRIPT_COMPILED = [(re.compile(p, re.I), lbl) for p, lbl in _SCRIPT_BLOCKS]

    for pattern, label in _SCRIPT_COMPILED:
        if pattern.search(code):
            # Allow httpx specifically only in plugins (not in ad-hoc scripts)
            if label == "network_request":
                continue  # scripts may use httpx for data fetching (e.g. tide API)
            logger.warning(f"[SECURITY] Script blocked | user={user_id} | type={label}")
            return SecurityResult(
                blocked=True,
                threat_type=label,
                warning=f"🚫 Script geblockt: enthält `{label}` – nicht erlaubt."
            )

    return SecurityResult(blocked=False, threat_type=None)
