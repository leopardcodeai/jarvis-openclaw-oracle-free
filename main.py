#!/usr/bin/env python3
"""OpenClaw - AI Assistant with Telegram Integration"""

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.bot import run_bot

if __name__ == "__main__":
    run_bot()
