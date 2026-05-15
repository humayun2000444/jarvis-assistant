# JARVIS - Personal AI Assistant

A robust, Iron Man-inspired personal AI assistant with wake word activation, two-way voice conversation, and 30+ smart features. Built with Python, Ollama, and PyQt6.

Say **"Hey Jarvis"** and start talking — it listens, responds, launches apps, searches the web, sets reminders, controls music, manages files, takes notes, and much more.

## Features

### Core
- **"Hey Jarvis" Wake Word** - Always listening, activates hands-free
- **Voice Conversation** - Natural two-way voice conversation with speak-back
- **App Launcher** - Open any installed app by voice ("open Chrome", "launch VS Code")
- **Local AI** - Privacy-focused, runs entirely on your machine via Ollama
- **Multi-Model Support** - Switch between Ollama models with `--model` flag

### Smart Features
- **Web Search** - "Search for Python tutorials" — real-time DuckDuckGo search with AI answers
- **Screen Awareness** - "What's on my screen?" — OCR reads text from your screen
- **Clipboard** - "What did I copy?" — read and manage clipboard contents
- **Reminders & Alarms** - "Remind me in 30 minutes to call mom" — timed audio alerts
- **Music Control** - "Play music", "Next song", "What's playing?" — controls Spotify/VLC via MPRIS
- **File Search** - "Find my resume", "Show downloads" — search files across your system
- **Note Taking** - "Take a note: meeting at 4pm" — voice notes stored in database
- **Persistent Memory** - "Remember that my birthday is March 5" / "What's my birthday?" — remembers facts forever
- **System Control** - "System info", "Kill Chrome", "Battery status", "Brightness 50"
- **Daily Briefing** - "Brief me" — weather + tasks + reminders + system status + quote
- **Automation Workflows** - "Goodnight" (locks + mutes), "Work mode" (opens Chrome + VS Code + Terminal)

### Productivity
- **Task Management** - Add, complete, and track tasks with priorities and due dates
- **Activity Logging** - Log daily work activities with duration tracking
- **Daily Summaries** - Automatic end-of-day productivity summaries
- **Pattern Learning** - Learns from your routine and provides suggestions
- **Pomodoro Timer** - Built-in focus timer with breaks
- **Health Reminders** - Water, posture, eye strain, and stretch reminders

### Interface
- **Iron Man GUI** - Animated Arc Reactor, dark HUD theme, system monitoring panels
- **CLI Mode** - Rich interactive terminal with 20+ slash commands
- **Background Daemon** - Scheduled tasks, reminders, and notifications
- **Plugin System** - Extend JARVIS with custom plugins
- **YAML Config** - User-customizable settings

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

### Optional dependencies for full features
```bash
# Screen OCR
sudo apt install tesseract-ocr

# Clipboard
sudo apt install xclip

# Music control
sudo apt install playerctl

# Window detection
sudo apt install xdotool
```

## Usage

### GUI Mode (Iron Man Style Interface)
```bash
jarvis --gui
```

### CLI Mode (Interactive Terminal)
```bash
jarvis
```

### Voice Mode (Terminal-based)
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

## Voice Commands

Say **"Hey Jarvis"** to wake up, then speak naturally:

| Category | Voice Command | Action |
|----------|--------------|--------|
| **Apps** | "Open Chrome" | Launches Google Chrome |
| **Apps** | "Start VS Code" | Launches Visual Studio Code |
| **Apps** | "Open terminal" | Opens terminal |
| **Search** | "Search for machine learning" | Web search with results |
| **Search** | "What is Docker?" | Instant answer |
| **Reminders** | "Remind me in 30 minutes to stretch" | Timed alarm |
| **Reminders** | "Remind me at 3pm to check email" | Alarm at specific time |
| **Music** | "Play music" / "Pause" | Media playback control |
| **Music** | "Next song" / "Previous song" | Track navigation |
| **Music** | "What's playing?" | Shows current track |
| **Files** | "Find my resume" | Searches your files |
| **Files** | "Show downloads" | Lists recent downloads |
| **Files** | "Disk usage" | Shows storage info |
| **Notes** | "Take a note: buy groceries" | Saves a note |
| **Notes** | "Show my notes" | Lists notes |
| **Notes** | "Search notes for meeting" | Searches notes |
| **Memory** | "Remember my favorite color is blue" | Stores fact |
| **Memory** | "What's my favorite color?" | Recalls fact |
| **Memory** | "Forget my favorite color" | Deletes fact |
| **System** | "System info" | CPU, RAM, disk, processes |
| **System** | "Battery status" | Battery level |
| **System** | "Kill process firefox" | Force kills app |
| **System** | "Brightness 70" | Sets brightness |
| **System** | "What's my IP?" | Shows IP address |
| **Screen** | "What's on my screen?" | OCR reads screen |
| **Clipboard** | "What did I copy?" | Shows clipboard |
| **Briefing** | "Daily briefing" | Full status report |
| **Workflows** | "Goodnight" | Mutes + locks screen |
| **Workflows** | "Work mode" | Opens Chrome + VS Code + Terminal |
| **Workflows** | "Break time" | Break notification |
| **Weather** | "What's the weather?" | Current weather |
| **Tasks** | "Show my tasks" | Lists pending tasks |
| **Convo** | "Goodbye" | Ends conversation mode |

