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

# Install Tailscale
echo "🔐 Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable tailscaled
sudo systemctl start tailscaled

# Connect to Tailscale network
if [ -n "$TAILSCALE_AUTH_KEY" ]; then
    echo "🔗 Connecting to Tailscale as ${TAILSCALE_HOSTNAME:-jarvis-oracle}..."
    sudo tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="${TAILSCALE_HOSTNAME:-jarvis-oracle}" \
        --accept-routes \
        --ssh
    echo "✅ Tailscale connected!"
    echo "   Tailscale IP: $(tailscale ip -4)"
else
    echo "⚠️  TAILSCALE_AUTH_KEY nicht gesetzt - überspringe Tailscale-Verbindung"
fi

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

# Pull Gemma 4 e2b model
echo "📥 Pulling Gemma 4 e2b model (this may take a while)..."
ollama pull gemma4:e2b

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
echo "📋 System Status:"
echo "   Tailscale IP : $(tailscale ip -4 2>/dev/null || echo 'nicht verbunden')"
echo "   Ollama       : $(systemctl is-active ollama)"
echo "   OpenClaw Dir : $APP_DIR"
echo ""
echo "📋 Next steps:"
echo "1. Bot starten: cd $APP_DIR && source venv/bin/activate && python main.py"
echo "Or als Service:"
echo "   sudo cp deploy/openclaw.service /etc/systemd/system/"
echo "   sudo systemctl enable openclaw && sudo systemctl start openclaw"
