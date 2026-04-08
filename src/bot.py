import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from .config import settings
from .llm_router import router
from .conversation import conversations
from .oracle_monitor import OracleMonitor
from .youtube_monitor import YouTubeMonitor
from .web_search import search, format_results_for_llm, format_results_for_telegram
from .weather import get_weather, format_weather, format_weather_for_llm
from .finance import get_crypto_price, get_stock_price, format_crypto, format_stock, format_for_llm as format_finance_llm, COINGECKO_IDS
from .memory import add_memory, list_memories, search_memories, delete_memory, format_memories
from .wikipedia_tool import wiki_search, format_wiki, format_wiki_for_llm
from .sysadmin import (run_command as sys_run, format_result as sys_format_result,
                       ALLOWED_COMMAND_KEYS, get_system_stats, format_system_stats)
from .youtube_monitor import resolve_channel_id as yt_resolve_channel_id
from .voice_transcriber import transcribe_voice
from .plugin_manager import (pip_install, list_installed, list_plugins,
                              run_plugin, extract_plugin_from_response,
                              save_and_load_plugin)
from .security import check_input, sanitize_output, check_script_code
from .script_runner import (
    run_code, save_script, search_scripts, list_scripts, get_script, delete_script,
    update_last_output, extract_script_from_response,
    format_scripts_list, format_run_result,
)
from .charts import (crypto_chart, stock_chart, format_chart_summary,
                     weather_chart, format_weather_chart_summary,
                     COINGECKO_IDS as CHART_COIN_IDS, PERIOD_DAYS, WEATHER_PERIODS)
from .github_tool import (
    search_repos as gh_search_repos, search_code as gh_search_code,
    get_repo_info as gh_repo_info, read_file as gh_read_file,
    list_prs as gh_list_prs, list_issues as gh_list_issues,
    edit_file_pr as gh_edit_pr, push_direct as gh_push,
    format_repo_info, format_search_repos, format_prs, format_issues,
)

oracle_monitor: OracleMonitor | None = None
youtube_monitor: YouTubeMonitor | None = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    allowed = settings.allowed_users
    return len(allowed) == 0 or user_id in allowed


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    
    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Du bist nicht berechtigt, diesen Bot zu nutzen.")
        return
    
    welcome_text = f"""🎖️ Guten Tag, Captain Leopard!

Ich bin **Jarvis**, Ihr persönlicher AI-Assistent. Zu Ihren Diensten.

**Befehle:**
/start - Diese Nachricht anzeigen
/clear - Gesprächsverlauf löschen
/status - System-Status prüfen
/help - Hilfe anzeigen

Was kann ich für Sie tun, Captain? 🦾"""
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not is_authorized(update.effective_user.id):
        return
    
    help_text = """📚 **Jarvis Hilfe**

**Was kann ich für Sie tun, Captain?**
• Fragen beantworten
• Texte schreiben & übersetzen
• Ideen brainstormen
• Code erklären
• Und vieles mehr!

**Befehle:**
• `/clear` - Startet ein neues Gespräch
• `/status` - Zeigt den System-Status
• `/setprompt <text>` - Setzt einen eigenen System-Prompt
• `/resetprompt` - Setzt den Standard-Prompt zurück

**Tipp:** Ich merke mir den Kontext unseres Gesprächs. Nutzen Sie /clear für ein frisches Gespräch, Captain."""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return
    
    conversations.clear_history(user_id)
    await update.message.reply_text("🧹 Gesprächsverlauf gelöscht, Captain. Wir starten frisch!")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    if not is_authorized(update.effective_user.id):
        return
    
    await update.message.reply_text("🔍 Prüfe System-Status...")
    
    health = await router.health_check()
    
    gemini_status = "✅ Online" if health["gemini"] else "❌ Offline"
    openrouter_status = "✅ Online" if health["openrouter"] else "❌ Offline"
    ollama_status = "✅ Online" if health["ollama"] else "❌ Offline"
    
    status_text = f"""📊 **System-Status, Captain**

**Google Gemini (Primary):** {gemini_status}
  Model: `{settings.gemini_model}`

**OpenRouter (Secondary):** {openrouter_status}
  Model: `{settings.openrouter_model}`

**Ollama (Fallback):** {ollama_status}
  Model: `{settings.ollama_model}`

**Routing:** Gemini → OpenRouter → Ollama"""
    
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def setprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setprompt command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Bitte gib einen Prompt an.\n"
            "Beispiel: `/setprompt Du bist ein Python-Experte.`",
            parse_mode="Markdown"
        )
        return
    
    prompt = " ".join(context.args)
    conversations.set_system_prompt(user_id, prompt)
    conversations.clear_history(user_id)
    
    await update.message.reply_text(
        f"✅ System-Prompt gesetzt:\n\n_{prompt}_\n\nGesprächsverlauf wurde gelöscht.",
        parse_mode="Markdown"
    )


async def resetprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resetprompt command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return
    
    conversations.reset_system_prompt(user_id)
    await update.message.reply_text("✅ System-Prompt auf Standard zurückgesetzt.")


