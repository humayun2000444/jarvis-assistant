"""
JARVIS - Personal AI Assistant Configuration
Supports user overrides via data/user_config.yaml
"""
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jarvis.db"
LOG_PATH = DATA_DIR / "jarvis.log"
CONFIG_FILE = DATA_DIR / "user_config.yaml"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# ============ DEFAULTS ============

# AI Settings
AI_MODEL = "llama3.2:1b"  # Ollama model - can change to mistral, codellama, etc.
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1000

# User Settings (will be personalized)
USER_NAME = os.environ.get("USER", "User")
WORK_START_HOUR = 9
WORK_END_HOUR = 17  # 5 PM summary time
REMINDER_INTERVAL_MINUTES = 30

# Assistant Personality
ASSISTANT_NAME = "Jarvis"

# Notification Settings
ENABLE_VOICE = True
ENABLE_DESKTOP_NOTIFICATIONS = True
NOTIFICATION_SOUND = True

# Learning Settings
LEARN_PATTERNS = True
PATTERN_MIN_OCCURRENCES = 3  # Minimum times to detect a pattern

# ============ LOAD USER OVERRIDES ============

_CONFIGURABLE_KEYS = {
    'AI_MODEL', 'AI_TEMPERATURE', 'AI_MAX_TOKENS',
    'USER_NAME', 'WORK_START_HOUR', 'WORK_END_HOUR',
    'REMINDER_INTERVAL_MINUTES', 'ASSISTANT_NAME',
    'ENABLE_VOICE', 'ENABLE_DESKTOP_NOTIFICATIONS',
    'NOTIFICATION_SOUND', 'LEARN_PATTERNS', 'PATTERN_MIN_OCCURRENCES',
}

def _load_user_config():
    """Load user overrides from YAML config file if it exists"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(CONFIG_FILE, 'r') as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in _CONFIGURABLE_KEYS}
    except ImportError:
        # PyYAML not installed, try simple key: value parsing
        overrides = {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' in line:
                        key, _, value = line.partition(':')
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key in _CONFIGURABLE_KEYS:
                            # Try to convert types
                            if value.lower() in ('true', 'false'):
                                overrides[key] = value.lower() == 'true'
                            else:
                                try:
                                    overrides[key] = int(value)
                                except ValueError:
                                    try:
                                        overrides[key] = float(value)
                                    except ValueError:
                                        overrides[key] = value
        except Exception:
            pass
        return overrides
    except Exception:
        return {}

# Apply overrides to module globals
_user_overrides = _load_user_config()
_globals = globals()
for _key, _value in _user_overrides.items():
    _globals[_key] = _value

# ============ DERIVED SETTINGS ============

PERSONALITY_PROMPT = f"""You are {ASSISTANT_NAME}, a personal AI assistant for {USER_NAME}.
You are helpful, friendly, and proactive. You help with:
- Task management and reminders
- Daily work tracking
- Providing suggestions based on patterns
- Answering questions and helping with work

Be concise but warm. Remember context from previous conversations.
Current user: {USER_NAME}
"""
