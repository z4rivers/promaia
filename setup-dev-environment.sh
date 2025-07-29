#!/bin/bash
# Development Environment Setup Script
# Run this script to set up your promaia-dev environment

set -e

echo "🔧 Setting up Promaia Development Environment..."

# Check if we're in the right directory
if [[ ! -f "maia.sh" ]] || [[ ! -d "promaia" ]]; then
    echo "❌ Error: Run this script from your main promaia directory"
    exit 1
fi

# Get the parent directory
PARENT_DIR=$(dirname "$(pwd)")
DEV_DIR="$PARENT_DIR/promaia-dev"

echo "📁 Cloning repository to $DEV_DIR..."
git clone . "$DEV_DIR"

cd "$DEV_DIR"

echo "🌿 Switching to development branch..."
git checkout -b development 2>/dev/null || git checkout development

echo "🔑 Setting up development environment file..."
cp docs/env.template .env.development

# Add development-specific environment variables
cat >> .env.development << 'EOF'

# Development Environment Overrides
MAIA_ENVIRONMENT=development
MAIA_DATA_DIR=data-dev
MAIA_DEBUG=1
EOF

echo "📝 Creating development config..."
cp promaia.config.json promaia.config.dev.json

echo "🐙 Creating development shell shortcut..."
cat > maiadev.sh << EOF
#!/bin/bash
# maiadev - Quick navigation to Maia DEV directory and environment activation
# Usage: maiadev (from anywhere) - navigates to maia-dev directory and activates venv

# If we're already in the promaia-dev directory, run the CLI instead
if [[ -f "promaia.config.json" ]] && [[ -d "promaia" ]]; then
    # Load development environment
    if [ -f ".env.development" ]; then
        export \$(cat .env.development | grep -v ^# | xargs)
    fi
    
    # Activate virtual environment and run CLI
    if [ -d "venv" ]; then
        source "venv/bin/activate"
        python -m promaia "\$@"
    else
        python3 -m promaia "\$@"
    fi
    exit \$?
fi

# The absolute path to your Maia DEV directory
PROMAIA_DEV_DIR="$DEV_DIR"

# Navigate to the Maia dev directory
if ! cd "\$PROMAIA_DEV_DIR"; then
    echo -e "\033[31m[ERROR]\033[0m Failed to navigate to Maia dev directory"
    exit 1
fi

# Load development environment
if [ -f ".env.development" ]; then
    export \$(cat .env.development | grep -v ^# | xargs)
fi

# Check if virtual environment exists and activate it
if [ -d "\$PROMAIA_DEV_DIR/venv" ]; then
    source "\$PROMAIA_DEV_DIR/venv/bin/activate"
else
    echo -e "\033[31m[ERROR]\033[0m Virtual environment not found. Run 'python3 -m venv venv'"
    exit 1
fi

# Show brief ready status
echo -e "\033[32m🐙 Maia DEV ready\033[0m"

# Start a new shell to keep the environment active
exec \$SHELL
EOF

chmod +x maiadev.sh

echo "🐍 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "📊 Creating development data directory..."
mkdir -p data-dev

echo "✅ Development environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env.development with your API keys"
echo "2. Add maiadev.sh to your PATH or create an alias"
echo "3. Run: source maiadev.sh"
echo ""
echo "🔄 Workflow:"
echo "• Develop in promaia-dev using 'maiadev' command"
echo "• Test thoroughly in dev environment"  
echo "• Push stable changes to main branch"
echo "• Pull into production with 'maia' command" 