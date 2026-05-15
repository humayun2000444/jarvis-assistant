# JARVIS - Personal AI Assistant

A robust, Iron Man-inspired personal AI assistant with wake word activation, voice conversation, GUI and CLI interfaces. JARVIS helps you manage tasks, launch apps, track daily activities, and provides intelligent suggestions based on your behavior patterns.

## Features

- **"Hey Jarvis" Wake Word** - Always listening, activates hands-free
- **Voice Conversation** - Natural two-way voice conversation with speak-back
- **App Launcher** - Open any installed app by voice or text ("open Chrome", "launch VS Code")
- **Task Management** - Add, complete, and track tasks with priorities and due dates
- **Activity Logging** - Log daily work activities with duration tracking
- **Daily Summaries** - Automatic end-of-day productivity summaries
- **Pattern Learning** - Learns from your daily routine and provides suggestions
- **Neural Voice Output** - Human-like text-to-speech with British accent
- **Weather Updates** - Real-time weather information for any location
- **Desktop Notifications** - System notifications for reminders
- **Pomodoro Timer** - Built-in focus timer with breaks
- **Health Reminders** - Water, posture, eye strain, and stretch reminders
- **System Monitoring** - Real-time CPU, RAM, Disk, and Battery status
- **Local AI** - Uses Ollama for privacy-focused local AI processing
- **Multi-Model Support** - Switch between Ollama models with `--model` flag
- **Plugin System** - Extend JARVIS with custom plugins
- **YAML Config** - User-customizable settings via `data/user_config.yaml`

## Screenshots

The GUI features an Iron Man-inspired interface with:
- Animated Arc Reactor
- Dark HUD theme with cyan/blue glow
- System monitoring panels
- Command palette (Ctrl+K)
- Voice conversation mode (Ctrl+J)
- Wake word status indicator

## Installation

### Prerequisites

- Python 3.8+
- Ollama (for AI features)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/humayun2000444/jarvis-assistant.git
cd jarvis

# Run the installer
chmod +x install.sh
./install.sh

# Or manual installation
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Ollama (for AI features)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2:1b
```

## Usage

### GUI Mode (Iron Man Style Interface)
```bash
jarvis --gui
# or
jarvis -g
```

### CLI Mode (Interactive Terminal)
```bash
jarvis
```

### Background Daemon
```bash
jarvis --daemon
```

### Voice Mode (Terminal-based Conversation)
```bash
jarvis --voice       # Start continuous voice conversation
jarvis --talk        # Quick voice interaction (speak once)
```

### Model Management
```bash
jarvis --list-models           # List available Ollama models
jarvis --model mistral --gui   # Use a different model
```

### Quick Commands
```bash
jarvis --welcome     # Show welcome message
jarvis --summary     # Show daily summary
jarvis --health      # Check system health
jarvis --diagnose    # Run full diagnostics
jarvis --setup       # Run initial setup
```

### Voice Commands (GUI)

JARVIS listens for the wake word **"Hey Jarvis"** at all times. Once activated:

| Voice Command | Action |
|--------------|--------|
| "Hey Jarvis" | Wake up and start listening |
| "Hey Jarvis, open Chrome" | Wake up and execute immediately |
| "open terminal" | Launch terminal |
| "start VS Code" | Launch Visual Studio Code |
| "open file manager" | Launch Nautilus |
| "what's the weather" | Get current weather |
| "what time is it" | Get current time |
| "volume up/down" | Adjust system volume |
| "take screenshot" | Capture screen |
| "lock screen" | Lock the screen |
| "goodbye" / "stop listening" | End conversation mode |

JARVIS can launch **any installed application** — not just the ones listed above. It searches system binaries and .desktop files automatically.

### CLI Commands
```bash
# Task management
/tasks              # List pending tasks
/add <task>         # Add a new task
/done <id>          # Complete a task

# Activity logging
/log <activity>     # Log an activity
/today              # Show today's activities

# Reports
/summary            # Generate daily summary
/stats              # Show productivity stats
/suggest            # Get behavior suggestions

# Weather
/weather             # Current weather (auto-detect location)
/weather London      # Weather for specific city
"what's the weather"  # Natural language also works

# Other
/help               # Show all commands
exit                # Exit JARVIS
```

## Configuration

### YAML Config File

Create `data/user_config.yaml` to customize settings:

```yaml
# AI Model (Ollama)
AI_MODEL: "llama3.2:1b"
AI_TEMPERATURE: 0.7