WEATHER_TRIGGERS = ["wetter", "temperatur", "regenschirm", "regen", "grad", "wind", "forecast", "vorhersage", "schnee", "hitze"]
CRYPTO_TRIGGERS = list(COINGECKO_IDS.keys()) + ["krypto", "crypto", "coin"]
STOCK_TRIGGERS = ["aktie", "aktien", "stock", "kurs", "börse", "nasdaq", "dax"]
WIKI_TRIGGERS = ["erkläre", "erklar", "erklär", "was ist", "wer ist", "wer war", "definition", "bedeutung", "wikipedia", "wie funktioniert"]
SEARCH_TRIGGERS = ["such", "news", "neueste", "aktuell", "heute", "preis", "wann", "wie viel", "wie viele"]


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query> command."""
    if not is_authorized(update.effective_user.id):
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Verwendung: `/search <Suchbegriff>`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    results = await search(query)
    msg = format_results_for_telegram(query, results)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_(Ergebnisse gekürzt)_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weather <city> command."""
    if not is_authorized(update.effective_user.id):
        return
    city = " ".join(context.args) or "München"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await get_weather(city)
    if data:
        await update.message.reply_text(format_weather(data), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Stadt '{city}' nicht gefunden.")


async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /crypto <coin> command."""
    if not is_authorized(update.effective_user.id):
        return
    coin = " ".join(context.args).lower() or "bitcoin"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await get_crypto_price(coin)
    if data:
        await update.message.reply_text(format_crypto(data), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Krypto '{coin}' nicht gefunden.")


async def stocks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stocks <ticker> command."""
    if not is_authorized(update.effective_user.id):
        return
    ticker = " ".join(context.args).upper() or "AAPL"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await get_stock_price(ticker)
    if data:
        await update.message.reply_text(format_stock(data), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Aktie '{ticker}' nicht gefunden.")


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remember <category> <text> command."""
    if not is_authorized(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Verwendung: `/remember <text>` oder `/remember shopping Milch kaufen`\n"
            "Kategorien: note, shopping, reminder, idea, todo, link, info",
            parse_mode="Markdown"
        )
        return
    categories = ["note", "shopping", "reminder", "idea", "todo", "link", "info"]
    if args[0].lower() in categories:
        category = args[0].lower()
        content = " ".join(args[1:])
    else:
        category = "note"
        content = " ".join(args)
    if not content:
        await update.message.reply_text("❌ Kein Inhalt angegeben.")
        return
    mem_id = await add_memory(update.effective_user.id, content, category)
    await update.message.reply_text(f"🧠 Gespeichert als `#{mem_id}` [{category}]: {content}", parse_mode="Markdown")


async def recall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recall [query] command."""
    if not is_authorized(update.effective_user.id):
        return
    query = " ".join(context.args)
    user_id = update.effective_user.id
    if query:
        entries = await search_memories(user_id, query)
        msg = format_memories(entries, f"Suche: {query}")
    else:
        entries = await list_memories(user_id, limit=15)
        msg = format_memories(entries, "Letzte Erinnerungen")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /forget <id> command."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Verwendung: `/forget <ID>`", parse_mode="Markdown")
        return
    mem_id = int(context.args[0])
    deleted = await delete_memory(update.effective_user.id, mem_id)
    if deleted:
        await update.message.reply_text(f"🗑️ Erinnerung `#{mem_id}` gelöscht.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Erinnerung `#{mem_id}` nicht gefunden.", parse_mode="Markdown")


async def wiki_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wiki <topic> command."""
    if not is_authorized(update.effective_user.id):
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Verwendung: `/wiki <Thema>`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await wiki_search(query)
    msg = format_wiki(data)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_(Artikel gekürzt)_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def sys_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sys <command> command."""
    if not is_authorized(update.effective_user.id):
        return
    cmd = " ".join(context.args)
    if not cmd:
        cmds = "\n".join(f"• `{k}`" for k in ALLOWED_COMMAND_KEYS)
        await update.message.reply_text(f"🖥️ *Verfügbare Befehle:*\n{cmds}", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await sys_run(cmd)
    msg = sys_format_result(result, cmd)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n```"
    await update.message.reply_text(msg, parse_mode="Markdown")


CHART_TRIGGERS = ["verlauf", "chart", "graph", "entwicklung", "historisch", "history",
                  "letztes jahr", "letzten monat", "letzten wochen", "letzten 30", "letzten 7",
                  "wie war", "wie lief", "performance", "rendite", "kurs verlauf",
                  "als graph", "als chart", "als bild", "als diagramm",
                  "aktienkurs"]
# Word-boundary sensitive triggers (avoid false positives like "aktuelle" → "aktie")
_CHART_WORD_TRIGGERS = ["aktie", "kurs", "börse", "börsenkurs"]


def _is_chart_query(msg_lower: str) -> bool:
    """Check chart triggers with word-boundary awareness."""
    if any(t in msg_lower for t in CHART_TRIGGERS):
        return True
    # Word-boundary check for short ambiguous words
    import re as _re
    return any(_re.search(rf'\b{_re.escape(t)}\b', msg_lower) for t in _CHART_WORD_TRIGGERS)

# Company name → ticker mapping for auto chart detection
COMPANY_TICKERS = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "meta": "META", "facebook": "META", "netflix": "NFLX",
    "tesla": "TSLA", "nvidia": "NVDA", "amd": "AMD", "intel": "INTC",
    "qualcomm": "QCOM", "paypal": "PYPL", "shopify": "SHOP", "uber": "UBER",
    "spotify": "SPOT", "coinbase": "COIN", "palantir": "PLTR", "snowflake": "SNOW",
    "volkswagen": "VOW3.DE", "vw": "VOW3.DE", "bmw": "BMW.DE",
    "mercedes": "MBG.DE", "siemens": "SIE.DE", "sap": "SAP", "allianz": "ALV.DE",
    "bayer": "BAYN.DE", "basf": "BAS.DE", "airbus": "AIR.PA",
    "deutsche bank": "DBK.DE", "daimler": "MBG.DE",
    "samsung": "005930.KS", "alibaba": "BABA", "tencent": "0700.HK",
}

TEMP_CHART_TRIGGERS = ["temperatur graph", "temperatur chart", "temp graph", "temp chart",
                       "temperaturverlauf", "temperature graph", "temperature chart",
                       "wärme verlauf", "grad verlauf", "wie war die temperatur",
                       "letzten tag temp", "letzte 24", "letzte 48", "letzten 7 tage temp"]

# Additional keywords for compound detection: "temperatur" + one of these = chart
_TEMP_COMPOUND_KEYWORDS = [
    "verlauf", "graph", "chart", "diagramm", "bild", "visuali",
    "stunden", "tage", "woche", "monat", "letzte", "letzten",
    "historisch", "history", "entwicklung", "zeig", "wie war",
    "wie lief", "24h", "48h", "7d", "14d",
]

# Time-based keywords that turn a "wetter" query into a chart request
_WEATHER_TIME_KEYWORDS = [
    "stunden", "tage", "letzte", "letzten", "letzte 24", "letzte 48",
    "historisch", "verlauf", "entwicklung",
    "graph", "chart", "diagramm", "bild", "visuali",
    "24h", "48h", "7d", "14d",
    "wie war", "wie lief", "vergangen",
]


async def _send_chart(update: Update, context, kind: str, symbol: str, period: str):
    """Generate and send a chart image with text summary."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    if kind == "crypto":
        buf, meta = await crypto_chart(symbol, period)
    else:
        buf, meta = await stock_chart(symbol, period)

    if buf is None:
        await update.message.reply_text(f"❌ Keine Daten für `{symbol.upper()}` ({period}) gefunden.",
                                        parse_mode="Markdown")
        return None

    caption = format_chart_summary(meta, kind)
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=buf,
        caption=caption,
        parse_mode="Markdown"
    )
    return meta


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chart <symbol> [period] – generate price chart.
    Examples: /chart btc 1y   /chart TSLA 6m   /chart ethereum 3m
    Periods: 7d, 1m, 3m, 6m, 1y, 2y, 5y (default: 1y)
    """
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Verwendung: `/chart <symbol> [zeitraum]`\n\n"
            "Beispiele:\n"
            "`/chart btc 1y` – Bitcoin letztes Jahr\n"
            "`/chart eth 3m` – Ethereum letzte 3 Monate\n"
            "`/chart TSLA 6m` – Tesla letzte 6 Monate\n\n"
            "Zeiträume: `7d` `1m` `3m` `6m` `1y` `2y` `5y`",
            parse_mode="Markdown"
        )
        return

    symbol = context.args[0].lower()
    period = context.args[1].lower() if len(context.args) > 1 else "1y"

    if period not in PERIOD_DAYS:
        period = "1y"

    kind = "crypto" if symbol in CHART_COIN_IDS else "stock"
    await _send_chart(update, context, kind, symbol, period)


async def tempgraph_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tempgraph <Stadt> [24h|48h|7d|14d] – Temperaturverlauf als Graph.
    Beispiele: /tempgraph München   /tempgraph Berlin 7d
    """
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Verwendung: `/tempgraph <Stadt> [zeitraum]`\n\n"
            "Beispiele:\n"
            "`/tempgraph München` – letzte 24 Stunden\n"
            "`/tempgraph Berlin 48h` – letzte 48 Stunden\n"
            "`/tempgraph Hamburg 7d` – letzte 7 Tage\n\n"
            "Zeiträume: `24h` `48h` `7d` `14d`",
            parse_mode="Markdown"
        )
        return

    city = context.args[0]
    period = context.args[1].lower() if len(context.args) > 1 else "24h"
    if period not in WEATHER_PERIODS:
        period = "24h"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    buf, meta = await weather_chart(city, period)
    if buf is None:
        await update.message.reply_text(f"❌ Keine Wetterdaten für `{city}` gefunden.", parse_mode="Markdown")
        return
    caption = format_weather_chart_summary(meta)
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=buf,
        caption=caption,
        parse_mode="Markdown"
    )


async def install_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /install <package> – install a pip package at runtime."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        installed = list_installed()
        msg = "📦 *Installierte Pakete:*\n" + ("\n".join(f"• `{p}`" for p in installed) if installed else "_keine_")
        msg += "\n\nVerwendung: `/install <paketname>`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    package = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"📦 Installiere `{package}`...", parse_mode="Markdown")
    ok, msg = await pip_install(package)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def plugins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plugins – list all loaded plugins."""
    if not is_authorized(update.effective_user.id):
        return
    plugins = list_plugins()
    if not plugins:
        await update.message.reply_text("🔌 Keine Plugins geladen.\nJarvis kann neue schreiben wenn du ihn darum bittest!")
        return
    lines = ["🔌 *Geladene Plugins:*\n"]
    for p in plugins:
        lines.append(f"• `{p['name']}` – {p['description']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def ytid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ytid <url_or_handle> – resolve YouTube channel ID automatically."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Verwendung: `/ytid <channel-url oder @handle>`\n\n"
            "Beispiele:\n"
            "`/ytid @airevolutionx`\n"
            "`/ytid https://www.youtube.com/@MrBeast`\n"
            "`/ytid youtube.com/@mkbhd`",
            parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"🔍 Suche Channel ID für `{query}`...", parse_mode="Markdown")

    channel_id = await yt_resolve_channel_id(query)
    if channel_id:
        await update.message.reply_text(
            f"✅ *Channel ID gefunden:*\n\n"
            f"`{channel_id}`\n\n"
            f"In `.env` eintragen:\n`YOUTUBE_CHANNEL_ID={channel_id}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ Konnte keine Channel ID für `{query}` finden.\n"
            f"Tipp: Versuche die vollständige URL: `https://www.youtube.com/@handle`",
            parse_mode="Markdown"
        )


async def scripts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scripts – list all saved scripts."""
    if not is_authorized(update.effective_user.id):
        return
    scripts = await list_scripts()
    await update.message.reply_text(format_scripts_list(scripts), parse_mode="Markdown")


async def runscript_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /runscript <name_or_id> – run a saved script."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Verwendung: `/runscript <name oder ID>`", parse_mode="Markdown")
        return
    id_or_name = context.args[0]
    script = await get_script(id_or_name)
    if not script:
        await update.message.reply_text(f"❌ Kein Skript `{id_or_name}` gefunden.", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await run_code(script["code"])
    await update_last_output(script["name"], result.get("stdout", ""))
    msg = format_run_result(result, script["name"])
    await update.message.reply_text(msg, parse_mode="Markdown")


async def delscript_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delscript <name_or_id> – delete a saved script."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Verwendung: `/delscript <name oder ID>`", parse_mode="Markdown")
        return
    ok = await delete_script(context.args[0])
    if ok:
        await update.message.reply_text(f"🗑️ Skript `{context.args[0]}` gelöscht.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Skript `{context.args[0]}` nicht gefunden.", parse_mode="Markdown")


def _gh_token() -> str | None:
    return settings.github_token


def _resolve_repo(args: list[str], default_owner: str) -> str:
    """Resolve 'repo' or 'owner/repo' from args."""
    if not args:
        return ""
    name = args[0]
    if "/" in name:
        return name
    return f"{default_owner}/{name}"


async def ghsearch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghsearch <query> – search GitHub repos."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    if not token:
        await update.message.reply_text("❌ Kein GitHub-Token konfiguriert.")
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Verwendung: `/ghsearch <Suchbegriff>`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    results = await gh_search_repos(token, query)
    msg = format_search_repos(results)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n_(gekürzt)_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def ghrepo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghrepo <owner/repo> – repo info."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    if not token:
        await update.message.reply_text("❌ Kein GitHub-Token konfiguriert.")
        return
    repo = _resolve_repo(context.args, settings.github_default_owner)
    if not repo:
        await update.message.reply_text("Verwendung: `/ghrepo <repo>` oder `/ghrepo owner/repo`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await gh_repo_info(token, repo)
    if data:
        msg = format_repo_info(data)
        if len(msg) > 4000:
            msg = msg[:4000] + "\n_(gekürzt)_"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Repo `{repo}` nicht gefunden.", parse_mode="Markdown")


async def ghfile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghfile <owner/repo> <path> [branch] – read file."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    if not token:
        await update.message.reply_text("❌ Kein GitHub-Token konfiguriert.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Verwendung: `/ghfile <repo> <pfad> [branch]`", parse_mode="Markdown")
        return
    repo = _resolve_repo([context.args[0]], settings.github_default_owner)
    path = context.args[1]
    ref = context.args[2] if len(context.args) > 2 else "main"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    data = await gh_read_file(token, repo, path, ref)
    if not data:
        await update.message.reply_text(f"❌ Datei `{path}` nicht gefunden.", parse_mode="Markdown")
        return
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}", parse_mode="Markdown")
        return
    content = data["content"]
    header = f"📄 `{repo}/{path}` (branch: `{ref}`)\n\n"
    body = f"```\n{content[:3500]}\n```"
    if len(content) > 3500:
        body += "\n_(Datei gekürzt)_"
    await update.message.reply_text(header + body, parse_mode="Markdown")


async def ghprs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghprs <owner/repo> – list PRs."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    repo = _resolve_repo(context.args, settings.github_default_owner)
    if not repo:
        await update.message.reply_text("Verwendung: `/ghprs <repo>`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    prs = await gh_list_prs(token, repo)
    await update.message.reply_text(format_prs(prs, repo), parse_mode="Markdown")


async def ghissues_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghissues <owner/repo> – list issues."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    repo = _resolve_repo(context.args, settings.github_default_owner)
    if not repo:
        await update.message.reply_text("Verwendung: `/ghissues <repo>`", parse_mode="Markdown")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    issues = await gh_list_issues(token, repo)
    await update.message.reply_text(format_issues(issues, repo), parse_mode="Markdown")


async def ghedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghedit <repo> <path> <branch> <commit_msg> | <content> – edit file + create PR."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    if not token:
        await update.message.reply_text("❌ Kein GitHub-Token konfiguriert.")
        return
    text = update.message.text
    # Parse: /ghedit repo path branch commit_msg | file content
    if "|" not in text:
        await update.message.reply_text(
            "Verwendung:\n`/ghedit <repo> <pfad> <branch> <commit msg> | <dateiinhalt>`\n\n"
            "Beispiel:\n`/ghedit openclaw-oracle-free README.md jarvis/update Update README | # Neuer Titel`",
            parse_mode="Markdown"
        )
        return
    parts = text.split("|", 1)
    header_parts = parts[0].strip().split()[1:]  # remove /ghedit
    new_content = parts[1].strip()
    if len(header_parts) < 3:
        await update.message.reply_text("❌ Zu wenige Argumente. Siehe /ghedit ohne Argumente.", parse_mode="Markdown")
        return
    repo = _resolve_repo([header_parts[0]], settings.github_default_owner)
    path = header_parts[1]
    branch = header_parts[2]
    commit_msg = " ".join(header_parts[3:]) if len(header_parts) > 3 else "Jarvis edit"
    pr_title = f"[Jarvis] {commit_msg}"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await gh_edit_pr(token, repo, path, new_content, branch, commit_msg, pr_title)
    if result["success"]:
        await update.message.reply_text(
            f"✅ *PR erstellt!*\n\n"
            f"🌿 Branch: `{result['branch']}`\n"
            f"🔗 {result['pr_url']}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ Fehler: {result['error']}")


async def ghpush_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghpush <repo> <path> <branch> <commit_msg> | <content> – push directly."""
    if not is_authorized(update.effective_user.id):
        return
    token = _gh_token()
    if not token:
        await update.message.reply_text("❌ Kein GitHub-Token konfiguriert.")
        return
    text = update.message.text
    if "|" not in text:
        await update.message.reply_text(
            "Verwendung:\n`/ghpush <repo> <pfad> <branch> <commit msg> | <inhalt>`",
            parse_mode="Markdown"
        )
        return
    parts = text.split("|", 1)
    header_parts = parts[0].strip().split()[1:]
    new_content = parts[1].strip()
    if len(header_parts) < 3:
        await update.message.reply_text("❌ Zu wenige Argumente.", parse_mode="Markdown")
        return
    repo = _resolve_repo([header_parts[0]], settings.github_default_owner)
    path = header_parts[1]
    branch = header_parts[2]
    commit_msg = " ".join(header_parts[3:]) if len(header_parts) > 3 else "Jarvis push"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await gh_push(token, repo, path, new_content, commit_msg, branch)
    if result["success"]:
        await update.message.reply_text(
            f"✅ *Gepusht!*\n\n"
            f"🔀 Commit: `{result['sha']}`\n"
            f"🔗 {result['url']}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ Fehler: {result['error']}")


async def safe_reply(message, text: str, **kwargs) -> None:
    """Send reply with Markdown, fall back to plain text on parse error."""
    try:
        await message.reply_text(text, parse_mode="Markdown", **kwargs)
    except Exception:
        try:
            await message.reply_text(text, parse_mode=None, **kwargs)
        except Exception as e:
            logger.error(f"safe_reply failed: {e}")
            await message.reply_text("❌ Antwort konnte nicht gesendet werden.", parse_mode=None)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, override_text: str | None = None) -> None:
    """Handle incoming text messages."""
    user = update.effective_user
    user_id = user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Du bist nicht berechtigt, diesen Bot zu nutzen.")
        return
    
    user_message = override_text or update.message.text
    logger.info(f"Message from {user.first_name} ({user_id}): {user_message[:50]}...")

    # ── Security: prompt injection check ──────────────────────────────────────
    sec = check_input(user_message, user_id)
    if sec.blocked:
        await update.message.reply_text(sec.warning, parse_mode=None)
        return

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Intercept heartbeat/status text messages → call real command directly
    if user_message.strip().lower() in ("heartbeat", "/heartbeat", "status", "heartbeat status"):
        await heartbeat_command(update, context)
        return

    # Auto tool detection based on message content
    context_parts = []
    msg_lower = user_message.lower()

    # Temperature chart detection – explicit triggers OR compound ("temperatur" + visual/time keyword)
    import re
    _is_temp_chart = (
        any(t in msg_lower for t in TEMP_CHART_TRIGGERS)
        or ("temperatur" in msg_lower and any(k in msg_lower for k in _TEMP_COMPOUND_KEYWORDS))
        or ("wetter" in msg_lower and any(k in msg_lower for k in _WEATHER_TIME_KEYWORDS))
        or (any(x in msg_lower for x in ["48 stunden", "48h", "letzten 48", "letzte 48"])
            and any(w in msg_lower for w in ["wetter", "temperatur", "temp", "grad"]))
    )
    if _is_temp_chart:
        temp_period = "24h"
        if any(x in msg_lower for x in ["48h", "48 stunden", "letzten 48", "letzte 48", "2 tage"]):
            temp_period = "48h"
        elif any(x in msg_lower for x in ["7d", "7 tage", "woche", "letzte woche", "letzten 7"]):
            temp_period = "7d"
        elif any(x in msg_lower for x in ["14d", "14 tage", "zwei wochen", "letzten 14"]):
            temp_period = "14d"
        # Extract city: "für X" or "in X" or "von X"
        city = "München"
        for pattern in [r'für ([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)',
                        r'in ([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)',
                        r'von ([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)']:
            m = re.search(pattern, user_message)
            if m:
                city = m.group(1)
                break
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        t_buf, t_meta = await weather_chart(city, temp_period)
        if t_buf:
            caption = format_weather_chart_summary(t_meta)
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=t_buf,
                                         caption=caption, parse_mode="Markdown")
            context_parts.append(
                f"[CHART BEREITS ALS BILD GESENDET – KEIN ASCII-Diagramm ausgeben!\n"
                f"Temperatur-Chart: {city} {temp_period} | "
                f"aktuell {t_meta.get('current_temp', '?')}°C | "
                f"max {t_meta.get('max_temp', '?')}°C | "
                f"min {t_meta.get('min_temp', '?')}°C | "
                f"Niederschlag: {t_meta.get('total_precip', 0)} mm]"
            )
            logger.info(f"Auto-tempgraph: {city} {temp_period}")

    # Chart detection – only fire if a known ticker/coin is identifiable
    if _is_chart_query(msg_lower) and not _is_temp_chart:
        period = "1y"
        period_map = {"woche": "7d", "7 tage": "7d", "7d": "7d",
                      "monat": "1m", "30 tage": "1m", "1m": "1m",
                      "3 monat": "3m", "3m": "3m",
                      "6 monat": "6m", "6m": "6m",
                      "letztes jahr": "1y", "jahr": "1y", "1 jahr": "1y", "1y": "1y",
                      "2 jahr": "2y", "5 jahr": "5y"}
        for kw, p in period_map.items():
            if kw in msg_lower:
                period = p
                break

        chart_sent = False

        # 1. Crypto coins
        for coin_key in CHART_COIN_IDS:
            if coin_key in msg_lower and len(coin_key) > 2:
                await _send_chart(update, context, "crypto", coin_key, period)
                context_parts.append(f"[CHART BEREITS ALS BILD GESENDET – KEIN ASCII-Diagramm! {coin_key.upper()} {period}]")
                chart_sent = True
                break

        if not chart_sent:
            # 2. Company name → ticker lookup
            ticker = None
            for name, sym in COMPANY_TICKERS.items():
                if name in msg_lower:
                    ticker = sym
                    break

            # 3. Explicit ALLCAPS ticker – only if chart word is NEAR the ticker
            if not ticker:
                caps = re.findall(r'\b([A-Z]{2,5})\b', user_message)
                _ignore = {"DE", "AG", "KG", "SE", "AS", "AN", "IN", "UND", "MIT",
                           "AUF", "DAS", "DIE", "DER", "EIN", "ZUM", "ZUR", "NEU",
                           "AM", "IM", "ZU", "VS", "IM", "KI", "AI", "ID"}
                for t in caps:
                    if t not in _ignore:
                        ticker = t
                        break

            # Only send chart if ticker found AND yfinance likely has it
            if ticker:
                await _send_chart(update, context, "stock", ticker, period)
                context_parts.append(f"[CHART BEREITS ALS BILD GESENDET – KEIN ASCII-Diagramm! {ticker} {period}]")

    # Weather detection – if a city is identifiable, always send chart image; else text
    if any(t in msg_lower for t in WEATHER_TRIGGERS) and not _is_temp_chart:
        city = None
        for pattern in [r'(?:in|für|von|aus)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)',
                        r'([A-ZÄÖÜ][a-zäöüß]{2,}(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)\s+(?:wetter|temperatur|regen|sonne)']:
            m = re.search(pattern, user_message)
            if m:
                city = m.group(1)
                break

        if city:
            # City found → send chart (24h default, or detected period)
            temp_period = "24h"
            if any(x in msg_lower for x in ["48h", "48 stunden", "letzten 48", "letzte 48", "2 tage"]):
                temp_period = "48h"
            elif any(x in msg_lower for x in ["7d", "7 tage", "woche"]):
                temp_period = "7d"
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
            t_buf, t_meta = await weather_chart(city, temp_period)
            if t_buf:
                caption = format_weather_chart_summary(t_meta)
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=t_buf,
                                             caption=caption, parse_mode="Markdown")
                context_parts.append(
                    f"[CHART BEREITS ALS BILD GESENDET – KEIN ASCII-Diagramm!\n"
                    f"Wetter-Chart: {city} {temp_period} | "
                    f"aktuell {t_meta.get('current_temp', '?')}°C | "
                    f"max {t_meta.get('max_temp', '?')}°C | min {t_meta.get('min_temp', '?')}°C]"
                )
                logger.info(f"Auto-weather-chart: {city} {temp_period}")
            else:
                # Chart failed, fall back to text
                weather_data = await get_weather(city)
                if weather_data:
                    context_parts.append(format_weather_for_llm(weather_data))
        else:
            # No city detected → use Captain's home city Munich
            weather_data = await get_weather("München")
            if weather_data:
                context_parts.append(format_weather_for_llm(weather_data))
                logger.info("Auto-weather: no city, text fallback")

    # System stats detection (use word boundaries for short ambiguous words)
    _SYS_EXACT = ["auslastung", "system stats", "systemstatus", "ressourcen",
                  "disk usage", "wie viel ram", "wie viel cpu", "prozessor auslastung",
                  "server auslastung", "server load", "arbeitsspeicher", "speicher auslastung"]
    _SYS_WORD = ["cpu", "ram", "uptime", "speicher"]
    import re as _re
    _sys_hit = (any(t in msg_lower for t in _SYS_EXACT)
                or any(_re.search(rf'\b{t}\b', msg_lower) for t in _SYS_WORD))
    if _sys_hit:
        stats = get_system_stats()
        await update.message.reply_text(format_system_stats(stats), parse_mode="Markdown")
        context_parts.append(
            "[SYSTEM-STATS BEREITS ALS NACHRICHT GESENDET – nicht wiederholen! "
            "Nur kurz bestätigen oder auf konkrete Folgefragen eingehen.]"
        )
        logger.info("Auto-sysstat sent")

    # Crypto detection
    if any(t in msg_lower for t in CRYPTO_TRIGGERS):
        for coin in CRYPTO_TRIGGERS:
            if coin in msg_lower and len(coin) > 2:
                crypto_data = await get_crypto_price(coin)
                if crypto_data:
                    context_parts.append(format_finance_llm(crypto_data, "crypto"))
                    logger.info(f"Auto-crypto: {coin}")
                    break

    # Stock detection
    if any(t in msg_lower for t in STOCK_TRIGGERS):
        import re
        tickers = re.findall(r'\b([A-Z]{2,5})\b', user_message)
        for ticker in tickers[:2]:
            stock_data = await get_stock_price(ticker)
            if stock_data and stock_data.get("price"):
                context_parts.append(format_finance_llm(stock_data, "stock"))
                logger.info(f"Auto-stock: {ticker}")
                break

    # Wikipedia detection
    if any(t in msg_lower for t in WIKI_TRIGGERS):
        wiki_data = await wiki_search(user_message, sentences=4)
        if wiki_data["success"]:
            context_parts.append(format_wiki_for_llm(wiki_data))
            logger.info(f"Auto-wiki: {user_message[:40]}")

    # Web search fallback
    if not context_parts and any(t in msg_lower for t in SEARCH_TRIGGERS):
        results = await search(user_message, max_results=3)
        if results:
            context_parts.append(format_results_for_llm(user_message, results))
            logger.info(f"Auto-search: {user_message[:40]}")

    # Inject loaded plugins as context – ONLY if query is relevant to a plugin
    loaded = list_plugins()
    if loaded:
        import os as _os, re as _re
        _plugins_abs = _os.path.abspath("plugins")

        # Only show plugins whose name/description keywords appear in the message
        def _plugin_relevant(p: dict) -> bool:
            keywords = _re.sub(r'[_\-]', ' ', p['name'] + ' ' + p['description']).lower().split()
            # Keep only meaningful words (≥4 chars)
            keywords = [k for k in keywords if len(k) >= 4]
            return any(k in msg_lower for k in keywords)

        relevant_plugins = [p for p in loaded if _plugin_relevant(p)]
        if relevant_plugins:
            plugin_ctx = "[Geladenes Plugin verfügbar – nutze JARVIS_EXEC um es aufzurufen]\n"
            for p in relevant_plugins:
                plugin_ctx += f"• `{p['name']}`: {p['description']}\n"
            plugin_ctx += (
                f"\nAufruf-Template:\n"
                f"```python\n"
                f"import sys, importlib, asyncio, base64\n"
                f"sys.path.insert(0, r'{_plugins_abs}')\n"
                f"mod = importlib.import_module('<plugin_name>')\n"
                f"result = asyncio.run(mod.run('<query>'))\n"
                f"if isinstance(result, dict) and result.get('type') == 'photo':\n"
                f"    print('JARVIS_IMAGE:' + base64.b64encode(result['bytes']).decode())\n"
                f"else:\n"
                f"    print(result)\n"
                f"```"
            )
            context_parts.append(plugin_ctx)

    # Search script library – only for queries that clearly need computation/generation
    _SCRIPT_TRIGGERS = ["berechn", "generier", "erstell", "konvertier", "sortier",
                        "skript", "script", "code", "qr", "barcode", "liste erstell",
                        "fibonacci", "primzahl", "statistik", "csv", "json", "format"]
    _needs_script = any(t in msg_lower for t in _SCRIPT_TRIGGERS)
    lib_scripts = await search_scripts(user_message) if _needs_script else []
    if lib_scripts:
        lib_context = "[Script Library Context]\n"
        for s in lib_scripts[:3]:
            lib_context += (f"• `{s['name']}` ({s['tags'] or 'kein tag'}): {s['description'] or ''}"
                            f" – zuletzt verwendet: {s['last_used'] or 'nie'}, "
                            f"{s['use_count']}× genutzt\n")
            if s.get("last_output"):
                lib_context += f"  Letzter Output: {s['last_output'][:200]}\n"
        context_parts.append(lib_context)

    # Store ONLY the clean user message in history (no tool context)
    conversations.add_message(user_id, "user", user_message)

    # Build tool context string (only for this LLM call, not stored)
    tool_context = "\n\n" + "\n\n".join(context_parts) if context_parts else ""

    # Get history and inject tool context into last message for current LLM call
    system_prompt = conversations.get_system_prompt(user_id)
    if tool_context:
        messages = conversations.get_messages_with_context(user_id, tool_context)
    else:
        messages = conversations.get_messages(user_id)

    # Call LLM – with fallback retry if content is empty
    response = await router.chat(messages, system_prompt)

    if response.success and not response.content:
        # Empty content (e.g. Gemini safety block) – retry via OpenRouter directly
        logger.warning("Empty LLM content, retrying via OpenRouter")
        response = await router._call_openrouter(messages)
    if response.success and not response.content:
        # Still empty – try Ollama
        logger.warning("Still empty, trying Ollama")
        response = await router._call_ollama(messages)

    if not response.success or not response.content:
        error_msg = "❌ Entschuldigung, ich konnte keine Antwort generieren. Bitte versuche es später erneut."
        logger.error(f"LLM error: {response.error or 'empty content'}")
        await update.message.reply_text(error_msg)
        return

    # ── Plugin auto-save ──────────────────────────────────────────────────────
    plugin_info = extract_plugin_from_response(response.content or "")
    if plugin_info:
        logger.info(f"Plugin detected: {plugin_info['name']}")
        await update.message.reply_text(
            f"🔌 *Jarvis erstellt Plugin: `{plugin_info['name']}`*",
            parse_mode="Markdown"
        )
        if plugin_info.get("packages"):
            await update.message.reply_text(
                f"📦 Installiere: `{', '.join(plugin_info['packages'])}`...",
                parse_mode="Markdown"
            )
        ok, msg = await save_and_load_plugin(plugin_info)
        await update.message.reply_text(msg, parse_mode="Markdown")
        if ok:
            await update.message.reply_text(
                f"✅ Plugin `{plugin_info['name']}` ist jetzt aktiv!\n"
                f"Aufruf mit: `/plugins`",
                parse_mode="Markdown"
            )
        conversations.add_message(user_id, "assistant", response.content)
        return

    # ── Script auto-execution ─────────────────────────────────────────────────
    script_info = extract_script_from_response(response.content or "")
    if script_info:
        logger.info(f"Script detected: {script_info['name']}")

        # Show the clean text (without code block) first if there is one
        clean = script_info["clean_text"]
        if clean:
            await update.message.reply_text(
                f"🐍 *Jarvis schreibt ein Skript: `{script_info['name']}`*",
                parse_mode="Markdown"
            )

        # Execute the script – with self-healing retry loop
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        _sec = check_script_code(script_info["code"], user_id)
        if _sec.blocked:
            await update.message.reply_text(_sec.warning, parse_mode=None)
            conversations.add_message(user_id, "assistant", response.content)
            return
        run_result = await run_code(script_info["code"])

        # ── Self-healing: retry up to 2x on failure OR wrong output type ─────────
        _MAX_RETRIES = 2
        _IMAGE_KEYWORDS = ["bild", "foto", "image", "photo", "icon", "qr", "barcode",
                           "grafik", "picture", "generate", "erstell", "zeichn"]
        _expects_image = any(k in msg_lower for k in _IMAGE_KEYWORDS)

        for _retry in range(_MAX_RETRIES):
            _stdout = (run_result.get("stdout") or "").strip()
            _err = (run_result.get("stderr") or run_result.get("error") or "").strip()

            # Detect failure cases
            _failed = not run_result["success"]
            _wrong_type = (_expects_image and run_result["success"]
                           and not _stdout.startswith("JARVIS_IMAGE:")
                           and len(_stdout) < 500)  # got short text instead of image

            if not _failed and not _wrong_type:
                break

            if _failed:
                _reason = f"Script fehlgeschlagen:\n```\n{_err[:500]}\n```"
                _hint = "Korrigiere den Fehler und schreibe das Script komplett neu mit [JARVIS_EXEC]."
            else:
                _reason = f"Script lief durch, aber gab Text statt Bild zurück: `{_stdout[:100]}`"
                _hint = ("Der Captain erwartet ein echtes Bild als Ausgabe (JARVIS_IMAGE:<base64>). "
                         "Schreibe das Script neu, das ein echtes Bild generiert und mit "
                         "`print('JARVIS_IMAGE:' + base64.b64encode(img_bytes).decode())` ausgibt.")

            logger.info(f"Self-healing attempt {_retry+1}: {'failure' if _failed else 'wrong output type'}")
            _status = await update.message.reply_text(
                f"🔄 {'Fehler' if _failed else 'Falsches Ergebnis'} erkannt, korrigiere... "
                f"_(Versuch {_retry+2}/{_MAX_RETRIES+1})_",
                parse_mode="Markdown"
            )
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            _fix_msgs = conversations.get_messages(user_id) + [{
                "role": "user",
                "content": (
                    f"[SELBSTKORREKTUR] {_reason}\n"
                    f"Ursprüngliche Anfrage: {user_message[:200]}\n{_hint}"
                )
            }]
            _fix_resp = await router.chat(_fix_msgs, system_prompt)
            await _status.delete()

            if not _fix_resp.success:
                break
            _new_script = extract_script_from_response(_fix_resp.content)
            if not _new_script:
                break

            run_result = await run_code(_new_script["code"])
            script_info = _new_script
            response = _fix_resp
        # ── End self-healing ───────────────────────────────────────────────────

        # Save to library with output
        output_str = run_result.get("stdout", "") or run_result.get("error", "")
        await save_script(
            name=script_info["name"],
            description=user_message[:200],
            tags=script_info.get("tags", ""),
            code=script_info["code"],
            last_output=output_str[:2000],
        )

        # Check if output is an image
        stdout = run_result.get("stdout", "") or ""
        if stdout.startswith("JARVIS_IMAGE:"):
            import base64 as _b64
            img_data = _b64.b64decode(stdout[len("JARVIS_IMAGE:"):].strip())
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=img_data,
                caption=f"🖼 {script_info['name']}"
            )
            conversations.add_message(user_id, "assistant", response.content)
            return

        # Show execution result
        exec_msg = format_run_result(run_result, script_info["name"])
        if len(exec_msg) > 4000:
            exec_msg = exec_msg[:4000] + "\n```\n_(gekürzt)_"
        await update.message.reply_text(exec_msg, parse_mode="Markdown")

        # Second LLM call: interpret the output for the user
        if run_result["success"] and run_result.get("stdout"):
            interp_messages = conversations.get_messages(user_id) + [{
                "role": "user",
                "content": (
                    f"[Script `{script_info['name']}` wurde ausgeführt. Output:\n"
                    f"```\n{run_result['stdout'][:2000]}\n```]\n"
                    f"Fasse das Ergebnis präzise und verständlich für den Captain zusammen."
                )
            }]
            interp = await router.chat(interp_messages, system_prompt)
            if interp.success and interp.content:
                reply_text = interp.content
                if len(reply_text) > 4000:
                    reply_text = reply_text[:4000] + "\n_(gekürzt)_"
                await safe_reply(update.message, reply_text)
                conversations.add_message(user_id, "assistant", response.content + "\n\n" + interp.content)
                return

    # ── Normal response ───────────────────────────────────────────────────────
    conversations.add_message(user_id, "assistant", response.content)
    reply_text = sanitize_output(response.content, user_id)  # redact secrets
    if len(reply_text) > 4000:
        reply_text = reply_text[:4000] + "\n\n_(Nachricht gekürzt)_"
    await safe_reply(update.message, reply_text)


