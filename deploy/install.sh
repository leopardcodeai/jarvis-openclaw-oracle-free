#!/bin/bash
# OpenClaw Installation Script for Oracle Cloud (Ubuntu ARM)
# Run this script on your Oracle Cloud instance

set -e

echo "🚀 OpenClaw Installation Script"
echo "================================"

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Install Ollama
echo "🦙 Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
echo "🔧 Starting Ollama service..."
sudo systemctl enable ollama
sudo systemctl start ollama

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
sleep 5

# Pull a small model for fallback (Gemma 2 2B is good for ARM)
echo "📥 Pulling Gemma 2 2B model (this may take a while)..."
ollama pull gemma2:2b

# Create app directory
APP_DIR="$HOME/openclaw"
echo "📁 Setting up application directory: $APP_DIR"

if [ -d "$APP_DIR" ]; then
    echo "Directory exists, updating..."
    cd "$APP_DIR"
    git pull 2>/dev/null || echo "Not a git repo, skipping pull"
else
    mkdir -p "$APP_DIR"
fi

# Copy files if running locally
if [ -f "./main.py" ]; then
    echo "📋 Copying application files..."
    cp -r ./* "$APP_DIR/"
fi

cd "$APP_DIR"

# Create virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit the .env file with your credentials!"
    echo "   nano $APP_DIR/.env"
    echo ""
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit your .env file: nano $APP_DIR/.env"
echo "2. Add your Telegram Bot Token (from @BotFather)"
echo "3. Add your OpenRouter API Key (from openrouter.ai)"
echo "4. Start the bot: cd $APP_DIR && source venv/bin/activate && python main.py"
echo ""
echo "Or use the systemd service:"
echo "   sudo cp deploy/openclaw.service /etc/systemd/system/"
echo "   sudo systemctl enable openclaw"
echo "   sudo systemctl start openclaw"