# User Settings
USER_NAME: "Tony"
ASSISTANT_NAME: "Jarvis"

# Work hours
WORK_START_HOUR: 9
WORK_END_HOUR: 17

# Reminder intervals
REMINDER_INTERVAL_MINUTES: 30

# Features
ENABLE_VOICE: true
ENABLE_DESKTOP_NOTIFICATIONS: true
```

### Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `AI_MODEL` | `llama3.2:1b` | Ollama model to use |
| `AI_TEMPERATURE` | `0.7` | AI response creativity (0.0-1.0) |
| `USER_NAME` | System user | Your name |
| `ASSISTANT_NAME` | `Jarvis` | Assistant's name |
| `WORK_START_HOUR` | `9` | Work start hour |
| `WORK_END_HOUR` | `17` | Work end hour |
| `ENABLE_VOICE` | `true` | Enable voice output |

## Project Structure

```
jarvis/
├── jarvis.py           # Main entry point
├── pyproject.toml      # Python project config
├── install.sh          # Installation script
├── requirements.txt    # Python dependencies
├── config/
│   └── settings.py     # Configuration with YAML override support
├── core/
│   ├── ai_engine.py    # Ollama AI integration with token-aware context
│   ├── database.py     # SQLite database with connection pooling
│   ├── features.py     # System monitor, Voice engine, Pomodoro, App launcher
│   ├── voice_assistant.py  # Voice conversation and wake word
│   ├── weather.py      # Real-time weather service
│   ├── scheduler.py    # Task scheduler (daemon mode)
│   ├── health.py       # Health checks & diagnostics
│   └── logger.py       # Logging system
├── cli/
│   └── main.py         # CLI interface
├── gui/
│   └── main_window.py  # PyQt6 GUI with wake word listener
├── plugins/
│   ├── __init__.py
│   └── loader.py       # Plugin discovery and loading
├── tests/
│   ├── test_database.py    # Database tests (27 tests)
│   └── test_ai_engine.py   # AI engine tests (17 tests)
└── data/
    ├── jarvis.db       # SQLite database
    ├── user_config.yaml # User config overrides
    └── logs/           # Log files
```

## Plugins

JARVIS supports plugins for extending functionality. Create a Python file in the `plugins/` directory:

```python
# plugins/my_plugin.py
def register(app):
    app['commands']['greet'] = {
        'description': 'Say hello',
        'handler': lambda args: print("Hello from my plugin!")
    }
```

Plugins can register:
- **CLI commands** — available as `/command` in interactive mode
- **Quick commands** — available in the command palette (Ctrl+K)
- **Scheduled jobs** — run on a timer

## Health & Diagnostics

```bash
# Quick health check
jarvis --health

# Full diagnostic report
jarvis --diagnose

# Attempt repairs
jarvis --repair database
jarvis --repair logs
jarvis --repair config
```

## Keyboard Shortcuts (GUI)

| Shortcut | Action |
|----------|--------|
| `Ctrl+J` | Toggle voice conversation mode |
| `Ctrl+K` | Open command palette |
| `Ctrl+M` | Toggle voice output |
| `Ctrl+Q` | Quit application |

## Dependencies

### Required
- PyQt6 - GUI framework
- rich - CLI formatting
- click - CLI commands
- apscheduler - Task scheduling

### Optional
- ollama - Local AI
- edge-tts - Neural text-to-speech
- pyttsx3 - TTS fallback
- SpeechRecognition - Voice input
- psutil - System monitoring
- plyer - Desktop notifications
- pyyaml - YAML config support

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_database.py -v
pytest tests/test_ai_engine.py -v
```

## Troubleshooting

### Ollama not working
```bash
# Start Ollama service
ollama serve

# Pull the model
ollama pull llama3.2:1b

# List available models
jarvis --list-models
```

### Voice not working
```bash
# Install voice dependencies
pip install SpeechRecognition edge-tts

# Test voice
python -c "from core.features import VoiceEngine; VoiceEngine().test_voice()"
```

### GUI not starting
```bash
# Install PyQt6
pip install PyQt6

# Check dependencies
jarvis --setup
```

### Database issues
```bash
# Check database integrity
jarvis --diagnose

# Attempt repair
jarvis --repair database
```

## License

MIT License - Feel free to use and modify as needed.

## Author

Created by [humayun2000444](https://github.com/humayun2000444) with Claude Code assistance.

---

*"Just A Rather Very Intelligent System"*
