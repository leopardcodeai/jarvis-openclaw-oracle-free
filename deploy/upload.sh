#!/bin/bash
# Upload OpenClaw to Oracle Cloud Server
# Usage: ./deploy/upload.sh <server-ip> [ssh-key-path]

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy/upload.sh <server-ip> [ssh-key-path]"
    echo "Example: ./deploy/upload.sh 129.153.xxx.xxx ~/.ssh/oracle_key"
    exit 1
fi

SERVER_IP="$1"
SSH_KEY="${2:-~/.ssh/id_rsa}"
USER="ubuntu"

echo "🚀 Uploading OpenClaw to $SERVER_IP"
echo "================================"

# Create archive excluding unnecessary files
echo "📦 Creating archive..."
tar --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='*.pyc' \
    --exclude='.git' \
    -czvf /tmp/openclaw.tar.gz .

# Upload to server
echo "📤 Uploading to server..."
scp -i "$SSH_KEY" /tmp/openclaw.tar.gz "$USER@$SERVER_IP:~/"

# Extract and setup on server
echo "🔧 Setting up on server..."
ssh -i "$SSH_KEY" "$USER@$SERVER_IP" << 'EOF'
    mkdir -p ~/openclaw
    cd ~/openclaw
    tar -xzvf ~/openclaw.tar.gz
    rm ~/openclaw.tar.gz
    chmod +x deploy/*.sh
    echo "Files extracted to ~/openclaw"
EOF

echo ""
echo "✅ Upload complete!"
echo ""
echo "📋 Next steps on the server:"
echo "1. SSH into your server: ssh -i $SSH_KEY $USER@$SERVER_IP"
echo "2. Run the installer: cd ~/openclaw && ./deploy/install.sh"
