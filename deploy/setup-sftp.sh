#!/bin/bash
# Setup SFTP access for Mountain Duck / Finder
# Run this on your Oracle Cloud server

echo "🦆 Setting up SFTP for Mountain Duck..."

# SFTP is already enabled by default on Ubuntu via OpenSSH
# Just verify it's working
sudo systemctl status ssh

echo ""
echo "✅ SFTP is ready!"
echo ""
echo "📋 Mountain Duck Connection Settings:"
echo "======================================="
echo "Protocol: SFTP (SSH File Transfer Protocol)"
echo "Server: <YOUR_SERVER_IP>"
echo "Port: 22"
echo "Username: ubuntu"
echo "SSH Private Key: Select your .pem or private key file"
echo ""
echo "Path to mount: /home/ubuntu/openclaw"
