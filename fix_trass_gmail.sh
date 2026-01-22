#!/bin/bash
# Quick helper script to fix trass.gmail authentication

echo "=================================================="
echo "TRASS GMAIL AUTHENTICATION FIX"
echo "=================================================="
echo ""
echo "This script will help you re-authenticate trass.gmail"
echo ""
echo "Options:"
echo "  1. Re-authenticate now (will open browser)"
echo "  2. Disable trass.gmail sync temporarily"
echo "  3. Show current status"
echo "  4. Cancel"
echo ""
read -p "Choose an option (1-4): " choice

case $choice in
  1)
    echo ""
    echo "Starting Gmail authentication setup..."
    echo "A browser window will open for OAuth authentication."
    echo ""
    maia workspace gmail-setup trass koii@trassgames.com
    ;;
  2)
    echo ""
    echo "Disabling trass.gmail sync..."
    # Use Python to update the config
    python3 << 'EOF'
import json

config_file = "promaia.config.json"
with open(config_file, 'r') as f:
    config = json.load(f)

if 'trass.gmail' in config.get('databases', {}):
    config['databases']['trass.gmail']['sync_enabled'] = False
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print("✅ trass.gmail sync disabled in config")
    print("You can re-enable it later by setting 'sync_enabled': true")
else:
    print("❌ trass.gmail not found in config")
EOF
    ;;
  3)
    echo ""
    echo "Current trass.gmail configuration:"
    python3 << 'EOF'
import json

config_file = "promaia.config.json"
with open(config_file, 'r') as f:
    config = json.load(f)

db = config.get('databases', {}).get('trass.gmail', {})
print(f"  Sync Enabled: {db.get('sync_enabled', 'N/A')}")
print(f"  Last Sync: {db.get('last_sync_time', 'Never')}")
print(f"  Workspace: {db.get('workspace', 'N/A')}")
print(f"  Email: {db.get('database_id', 'N/A')}")
EOF
    echo ""
    echo "Checking credentials..."
    if [ -f "credentials/trass/gmail_token.json" ]; then
        echo "  Token file: ✅ EXISTS"
    else
        echo "  Token file: ❌ MISSING"
    fi
    if [ -f "credentials/trass/gmail_credentials.json" ]; then
        echo "  Credentials file: ✅ EXISTS"
    else
        echo "  Credentials file: ❌ MISSING"
    fi
    ;;
  4)
    echo ""
    echo "Cancelled."
    ;;
  *)
    echo ""
    echo "Invalid option. Please run the script again."
    ;;
esac

echo ""
echo "=================================================="
