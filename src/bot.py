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

oracle_monitor: OracleMonitor | None = None

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
    
    # Add user message to history
    conversations.add_message(user_id, "user", user_message)
    
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
        msg = await oracle_monitor.send_heartbeat()
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
    global oracle_monitor
    allowed = settings.allowed_users
    if allowed:
        oracle_monitor = OracleMonitor(application.bot, allowed[0])
        oracle_monitor.start()
        logger.info(f"Oracle monitor started, will notify {allowed[0]}")


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
