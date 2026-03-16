#!/bin/bash
#
# JARVIS Installation Script
# Installs dependencies and sets up autostart
#

set -e

JARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$JARVIS_DIR/venv"

echo "========================================"
echo "  JARVIS - Personal AI Assistant Setup"
echo "========================================"
echo

# Check Python
echo "1. Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   Found: $PYTHON_VERSION"
else
    echo "   ERROR: Python 3 is required"
    exit 1
fi

# Create virtual environment
echo
echo "2. Creating virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "   Created: $VENV_DIR"
else
    echo "   Already exists: $VENV_DIR"
fi

# Activate and install dependencies
echo
echo "3. Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null

# Install core dependencies
pip install rich click apscheduler python-dateutil pyyaml > /dev/null 2>&1
echo "   [OK] Core dependencies"

# Install GUI dependencies
pip install PyQt6 > /dev/null 2>&1 && echo "   [OK] PyQt6 (GUI)" || echo "   [SKIP] PyQt6 (optional)"

# Install notification dependencies
pip install plyer > /dev/null 2>&1 && echo "   [OK] plyer (notifications)" || echo "   [SKIP] plyer"

# Install voice dependencies
pip install pyttsx3 > /dev/null 2>&1 && echo "   [OK] pyttsx3 (voice)" || echo "   [SKIP] pyttsx3"

# Install Ollama Python client
pip install ollama > /dev/null 2>&1 && echo "   [OK] ollama (AI)" || echo "   [SKIP] ollama"

# Create launcher script
echo
echo "4. Creating launcher..."
cat > "$JARVIS_DIR/jarvis" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/jarvis.py" "$@"
LAUNCHER
chmod +x "$JARVIS_DIR/jarvis"

# Create symlink in ~/.local/bin
echo
echo "5. Creating command symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$JARVIS_DIR/jarvis" "$HOME/.local/bin/jarvis"
echo "   Linked: ~/.local/bin/jarvis"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo
    echo "   NOTE: Add this to your ~/.bashrc or ~/.zshrc:"
    echo '   export PATH="$HOME/.local/bin:$PATH"'
fi

# Create desktop entry
echo
echo "6. Creating desktop entry..."
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/jarvis.desktop" << DESKTOP
[Desktop Entry]
Name=JARVIS
Comment=Personal AI Assistant
Exec=$JARVIS_DIR/jarvis --gui
Icon=computer
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
DESKTOP
echo "   Created: ~/.local/share/applications/jarvis.desktop"

# Create autostart entry
echo
echo "7. Setting up autostart..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/jarvis.desktop" << AUTOSTART
[Desktop Entry]
Name=JARVIS
Comment=Personal AI Assistant
Exec=$JARVIS_DIR/jarvis --gui
Icon=computer
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
StartupNotify=false
AUTOSTART
echo "   Created: ~/.config/autostart/jarvis.desktop"

# Check Ollama
echo
echo "8. Checking Ollama AI backend..."
if command -v ollama &> /dev/null; then
    echo "   Ollama is installed"
    if ollama list 2>/dev/null | grep -q "llama"; then
        echo "   [OK] AI models available"
    else
        echo "   Downloading AI model (this may take a few minutes)..."
        ollama pull llama3.2 || echo "   [SKIP] Could not download model"
    fi
else
    echo "   Ollama not installed. For full AI capabilities, install it:"
    echo "   curl -fsSL https://ollama.ai/install.sh | sh"
    echo "   ollama pull llama3.2"
fi

# Initialize database
echo
echo "9. Initializing database..."
source "$VENV_DIR/bin/activate"
python -c "
import sys
sys.path.insert(0, '$JARVIS_DIR')
from core.database import get_db
db = get_db()
print('   Database initialized')
"

echo
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo
echo "Commands:"
echo "  jarvis           - Start interactive CLI"
echo "  jarvis --gui     - Start GUI application"
echo "  jarvis --help    - Show all options"
echo
echo "JARVIS will start automatically on next login."
echo "Run 'jarvis --gui' now to test!"
echo
