# � Jarvis – Persönlicher AI-Assistent

Ein selbst-gehosteter, voll ausgestatteter AI-Assistent auf Oracle Cloud Free Tier mit Telegram-Integration. Jarvis kennt dich als **leopardcode.ai CEO** und ist mit einer wachsenden Sammlung an Tools ausgestattet – komplett kostenlos.

## ✨ Features

### 🧠 Intelligentes LLM-Routing
Jarvis versucht automatisch den besten verfügbaren Provider:
```
Google Gemini 2.0 Flash  →  OpenRouter (Nvidia/Free)  →  Ollama lokal (gemma4:e2b)
```

### 🛠️ Tool-Suite (alle kostenlos, kein API-Key nötig*)

| Tool | Beschreibung |
|------|--------------|
| 🌤️ **Wetter** | Open-Meteo – Live-Daten + 3-Tage-Forecast, kein Key nötig |
| 📈 **Aktien** | yfinance – Live-Kurse von Yahoo Finance |
| 🪙 **Krypto** | CoinGecko API – BTC, ETH, SOL und mehr |
| 🧠 **Gedächtnis** | SQLite-Datenbank – Notizen, Einkaufsliste, Ideen, Reminders |
| 📚 **Wikipedia** | Saubere Artikel-Zusammenfassungen (DE + EN Fallback) |
| 🔍 **Web Search** | DuckDuckGo – aktuelle Web-Suche ohne API-Key |
| 💻 **Sysadmin** | Server-Befehle (RAM, Disk, Logs, Service-Status) |
| 🐙 **GitHub** | Repos suchen, Dateien lesen, PRs erstellen, pushen |
| 🎥 **YouTube** | Automatische Benachrichtigung bei neuen Videos (@airevolutionx) |
| ☁️ **Oracle Monitor** | Benachrichtigung sobald Free-Tier Kapazität verfügbar ist |

_*Gemini API Key empfohlen für beste Performance_

### 🔒 Sicherheit
- Nur autorisierte Telegram-User IDs können den Bot nutzen
- VPN-Anbindung via Tailscale
- GitHub-Writes nur via PR (kein Force-Push auf main)

---

## 🏗️ Architektur

```
┌──────────────┐     ┌───────────────────────┐
│   Telegram   │────▶│       Jarvis Bot       │
│   CEO        │◀────│   (Oracle Cloud ARM)   │
└──────────────┘     └───────────┬───────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
     ┌────────────────┐  ┌────────────┐   ┌──────────────────┐
     │ Gemini 2.0     │  │ OpenRouter │   │  Ollama (lokal)  │
     │ (Primary LLM)  │  │ (Fallback) │   │  gemma4:e2b      │
     └────────────────┘  └────────────┘   └──────────────────┘
              │
              ├── 🌤️ Open-Meteo (Wetter)
              ├── 📈 yfinance / CoinGecko (Finanzen)
              ├── 🧠 SQLite (Gedächtnis)
              ├── 📚 Wikipedia
              ├── 🔍 DuckDuckGo (Web Search)
              ├── 🐙 GitHub API
              └── 💻 Subprocess (Sysadmin)
```

---

## 📋 Voraussetzungen