async def heartbeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /heartbeat command."""
    if not is_authorized(update.effective_user.id):
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    if oracle_monitor:
        msg = await oracle_monitor.send_heartbeat(youtube_monitor)
    else:
        msg = "⚠️ Oracle Monitor nicht aktiv."

    try:
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception:
        # Fallback: send without Markdown if formatting fails
        await update.message.reply_text(msg, parse_mode=None)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages: describe with vision LLM."""
    if not is_authorized(update.effective_user.id):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    caption = update.message.caption or "Was siehst du auf diesem Bild? Beschreibe es detailliert auf Deutsch."

    try:
        # Get highest resolution photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()

        system_prompt = conversations.get_system_prompt(update.effective_user.id)
        response = await router.chat_with_vision(
            prompt=caption,
            image_bytes=bytes(img_bytes),
            mime_type="image/jpeg",
            system_prompt=system_prompt,
        )

        if response.success:
            reply = response.content
            conversations.add_message(update.effective_user.id, "user", f"[Bild gesendet] {caption}")
            conversations.add_message(update.effective_user.id, "assistant", reply)
            if len(reply) > 4000:
                reply = reply[:4000] + "\n_(gekürzt)_"
            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Vision-Fehler: `{response.error}`", parse_mode="Markdown")

    except Exception as e:
        import traceback
        logger.error(f"Photo handler error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(f"❌ Fehler: `{type(e).__name__}: {str(e)[:150]}`", parse_mode="Markdown")


async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video messages: extract first frame via ffmpeg, describe with vision LLM."""
    if not is_authorized(update.effective_user.id):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    caption = update.message.caption or "Was siehst du in diesem Video? Beschreibe Inhalt und Kontext auf Deutsch."

    try:
        import tempfile, subprocess as sp

        # Download video (limit to 20MB)
        video = update.message.video or update.message.document
        if not video:
            await update.message.reply_text("❌ Kein Video erkannt.")
            return

        if getattr(video, "file_size", 0) > 20 * 1024 * 1024:
            await update.message.reply_text("⚠️ Video zu groß (max 20MB). Sende ein kürzeres Clip.")
            return

        status = await update.message.reply_text("🎬 Analysiere Video...", parse_mode=None)

        file = await context.bot.get_file(video.file_id)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            vid_path = vf.name
        await file.download_to_drive(vid_path)

        # Extract first frame with ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as ff:
            frame_path = ff.name
        sp.run(
            ["ffmpeg", "-y", "-i", vid_path, "-vframes", "1", "-q:v", "2", frame_path],
            capture_output=True, timeout=15
        )
        os.unlink(vid_path)

        with open(frame_path, "rb") as f:
            img_bytes = f.read()
        os.unlink(frame_path)

        await status.delete()

        system_prompt = conversations.get_system_prompt(update.effective_user.id)
        response = await router.chat_with_vision(
            prompt=f"[Erster Frame eines Videos] {caption}",
            image_bytes=img_bytes,
            mime_type="image/jpeg",
            system_prompt=system_prompt,
        )

        if response.success:
            reply = response.content
            conversations.add_message(update.effective_user.id, "user", f"[Video gesendet] {caption}")
            conversations.add_message(update.effective_user.id, "assistant", reply)
            if len(reply) > 4000:
                reply = reply[:4000] + "\n_(gekürzt)_"
            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Vision-Fehler: `{response.error}`", parse_mode="Markdown")

    except Exception as e:
        import traceback
        logger.error(f"Video handler error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(f"❌ Fehler: `{type(e).__name__}: {str(e)[:150]}`", parse_mode="Markdown")


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages: transcribe with Whisper then process as text."""
    if not is_authorized(update.effective_user.id):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        ogg_bytes = await voice_file.download_as_bytearray()

        status_msg = await update.message.reply_text("🎙 Transkribiere...", parse_mode=None)

        text, lang = await transcribe_voice(bytes(ogg_bytes))

        await status_msg.delete()

        if not text:
            await update.message.reply_text("❌ Konnte Sprache nicht erkennen.")
            return

        lang_label = {"de": "🇩🇪 Deutsch", "en": "🇬🇧 English"}.get(lang, f"🌐 {lang}")
        await update.message.reply_text(
            f"🎙 _{lang_label}_: {text}",
            parse_mode="Markdown"
        )

        # Process transcribed text exactly like a normal text message
        await handle_message(update, context, override_text=text)

    except Exception as e:
        import traceback
        logger.error(f"Voice handler error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Fehler bei der Spracherkennung:\n`{type(e).__name__}: {str(e)[:200]}`",
            parse_mode="Markdown"
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    import traceback
    tb = "".join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))
    logger.error(f"Unhandled error: {context.error}\n{tb}")

    if update and update.effective_message:
        err_type = type(context.error).__name__
        err_msg = str(context.error)[:200]
        try:
            await update.effective_message.reply_text(
                f"❌ Fehler: `{err_type}: {err_msg}`",
                parse_mode="Markdown"
            )
        except Exception:
            await update.effective_message.reply_text(
                f"❌ Fehler: {err_type}: {err_msg}"
            )


