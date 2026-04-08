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
from .sysadmin import run_command as sys_run, format_result as sys_format_result, ALLOWED_COMMAND_KEYS
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user = update.effective_user
    user_id = user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Du bist nicht berechtigt, diesen Bot zu nutzen.")
        return
    
    user_message = update.message.text
    logger.info(f"Message from {user.first_name} ({user_id}): {user_message[:50]}...")
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Auto tool detection based on message content
    context_parts = []
    msg_lower = user_message.lower()

    # Weather detection
    if any(t in msg_lower for t in WEATHER_TRIGGERS):
        import re
        city_match = re.search(r'in ([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)', user_message)
        city = city_match.group(1) if city_match else "München"
        weather_data = await get_weather(city)
        if weather_data:
            context_parts.append(format_weather_for_llm(weather_data))
            logger.info(f"Auto-weather: {city}")

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

    # Build full message with context
    search_context = "\n\n" + "\n\n".join(context_parts) if context_parts else ""
    full_message = user_message + search_context if search_context else user_message
    conversations.add_message(user_id, "user", full_message)
    
    # Get conversation history and system prompt
    messages = conversations.get_messages(user_id)
    system_prompt = conversations.get_system_prompt(user_id)
    
    # Call LLM
    response = await router.chat(messages, system_prompt)
    
    if not response.success:
        error_msg = "❌ Entschuldigung, ich konnte keine Antwort generieren. Bitte versuche es später erneut."
        logger.error(f"LLM error: {response.error}")
        await update.message.reply_text(error_msg)
        return
    
    # Add assistant response to history
    conversations.add_message(user_id, "assistant", response.content)
    
    # Send response with provider info
    provider_emoji = "🌐" if response.provider == "openrouter" else "🏠"
    
    # Telegram has a 4096 character limit
    reply_text = response.content
    if len(reply_text) > 4000:
        reply_text = reply_text[:4000] + "\n\n_(Nachricht gekürzt)_"
    
    await update.message.reply_text(reply_text, parse_mode="Markdown")


async def heartbeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /heartbeat command."""
    if not is_authorized(update.effective_user.id):
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    if oracle_monitor:
        msg = await oracle_monitor.send_heartbeat(youtube_monitor)
    else:
        msg = "⚠️ Oracle Monitor nicht aktiv."
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ein Fehler ist aufgetreten. Bitte versuche es erneut."
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
    application.add_handler(CommandHandler("ghsearch", ghsearch_command))
    application.add_handler(CommandHandler("ghrepo", ghrepo_command))
    application.add_handler(CommandHandler("ghfile", ghfile_command))
    application.add_handler(CommandHandler("ghprs", ghprs_command))
    application.add_handler(CommandHandler("ghissues", ghissues_command))
    application.add_handler(CommandHandler("ghedit", ghedit_command))
    application.add_handler(CommandHandler("ghpush", ghpush_command))
    application.add_handler(CommandHandler("setprompt", setprompt_command))
    application.add_handler(CommandHandler("resetprompt", resetprompt_command))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    return application


def run_bot() -> None:
    """Run the bot."""
    logger.info("Starting OpenClaw Bot...")
    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
