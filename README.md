# JARVIS - Personal AI Assistant

A robust, Iron Man-inspired personal AI assistant with both GUI and CLI interfaces. JARVIS helps you manage tasks, track daily activities, and provides intelligent suggestions based on your behavior patterns.

## Features

- **Task Management** - Add, complete, and track tasks with priorities
- **Activity Logging** - Log daily work activities with duration tracking
- **Daily Summaries** - Automatic end-of-day productivity summaries
- **Pattern Learning** - Learns from your daily routine and provides suggestions
- **Voice Output** - Text-to-speech notifications (optional)
- **Desktop Notifications** - System notifications for reminders
- **Pomodoro Timer** - Built-in focus timer with breaks
- **Health Reminders** - Water, posture, eye strain, and stretch reminders
- **System Monitoring** - Real-time CPU, RAM, Disk, and Battery status
- **Local AI** - Uses Ollama for privacy-focused local AI processing

## Screenshots

The GUI features an Iron Man-inspired interface with:
- Animated Arc Reactor
- Dark HUD theme with cyan/blue glow
- System monitoring panels
- Command palette (Ctrl+K)

## Installation

### Prerequisites

- Python 3.8+
- Ollama (for AI features)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/jarvis.git
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

### Quick Commands
```bash
jarvis --welcome     # Show welcome message
jarvis --summary     # Show daily summary
jarvis --health      # Check system health
jarvis --diagnose    # Run full diagnostics
jarvis --setup       # Run initial setup
```

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

# Other
/help               # Show all commands
/quit               # Exit JARVIS
```

## Configuration

Edit `config/settings.py` to customize:

```python
# AI Model (Ollama)
AI_MODEL = "llama3.2:1b"

# Work hours
WORK_START_HOUR = 9
WORK_END_HOUR = 17

# Reminder intervals
REMINDER_INTERVAL_MINUTES = 30

# Features
ENABLE_VOICE = True
ENABLE_DESKTOP_NOTIFICATIONS = True
```

## Project Structure

```
jarvis/
├── jarvis.py           # Main entry point
├── install.sh          # Installation script
├── requirements.txt    # Python dependencies
├── config/
│   └── settings.py     # Configuration
├── core/
│   ├── database.py     # SQLite database
│   ├── ai_engine.py    # Ollama AI integration
│   ├── scheduler.py    # Task scheduler
│   ├── features.py     # System monitor, Pomodoro, etc.
│   ├── health.py       # Health checks & diagnostics
│   └── logger.py       # Logging system
├── cli/
│   └── main.py         # CLI interface
├── gui/
│   └── main_window.py  # PyQt6 GUI
└── data/
    ├── jarvis.db       # SQLite database
    └── logs/           # Log files
```

## Health & Diagnostics

JARVIS includes a comprehensive health monitoring system:

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
- pyttsx3 - Text-to-speech
- plyer - Desktop notifications
- psutil - System monitoring

## Troubleshooting

### Ollama not working
```bash
# Start Ollama service
ollama serve

# Pull the model
ollama pull llama3.2:1b
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

Created with Claude Code assistance.

---

*"Just A Rather Very Intelligent System"*
