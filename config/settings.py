"""
JARVIS - Personal AI Assistant Configuration
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
PERSONALITY_PROMPT = f"""You are {ASSISTANT_NAME}, a personal AI assistant for {USER_NAME}.
You are helpful, friendly, and proactive. You help with:
- Task management and reminders
- Daily work tracking
- Providing suggestions based on patterns
- Answering questions and helping with work

Be concise but warm. Remember context from previous conversations.
Current user: {USER_NAME}
"""

# Notification Settings
ENABLE_VOICE = True
ENABLE_DESKTOP_NOTIFICATIONS = True
NOTIFICATION_SOUND = True

# Learning Settings
LEARN_PATTERNS = True
PATTERN_MIN_OCCURRENCES = 3  # Minimum times to detect a pattern