## CLI Commands

```bash
# Tasks
/tasks              # List pending tasks
/add <task>         # Add a new task
/done <id>          # Complete a task

# Activity
/log <activity>     # Log an activity
/today              # Show today's activities

# Smart Features
/search <query>     # Search the web
/note <text>        # Save a note
/notes              # List notes
/remind <text>      # Set a reminder
/reminders          # List reminders
/music [cmd]        # Music control (play/pause/next/prev/status)
/system             # System info
/briefing           # Daily briefing
/remember <fact>    # Store a memory
/recall <query>     # Recall a memory
/workflows          # List workflows

# Reports
/summary            # Daily summary
/stats              # Productivity stats
/suggest            # Behavior suggestions
/weather [city]     # Weather info

# Other
/help               # Show all commands
exit                # Exit JARVIS
```

## Configuration

Create `data/user_config.yaml` to customize:

```yaml
AI_MODEL: "llama3.2:1b"
AI_TEMPERATURE: 0.7
USER_NAME: "Tony"
ASSISTANT_NAME: "Jarvis"
WORK_START_HOUR: 9
WORK_END_HOUR: 17
ENABLE_VOICE: true
ENABLE_DESKTOP_NOTIFICATIONS: true
```

## Project Structure

```
jarvis/
├── jarvis.py              # Main entry point
├── pyproject.toml          # Python project config
├── config/
│   └── settings.py         # Config with YAML override
├── core/
│   ├── ai_engine.py        # Ollama AI + smart feature routing
│   ├── smart_features.py   # 10 smart feature modules
│   ├── database.py         # SQLite with connection pooling
│   ├── features.py         # System monitor, TTS, Pomodoro, App launcher
│   ├── voice_assistant.py  # Voice conversation + wake word
│   ├── weather.py          # Weather service
│   ├── scheduler.py        # Background task scheduler
│   ├── health.py           # Health checks & diagnostics
│   └── logger.py           # Logging system
├── cli/
│   └── main.py             # CLI with 20+ commands
├── gui/
│   └── main_window.py      # PyQt6 GUI + wake word listener
├── plugins/
│   └── loader.py           # Plugin system
├── tests/
│   ├── test_database.py    # 27 database tests
│   └── test_ai_engine.py   # 17 AI engine tests
└── data/
    ├── jarvis.db           # SQLite database
    ├── reminders.json      # Persistent reminders
    ├── workflows.json      # Custom workflows
    └── user_config.yaml    # User config
```

## Keyboard Shortcuts (GUI)

| Shortcut | Action |
|----------|--------|
| `Ctrl+J` | Toggle voice conversation mode |
| `Ctrl+K` | Open command palette |
| `Ctrl+M` | Toggle voice output |
| `Ctrl+Q` | Quit application |

## Plugins

Create plugins in the `plugins/` directory:

```python
# plugins/my_plugin.py
def register(app):
    app['commands']['greet'] = {
        'description': 'Say hello',
        'handler': lambda args: print("Hello from my plugin!")
    }
```

## Testing

```bash
pytest tests/ -v    # Run all 44 tests
```

## Tech Stack

- **Python 3.8+** - Core language
- **Ollama** - Local LLM (llama3.2, mistral, etc.)
- **PyQt6** - GUI framework
- **Edge TTS** - Neural text-to-speech (British accent)
- **SpeechRecognition** - Voice input
- **SQLite** - Database with connection pooling
- **APScheduler** - Background task scheduling
- **DuckDuckGo** - Web search (no API key needed)
- **Tesseract** - OCR for screen reading
- **playerctl** - Media playback control

## License

MIT License - Feel free to use and modify.

## Author

Created by [humayun2000444](https://github.com/humayun2000444) with Claude Code assistance.

---

*"Just A Rather Very Intelligent System"*