async def post_init(application: Application) -> None:
    """Start background tasks after bot initializes."""
    global oracle_monitor, youtube_monitor
    allowed = settings.allowed_users
    if allowed:
        chat_id = allowed[0]
        oracle_monitor = OracleMonitor(application.bot, chat_id)
        oracle_monitor.start()
        youtube_monitor = YouTubeMonitor(application.bot, chat_id)
        youtube_monitor.start()
        logger.info(f"Oracle + YouTube monitors started, will notify {chat_id}")


def create_application() -> Application:
    """Create and configure the bot application."""
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("heartbeat", heartbeat_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("crypto", crypto_command))
    application.add_handler(CommandHandler("stocks", stocks_command))
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("recall", recall_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(CommandHandler("wiki", wiki_command))
    application.add_handler(CommandHandler("sys", sys_command))
    application.add_handler(CommandHandler("install", install_command))
    application.add_handler(CommandHandler("plugins", plugins_command))
    application.add_handler(CommandHandler("ytid", ytid_command))
    application.add_handler(CommandHandler("scripts", scripts_command))
    application.add_handler(CommandHandler("runscript", runscript_command))
    application.add_handler(CommandHandler("delscript", delscript_command))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("tempgraph", tempgraph_command))
    application.add_handler(CommandHandler("ghsearch", ghsearch_command))
    application.add_handler(CommandHandler("ghrepo", ghrepo_command))
    application.add_handler(CommandHandler("ghfile", ghfile_command))
    application.add_handler(CommandHandler("ghprs", ghprs_command))
    application.add_handler(CommandHandler("ghissues", ghissues_command))
    application.add_handler(CommandHandler("ghedit", ghedit_command))
    application.add_handler(CommandHandler("ghpush", ghpush_command))
    application.add_handler(CommandHandler("setprompt", setprompt_command))
    application.add_handler(CommandHandler("resetprompt", resetprompt_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.VIDEO, video_handler))

    # Error handler
    application.add_error_handler(error_handler)
    
    return application


def run_bot() -> None:
    """Run the bot."""
    logger.info("Starting OpenClaw Bot...")
    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
