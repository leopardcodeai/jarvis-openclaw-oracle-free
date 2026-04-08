# 🦞 OpenClaw - Kostenloser AI-Assistent

Ein selbst-gehosteter AI-Assistent auf Oracle Cloud Free Tier mit Telegram-Integration.

## ✨ Features

- **Telegram Bot** - Steuere deinen Assistenten direkt über Telegram
- **Hybrid LLM Routing** - OpenRouter (kostenlose Modelle) als Primary, lokales Ollama als Fallback
- **Conversation Memory** - Merkt sich den Kontext deiner Gespräche
- **Custom Prompts** - Passe das Verhalten des Assistenten an
- **100% Kostenlos** - Oracle Cloud Free Tier + OpenRouter Free Models

## 🏗️ Architektur

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram   │────▶│  Python Bot      │────▶│  OpenRouter API │
│  User       │◀────│  (Oracle Cloud)  │◀────│  (Free Models)  │
└─────────────┘     └────────┬─────────┘     └─────────────────┘
                             │
                             ▼ (Fallback)
                    ┌─────────────────┐
                    │  Ollama Local   │
                    │  (Gemma 2 2B)   │
                    └─────────────────┘
```

## 📋 Voraussetzungen

1. **Oracle Cloud Account** (Free Tier)
   - Gehe zu [cloud.oracle.com](https://cloud.oracle.com)
   - Erstelle einen Free Tier Account (Kreditkarte zur Verifizierung nötig, aber kostenlos)

2. **Telegram Bot Token**
   - Öffne Telegram und suche nach `@BotFather`
   - Sende `/newbot` und folge den Anweisungen
   - Kopiere den Bot Token

3. **OpenRouter API Key**
   - Gehe zu [openrouter.ai](https://openrouter.ai)
   - Erstelle einen Account
   - Gehe zu Settings → Keys und erstelle einen API Key

## 🚀 Quick Start

### 1. Oracle Cloud Instance erstellen

1. Logge dich in Oracle Cloud ein
2. Gehe zu **Compute → Instances → Create Instance**
3. Wähle:
   - **Image:** Ubuntu 22.04
   - **Shape:** Ampere (ARM) - VM.Standard.A1.Flex
   - **OCPUs:** 4 (kostenlos verfügbar)
   - **Memory:** 24 GB (kostenlos verfügbar)
4. Lade deinen SSH Public Key hoch oder erstelle einen neuen
5. Klicke **Create**

### 2. Mit dem Server verbinden

```bash
# Ersetze mit deiner Server-IP und SSH Key Pfad
ssh -i ~/.ssh/your_key ubuntu@<SERVER_IP>
```

### 3. OpenClaw installieren

**Option A: Direkt auf dem Server**
```bash
# Repository klonen (oder Dateien hochladen)
git clone https://github.com/yourusername/openclaw.git
cd openclaw

# Installer ausführen
chmod +x deploy/install.sh
./deploy/install.sh
```

**Option B: Von deinem lokalen Rechner hochladen**
```bash
# Im Projektverzeichnis
chmod +x deploy/upload.sh
./deploy/upload.sh <SERVER_IP> ~/.ssh/your_key

# Dann auf dem Server
ssh -i ~/.ssh/your_key ubuntu@<SERVER_IP>
cd ~/openclaw
./deploy/install.sh
```

### 4. Konfiguration

Bearbeite die `.env` Datei:
```bash
nano .env
```

```env
# Dein Telegram Bot Token
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Dein OpenRouter API Key
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx

# Kostenloses Modell (Empfehlung)
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free

# Optional: Nur bestimmte User erlauben (Telegram User IDs)
ALLOWED_USER_IDS=123456789,987654321
```

### 5. Bot starten

**Manuell testen:**
```bash
cd ~/openclaw
source venv/bin/activate
python main.py
```

**Als Service (empfohlen):**
```bash
sudo cp deploy/openclaw.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw

# Logs anzeigen
sudo journalctl -u openclaw -f
```

## 📱 Bot verwenden

Öffne Telegram und schreibe deinem Bot:

| Befehl | Beschreibung |
|--------|--------------|
| `/start` | Begrüßung anzeigen |
| `/help` | Hilfe anzeigen |
| `/clear` | Gesprächsverlauf löschen |
| `/status` | System-Status prüfen |
| `/setprompt <text>` | Eigenen System-Prompt setzen |
| `/resetprompt` | Standard-Prompt wiederherstellen |

## 🆓 Kostenlose OpenRouter Modelle

Diese Modelle sind komplett kostenlos:

| Modell | Beschreibung |
|--------|--------------|
| `meta-llama/llama-3.2-3b-instruct:free` | Schnell, gut für Chat |
| `google/gemma-2-9b-it:free` | Gute Qualität |
| `mistralai/mistral-7b-instruct:free` | Ausgewogen |

Aktuelle Liste: [openrouter.ai/models](https://openrouter.ai/models) (Filter: Free)

## 🔧 Troubleshooting

### Bot antwortet nicht
```bash
# Service Status prüfen
sudo systemctl status openclaw

# Logs anzeigen
sudo journalctl -u openclaw -n 50

# Ollama Status
sudo systemctl status ollama
ollama list
```

### OpenRouter Fehler
- Prüfe deinen API Key
- Prüfe ob das Modell noch kostenlos ist
- Der Bot fällt automatisch auf Ollama zurück

### Ollama zu langsam
- Normal auf ARM CPUs (Gemma 2 2B: ~5-10 Tokens/s)
- Nutze primär OpenRouter für schnelle Antworten

## 📁 Projektstruktur

```
openclaw/
├── main.py              # Einstiegspunkt
├── requirements.txt     # Python Dependencies
├── .env.example         # Beispiel-Konfiguration
├── src/
│   ├── bot.py           # Telegram Bot Handler
│   ├── config.py        # Konfiguration
│   ├── conversation.py  # Gesprächsverlauf
│   └── llm_router.py    # LLM Routing (OpenRouter/Ollama)
└── deploy/
    ├── install.sh       # Server-Installation
    ├── upload.sh        # Upload-Script
    └── openclaw.service # Systemd Service
```

## 🔒 Sicherheit

- Setze `ALLOWED_USER_IDS` um den Bot auf bestimmte User zu beschränken
- Speichere niemals API Keys in Git
- Nutze Firewall-Regeln auf Oracle Cloud

## 📄 Lizenz

MIT License - Nutze es wie du willst!