| Was | Wo | Kosten |
|-----|----|--------|
| Oracle Cloud Account | [cloud.oracle.com](https://cloud.oracle.com) | Kostenlos |
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) | Kostenlos |
| OpenRouter API Key | [openrouter.ai/keys](https://openrouter.ai/keys) | Kostenlos |
| Google Gemini API Key | [aistudio.google.com](https://aistudio.google.com/apikey) | Kostenlos |
| GitHub Personal Access Token | [github.com/settings/tokens](https://github.com/settings/tokens) | Kostenlos |

---

## 🚀 Quick Start

### 1. Oracle Cloud Instance (ARM Free Tier)

> ⚠️ Frankfurt ist oft ausgebucht. Das mitgelieferte `retry-launch.sh` versucht automatisch alle 2 Minuten alle Availability Domains.

```bash
# Automatisches Retry-Script starten (läuft im Hintergrund)
chmod +x deploy/retry-launch.sh
./deploy/retry-launch.sh > retry.log 2>&1 &

# Log beobachten
tail -f retry.log
```

**Oder manuell:**
1. Oracle Cloud → Compute → Instances → Create Instance
2. Image: **Ubuntu 22.04** | Shape: **VM.Standard.A1.Flex**
3. OCPUs: 4 | Memory: 24 GB | Boot Volume: 200 GB
4. SSH Public Key hochladen

### 2. Konfiguration (`.env`)

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ALLOWED_USER_IDS=123456789

# LLM Provider
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
OLLAMA_MODEL=gemma4:e2b

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_DEFAULT_OWNER=dein-github-username

# Tailscale (optional)
TAILSCALE_AUTH_KEY=tskey-auth-...
TAILSCALE_HOSTNAME=jarvis-oracle
```

### 3. Lokal testen

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 4. Auf Oracle-Server deployen

```bash
# Projekt + .env hochladen und Installation starten
chmod +x deploy/upload.sh
./deploy/upload.sh <SERVER_IP> ~/.ssh/oracle_key
```

Das `install.sh` erledigt automatisch:
- Python 3.12 + venv
- Ollama + gemma4:e2b pull
- Tailscale Installation + Verbindung
- systemd Service Setup

---

## 📱 Alle Befehle

### 💬 Basis
| Befehl | Beschreibung |
|--------|--------------|
| `/start` | Begrüßung |
| `/help` | Hilfe |
| `/clear` | Gesprächsverlauf löschen |
| `/status` | LLM-Provider Status |
| `/heartbeat` | Vollständiger System-Report |
| `/setprompt <text>` | Eigenen System-Prompt setzen |
| `/resetprompt` | Standard-Prompt wiederherstellen |

### � Web & Suche
| Befehl | Beschreibung |
|--------|--------------|
| `/search <query>` | DuckDuckGo Web-Suche |
| `/wiki <thema>` | Wikipedia-Zusammenfassung |
| `/weather <stadt>` | Aktuelles Wetter + 3-Tage-Forecast |

### 💰 Finanzen
| Befehl | Beschreibung |
|--------|--------------|
| `/crypto <coin>` | Krypto-Preis (btc, eth, sol, …) |
| `/stocks <ticker>` | Aktien-Kurs (TSLA, AAPL, …) |

### 🧠 Gedächtnis
| Befehl | Beschreibung |
|--------|--------------|
| `/remember [kategorie] <text>` | Eintrag speichern |
| `/recall [suche]` | Einträge anzeigen / suchen |
| `/forget <id>` | Eintrag löschen |

_Kategorien: `note`, `shopping`, `reminder`, `idea`, `todo`, `link`, `info`_

### 🐙 GitHub
| Befehl | Beschreibung |
|--------|--------------|
| `/ghsearch <query>` | Repos suchen |
| `/ghrepo <repo>` | Repo-Info + Commits |
| `/ghfile <repo> <pfad>` | Datei lesen |
| `/ghprs <repo>` | Offene Pull Requests |
| `/ghissues <repo>` | Offene Issues |
| `/ghedit <repo> <pfad> <branch> <msg> \| <inhalt>` | Datei bearbeiten → PR erstellen |
| `/ghpush <repo> <pfad> <branch> <msg> \| <inhalt>` | Direkt in Branch pushen |

### 💻 System
| Befehl | Beschreibung |
|--------|--------------|
| `/sys <befehl>` | Server-Befehl ausführen (Whitelist) |

_Erlaubte Befehle: `ram`, `disk`, `uptime`, `ps`, `ping <host>`, `status ollama`, `status openclaw`, `tailscale`, `logs ollama`, `restart ollama`_

---

## 🤖 Auto-Detection

Jarvis erkennt automatisch den Kontext und lädt Live-Daten ohne expliziten Befehl:

| Stichwörter | Aktion |
|------------|--------|
| „wetter", „regen", „temperatur" | Wetterdaten für erkannte Stadt laden |
| „bitcoin", „eth", „btc", „krypto" | CoinGecko-Preis laden |
| „aktie", „kurs", „DAX", „TSLA" | yfinance-Daten laden |
| „erkläre", „was ist", „wer war" | Wikipedia-Artikel laden |
| „news", „aktuell", „heute" | DuckDuckGo-Suche als Kontext |

---

## 📊 Monitoring

Jarvis überwacht automatisch im Hintergrund:

- **Oracle Cloud** (jede Minute): Sobald Free-Tier Kapazität verfügbar → Telegram Push mit IP + SSH-Befehl
- **YouTube @airevolutionx** (stündlich): Neues Video → Telegram Push mit Titel + Link
- **`/heartbeat`**: Kompletter Status-Report beider Monitore

---

## 📁 Projektstruktur

```
jarvis/
├── main.py                  # Einstiegspunkt
├── requirements.txt         # Python Dependencies
├── .env                     # Konfiguration (nicht in Git!)
├── .env.example             # Vorlage
├── jarvis_memory.db         # SQLite Gedächtnis (lokal)
├── retry.log                # Oracle Retry Log
├── src/
│   ├── bot.py               # Telegram Bot + alle Commands
│   ├── config.py            # Settings (pydantic)
│   ├── conversation.py      # Chat-Verlauf
│   ├── llm_router.py        # Gemini → OpenRouter → Ollama
│   ├── oracle_monitor.py    # Oracle Free-Tier Monitor
│   ├── youtube_monitor.py   # YouTube New-Video Monitor
│   ├── web_search.py        # DuckDuckGo Search
│   ├── weather.py           # Open-Meteo Wetter
│   ├── finance.py           # yfinance + CoinGecko
│   ├── memory.py            # SQLite Langzeitgedächtnis
│   ├── wikipedia_tool.py    # Wikipedia Zusammenfassungen
│   ├── sysadmin.py          # Sichere Server-Befehle
│   └── github_tool.py       # GitHub API Integration
└── deploy/
    ├── install.sh           # Server-Setup (inkl. Tailscale)
    ├── upload.sh            # SCP Upload + Remote-Install
    ├── retry-launch.sh      # Oracle Instance Retry-Script
    └── openclaw.service     # systemd Service
```

---

## � Troubleshooting

### Bot antwortet nicht
```bash
sudo systemctl status openclaw
sudo journalctl -u openclaw -n 50 --no-pager
```

### Gemini 429 (Quota)
→ Automatischer Fallback auf OpenRouter, kein Handlungsbedarf.

### Oracle Kapazität
```bash
tail -f retry.log   # Script-Status beobachten
```

### Ollama zu langsam
→ Normal auf ARM CPUs (~5 Tokens/s). OpenRouter/Gemini werden bevorzugt.

---

## 🔒 Sicherheit

- `ALLOWED_USER_IDS` auf deine Telegram-ID beschränken
- GitHub-Token nur mit nötigen Permissions (`repo`)
- `deploy/sysadmin.py` Whitelist für Server-Befehle
- `.env` niemals committen (in `.gitignore`)

---

## 📄 Lizenz

MIT License – Nutze es wie du willst!
