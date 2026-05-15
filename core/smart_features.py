#!/usr/bin/env python3
"""
JARVIS Smart Features Module
- Screen/Clipboard Awareness
- Web Search
- Reminders with Alarms
- Music Control
- File Search & Management
- Note Taking
- System Commands
- Persistent Memory
- Daily Briefing
- Automation Workflows
"""
import os
import sys
import subprocess
import threading
import time
import json
import re
import glob
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from core.logger import get_logger

logger = get_logger("smart_features")

# ============================================================
# 1. SCREEN / CLIPBOARD AWARENESS
# ============================================================

class ScreenAwareness:
    """Capture screen, read clipboard, OCR text from images"""

    def __init__(self):
        self._temp_screenshot = "/tmp/jarvis_screenshot.png"

    def get_clipboard(self) -> str:
        """Get current clipboard text"""
        try:
            result = subprocess.run(
                ['xclip', '-selection', 'clipboard', '-o'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ['xsel', '--clipboard', '--output'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except FileNotFoundError:
                pass
        return ""

    def set_clipboard(self, text: str) -> bool:
        """Set clipboard text"""
        try:
            proc = subprocess.Popen(
                ['xclip', '-selection', 'clipboard'],
                stdin=subprocess.PIPE
            )
            proc.communicate(text.encode())
            return proc.returncode == 0
        except FileNotFoundError:
            try:
                proc = subprocess.Popen(
                    ['xsel', '--clipboard', '--input'],
                    stdin=subprocess.PIPE
                )
                proc.communicate(text.encode())
                return proc.returncode == 0
            except FileNotFoundError:
                return False

    def take_screenshot(self, region: str = "full") -> Optional[str]:
        """Take a screenshot and return the file path"""
        try:
            if region == "full":
                subprocess.run(
                    ['gnome-screenshot', '-f', self._temp_screenshot],
                    capture_output=True, timeout=10
                )
            elif region == "window":
                subprocess.run(
                    ['gnome-screenshot', '-w', '-f', self._temp_screenshot],
                    capture_output=True, timeout=10
                )
            elif region == "area":
                subprocess.run(
                    ['gnome-screenshot', '-a', '-f', self._temp_screenshot],
                    capture_output=True, timeout=10
                )

            if os.path.exists(self._temp_screenshot):
                return self._temp_screenshot
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
        return None

    def ocr_screenshot(self) -> str:
        """Take screenshot and extract text via OCR"""
        path = self.take_screenshot()
        if not path:
            return "Could not take screenshot."

        try:
            result = subprocess.run(
                ['tesseract', path, 'stdout'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return "Could not read text from screen. Make sure tesseract-ocr is installed."
        except FileNotFoundError:
            return "OCR not available. Install with: sudo apt install tesseract-ocr"
        except Exception as e:
            return f"OCR error: {e}"

    def get_active_window_title(self) -> str:
        """Get the title of the active window"""
        try:
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        return ""


# ============================================================
# 2. WEB SEARCH
# ============================================================

class WebSearch:
    """Web search using DuckDuckGo (no API key needed)"""

    DDG_URL = "https://html.duckduckgo.com/html/"

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Search the web and return results"""
        try:
            import requests
            from html import unescape

            response = requests.post(
                self.DDG_URL,
                data={'q': query},
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) JARVIS/1.0'
                },
                timeout=10
            )

            results = []
            # Simple HTML parsing without BeautifulSoup
            text = response.text

            # Find result blocks
            snippets = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</a>',
                text, re.DOTALL
            )
            titles = re.findall(
                r'class="result__a"[^>]*>(.*?)</a>',
                text, re.DOTALL
            )
            urls = re.findall(
                r'class="result__url"[^>]*>(.*?)</a>',
                text, re.DOTALL
            )

            for i in range(min(num_results, len(titles))):
                title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                url = re.sub(r'<[^>]+>', '', urls[i]).strip() if i < len(urls) else ""

                if title:
                    results.append({
                        'title': unescape(title),
                        'snippet': unescape(snippet),
                        'url': url
                    })

            return results

        except ImportError:
            return [{'title': 'Error', 'snippet': 'requests library not installed', 'url': ''}]
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return [{'title': 'Error', 'snippet': str(e), 'url': ''}]

    def search_summary(self, query: str) -> str:
        """Search and return a formatted summary"""
        results = self.search(query)

        if not results:
            return f"No results found for '{query}'."

        if results[0].get('title') == 'Error':
            return f"Search failed: {results[0].get('snippet', 'Unknown error')}"

        summary = f"Search results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
            summary += f"{i}. {r['title']}\n"
            if r['snippet']:
                summary += f"   {r['snippet']}\n"
            if r['url']:
                summary += f"   {r['url']}\n"
            summary += "\n"

        return summary

    def quick_answer(self, query: str) -> str:
        """Try to get a quick answer from DuckDuckGo instant answer API"""
        try:
            import requests

            response = requests.get(
                'https://api.duckduckgo.com/',
                params={'q': query, 'format': 'json', 'no_html': 1},
                timeout=10
            )
            data = response.json()

            # Check for instant answer
            if data.get('AbstractText'):
                source = data.get('AbstractSource', '')
                return f"{data['AbstractText']}\n— {source}"
            elif data.get('Answer'):
                return data['Answer']
            elif data.get('Definition'):
                return data['Definition']

            # Fall back to search
            return self.search_summary(query)

        except Exception:
            return self.search_summary(query)


# ============================================================
# 3. REMINDERS WITH ALARMS
# ============================================================

class ReminderSystem:
    """Timed reminders with audio alerts"""

    def __init__(self, on_reminder: Callable = None):
        self._reminders: List[Dict] = []
        self._lock = threading.Lock()
        self._running = True
        self._callback = on_reminder
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        self._load_reminders()

    def _get_reminders_file(self) -> Path:
        from config.settings import DATA_DIR
        return DATA_DIR / "reminders.json"

    def _load_reminders(self):
        """Load reminders from disk"""
        path = self._get_reminders_file()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self._reminders = [r for r in data if r.get('time', '') > datetime.now().isoformat()]
            except Exception:
                self._reminders = []

    def _save_reminders(self):
        """Save reminders to disk"""
        path = self._get_reminders_file()
        try:
            with open(path, 'w') as f:
                json.dump(self._reminders, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    def add_reminder(self, message: str, minutes: int = 0, hours: int = 0, at_time: str = None) -> str:
        """Add a reminder. Returns confirmation message."""
        if at_time:
            # Parse time like "3:00 PM" or "15:00"
            try:
                today = datetime.now().date()
                for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M', '%I %p', '%I%p']:
                    try:
                        t = datetime.strptime(at_time.strip(), fmt).time()
                        remind_at = datetime.combine(today, t)
                        if remind_at < datetime.now():
                            remind_at += timedelta(days=1)
                        break
                    except ValueError:
                        continue
                else:
                    return f"Couldn't parse time '{at_time}'. Use formats like '3:00 PM' or '15:00'."
            except Exception as e:
                return f"Time parse error: {e}"
        else:
            total_minutes = minutes + (hours * 60)
            if total_minutes <= 0:
                total_minutes = 5  # Default 5 minutes
            remind_at = datetime.now() + timedelta(minutes=total_minutes)

        reminder = {
            'message': message,
            'time': remind_at.isoformat(),
            'created': datetime.now().isoformat(),
            'fired': False
        }

        with self._lock:
            self._reminders.append(reminder)
            self._save_reminders()

        time_str = remind_at.strftime('%I:%M %p')
        return f"Reminder set for {time_str}: {message}"

    def get_pending(self) -> List[Dict]:
        """Get all pending reminders"""
        now = datetime.now().isoformat()
        with self._lock:
            return [r for r in self._reminders if not r.get('fired') and r['time'] > now]

    def _check_loop(self):
        """Background loop to check and fire reminders"""
        while self._running:
            now = datetime.now().isoformat()

            with self._lock:
                for reminder in self._reminders:
                    if not reminder.get('fired') and reminder['time'] <= now:
                        reminder['fired'] = True
                        self._fire_reminder(reminder)
                self._save_reminders()

            time.sleep(10)  # Check every 10 seconds

    def _fire_reminder(self, reminder: Dict):
        """Fire a reminder — play sound and notify"""
        message = reminder['message']
        logger.info(f"Firing reminder: {message}")

        # Play alarm sound
        self._play_alarm()

        # Callback (for GUI/voice)
        if self._callback:
            try:
                self._callback(message)
            except Exception as e:
                logger.error(f"Reminder callback error: {e}")

    def _play_alarm(self):
        """Play an alarm sound"""
        # Try system sounds first
        sound_paths = [
            '/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga',
            '/usr/share/sounds/freedesktop/stereo/complete.oga',
            '/usr/share/sounds/freedesktop/stereo/bell.oga',
            '/usr/share/sounds/gnome/default/alerts/bark.ogg',
        ]

        for sound in sound_paths:
            if os.path.exists(sound):
                try:
                    subprocess.Popen(
                        ['paplay', sound],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return
                except FileNotFoundError:
                    continue

        # Fallback: system bell
        try:
            subprocess.run(['pactl', 'play-sample', 'bell'], capture_output=True)
        except Exception:
            pass

    def stop(self):
        self._running = False


# ============================================================
# 4. MUSIC CONTROL
# ============================================================

class MusicController:
    """Control media playback via MPRIS D-Bus (works with Spotify, VLC, etc.)"""

    def _playerctl(self, *args) -> str:
        """Run playerctl command"""
        try:
            result = subprocess.run(
                ['playerctl'] + list(args),
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return "playerctl not installed. Install with: sudo apt install playerctl"
        except Exception as e:
            return f"Error: {e}"

    def play(self) -> str:
        result = self._playerctl('play')
        return "Playing." if not result else result

    def pause(self) -> str:
        result = self._playerctl('pause')
        return "Paused." if not result else result

    def play_pause(self) -> str:
        result = self._playerctl('play-pause')
        return "Toggled playback." if not result else result

    def next_track(self) -> str:
        self._playerctl('next')
        return f"Next track: {self.now_playing()}"

    def previous_track(self) -> str:
        self._playerctl('previous')
        return f"Previous track: {self.now_playing()}"

    def stop(self) -> str:
        result = self._playerctl('stop')
        return "Stopped." if not result else result

    def now_playing(self) -> str:
        title = self._playerctl('metadata', 'title')
        artist = self._playerctl('metadata', 'artist')
        if title and 'not installed' not in title:
            if artist and 'not installed' not in artist:
                return f"{title} by {artist}"
            return title
        return "Nothing playing."

    def set_volume(self, level: float) -> str:
        """Set volume 0.0 - 1.0"""
        level = max(0.0, min(1.0, level))
        self._playerctl('volume', str(level))
        return f"Volume set to {int(level * 100)}%."

    def status(self) -> str:
        """Get full player status"""
        playing = self.now_playing()
        status = self._playerctl('status')
        vol = self._playerctl('volume')
        return f"Status: {status}\nNow playing: {playing}\nVolume: {vol}"


# ============================================================
# 5. FILE SEARCH & MANAGEMENT
# ============================================================

class FileManager:
    """Search and manage files"""

    HOME = os.path.expanduser("~")

    def find_files(self, name: str, search_dir: str = None, max_results: int = 10) -> List[str]:
        """Find files by name pattern"""
        search_dir = search_dir or self.HOME

        try:
            result = subprocess.run(
                ['find', search_dir, '-maxdepth', '5', '-iname', f'*{name}*',
                 '-not', '-path', '*/.*', '-not', '-path', '*/node_modules/*',
                 '-not', '-path', '*/venv/*', '-not', '-path', '*/__pycache__/*'],
                capture_output=True, text=True, timeout=15
            )
            files = [f for f in result.stdout.strip().split('\n') if f]
            return files[:max_results]
        except Exception as e:
            return [f"Search error: {e}"]

    def find_files_summary(self, name: str) -> str:
        """Search and return formatted results"""
        files = self.find_files(name)
        if not files or (len(files) == 1 and files[0].startswith("Search error")):
            return f"No files found matching '{name}'."

        result = f"Found {len(files)} file(s) matching '{name}':\n"
        for f in files:
            size = ""
            try:
                s = os.path.getsize(f)
                if s > 1024*1024:
                    size = f" ({s/1024/1024:.1f} MB)"
                elif s > 1024:
                    size = f" ({s/1024:.1f} KB)"
            except Exception:
                pass
            result += f"  - {f}{size}\n"
        return result

    def list_recent_downloads(self, count: int = 10) -> str:
        """List recent files in Downloads"""
        dl_dir = os.path.join(self.HOME, "Downloads")
        if not os.path.isdir(dl_dir):
            return "Downloads folder not found."

        files = []
        for f in os.listdir(dl_dir):
            path = os.path.join(dl_dir, f)
            if os.path.isfile(path):
                mtime = os.path.getmtime(path)
                size = os.path.getsize(path)
                files.append((f, mtime, size))

        files.sort(key=lambda x: x[1], reverse=True)

        if not files:
            return "No files in Downloads."

        result = "Recent downloads:\n"
        for name, mtime, size in files[:count]:
            date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            if size > 1024*1024:
                size_str = f"{size/1024/1024:.1f} MB"
            elif size > 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size} B"
            result += f"  - {name} ({size_str}, {date})\n"
        return result

    def get_disk_usage(self, path: str = None) -> str:
        """Get disk usage summary"""
        path = path or self.HOME
        usage = shutil.disk_usage(path)
        total = usage.total / (1024**3)
        used = usage.used / (1024**3)
        free = usage.free / (1024**3)
        pct = (usage.used / usage.total) * 100
        return f"Disk usage: {used:.1f} GB used / {total:.1f} GB total ({pct:.1f}%), {free:.1f} GB free"

    def open_file(self, path: str) -> str:
        """Open a file with the default application"""
        if os.path.exists(path):
            try:
                subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Opened {os.path.basename(path)}."
            except Exception as e:
                return f"Error opening file: {e}"
        return f"File not found: {path}"


# ============================================================
# 6. NOTE TAKING
# ============================================================

class NoteTaker:
    """Quick note-taking system backed by database"""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            from core.database import get_db
            self._db = get_db()
        return self._db

    def _ensure_table(self):
        """Create notes table if not exists"""
        with self.db.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_note(self, content: str, tags: str = None) -> str:
        """Save a note"""
        self._ensure_table()
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO notes (content, tags) VALUES (?, ?)',
                (content.strip(), tags)
            )
            note_id = cursor.lastrowid
        return f"Note #{note_id} saved."

    def search_notes(self, query: str) -> str:
        """Search notes"""
        self._ensure_table()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, created_at FROM notes WHERE content LIKE ? ORDER BY created_at DESC LIMIT 10",
                (f'%{query}%',)
            )
            rows = cursor.fetchall()

        if not rows:
            return f"No notes found matching '{query}'."

        result = f"Notes matching '{query}':\n"
        for row in rows:
            date = row['created_at'][:16] if row['created_at'] else ""
            result += f"  #{row['id']} [{date}] {row['content'][:100]}\n"
        return result

    def list_recent(self, count: int = 10) -> str:
        """List recent notes"""
        self._ensure_table()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, created_at FROM notes ORDER BY created_at DESC LIMIT ?",
                (count,)
            )
            rows = cursor.fetchall()

        if not rows:
            return "No notes yet."

        result = "Recent notes:\n"
        for row in rows:
            date = row['created_at'][:16] if row['created_at'] else ""
            result += f"  #{row['id']} [{date}] {row['content'][:100]}\n"
        return result

    def delete_note(self, note_id: int) -> str:
        """Delete a note"""
        self._ensure_table()
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            if cursor.rowcount > 0:
                return f"Note #{note_id} deleted."
        return f"Note #{note_id} not found."


# ============================================================
# 7. SYSTEM COMMANDS
# ============================================================

class SystemController:
    """Execute system commands by voice"""

    def get_system_info(self) -> str:
        """Get comprehensive system info"""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot

            info = f"System Status:\n"
            info += f"  CPU: {cpu}%\n"
            info += f"  RAM: {mem.percent}% ({mem.used/1024**3:.1f}/{mem.total/1024**3:.1f} GB)\n"
            info += f"  Disk: {disk.percent}% ({disk.used/1024**3:.1f}/{disk.total/1024**3:.1f} GB)\n"
            info += f"  Uptime: {str(uptime).split('.')[0]}\n"

            # Top processes
            procs = sorted(psutil.process_iter(['name', 'cpu_percent', 'memory_percent']),
                          key=lambda p: p.info.get('cpu_percent', 0) or 0, reverse=True)[:5]
            info += f"\nTop processes:\n"
            for p in procs:
                info += f"  - {p.info['name']}: CPU {p.info.get('cpu_percent', 0):.1f}%, RAM {p.info.get('memory_percent', 0):.1f}%\n"

            return info
        except ImportError:
            return "psutil not installed."

    def kill_process(self, name: str) -> str:
        """Kill a process by name"""
        try:
            result = subprocess.run(['pkill', '-f', name], capture_output=True, text=True)
            if result.returncode == 0:
                return f"Killed process: {name}"
            return f"No process found matching '{name}'."
        except Exception as e:
            return f"Error: {e}"

    def set_brightness(self, level: int) -> str:
        """Set screen brightness (0-100)"""
        level = max(0, min(100, level))
        try:
            # Try xrandr
            result = subprocess.run(['xrandr', '--output', 'eDP-1', '--brightness', str(level/100)],
                                   capture_output=True, text=True)
            if result.returncode == 0:
                return f"Brightness set to {level}%."

            # Try brightnessctl
            result = subprocess.run(['brightnessctl', 'set', f'{level}%'],
                                   capture_output=True, text=True)
            if result.returncode == 0:
                return f"Brightness set to {level}%."

            return "Could not set brightness."
        except FileNotFoundError:
            return "No brightness control available."

    def get_wifi_status(self) -> str:
        """Get WiFi status"""
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'],
                                   capture_output=True, text=True, timeout=10)
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes:'):
                    ssid = line.split(':', 1)[1]
                    return f"Connected to WiFi: {ssid}"
            return "Not connected to WiFi."
        except FileNotFoundError:
            return "nmcli not available."

    def get_battery(self) -> str:
        """Get battery status"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                status = "charging" if battery.power_plugged else "discharging"
                time_left = ""
                if battery.secsleft > 0 and not battery.power_plugged:
                    hours = battery.secsleft // 3600
                    mins = (battery.secsleft % 3600) // 60
                    time_left = f", {hours}h {mins}m remaining"
                return f"Battery: {battery.percent}% ({status}{time_left})"
            return "No battery detected (desktop PC?)."
        except ImportError:
            return "psutil not installed."

    def shutdown(self, action: str = "shutdown") -> str:
        """Shutdown, restart, or sleep"""
        if action == "shutdown":
            subprocess.Popen(['systemctl', 'poweroff'])
            return "Shutting down..."
        elif action == "restart":
            subprocess.Popen(['systemctl', 'reboot'])
            return "Restarting..."
        elif action == "sleep":
            subprocess.Popen(['systemctl', 'suspend'])
            return "Going to sleep..."
        elif action == "logout":
            subprocess.Popen(['gnome-session-quit', '--logout', '--no-prompt'])
            return "Logging out..."
        return f"Unknown action: {action}"

    def get_ip_address(self) -> str:
        """Get IP addresses"""
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
            ips = result.stdout.strip()
            return f"IP address(es): {ips}" if ips else "No network connection."
        except Exception:
            return "Could not get IP address."


# ============================================================
# 8. PERSISTENT MEMORY
# ============================================================

class PersistentMemory:
    """Remember facts and recall them across conversations"""

    def __init__(self):
        self._db = None
        self._ensure_table()

    @property
    def db(self):
        if self._db is None:
            from core.database import get_db
            self._db = get_db()
        return self._db

    def _ensure_table(self):
        try:
            with self.db.get_connection() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        category TEXT DEFAULT 'general',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Memory table error: {e}")

    def remember(self, key: str, value: str, category: str = "general") -> str:
        """Store a memory"""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            # Update if exists, else insert
            cursor.execute('SELECT id FROM memories WHERE key = ?', (key.lower(),))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    'UPDATE memories SET value = ?, category = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (value, category, existing['id'])
                )
                return f"Updated memory: {key}"
            else:
                cursor.execute(
                    'INSERT INTO memories (key, value, category) VALUES (?, ?, ?)',
                    (key.lower(), value, category)
                )
                return f"I'll remember that: {key} = {value}"

    def recall(self, query: str) -> str:
        """Recall a memory"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Exact match first
            cursor.execute('SELECT value FROM memories WHERE key = ?', (query.lower(),))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    'UPDATE memories SET last_accessed = CURRENT_TIMESTAMP WHERE key = ?',
                    (query.lower(),)
                )
                conn.commit()
                return row['value']

            # Fuzzy search
            cursor.execute(
                'SELECT key, value FROM memories WHERE key LIKE ? OR value LIKE ? LIMIT 5',
                (f'%{query.lower()}%', f'%{query.lower()}%')
            )
            rows = cursor.fetchall()
            if rows:
                result = "Here's what I remember:\n"
                for r in rows:
                    result += f"  - {r['key']}: {r['value']}\n"
                return result

        return f"I don't have any memory about '{query}'."

    def list_memories(self, category: str = None) -> str:
        """List all memories"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    'SELECT key, value, category FROM memories WHERE category = ? ORDER BY created_at DESC',
                    (category,)
                )
            else:
                cursor.execute('SELECT key, value, category FROM memories ORDER BY created_at DESC LIMIT 20')
            rows = cursor.fetchall()

        if not rows:
            return "No memories stored yet."

        result = "My memories:\n"
        for r in rows:
            result += f"  - [{r['category']}] {r['key']}: {r['value']}\n"
        return result

    def forget(self, key: str) -> str:
        """Delete a memory"""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM memories WHERE key = ?', (key.lower(),))
            if cursor.rowcount > 0:
                return f"Forgotten: {key}"
        return f"No memory found for '{key}'."

    def get_context_for_ai(self) -> str:
        """Get relevant memories as context for AI responses"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM memories ORDER BY last_accessed DESC NULLS LAST LIMIT 10')
            rows = cursor.fetchall()

        if not rows:
            return ""

        context = "User memories:\n"
        for r in rows:
            context += f"- {r['key']}: {r['value']}\n"
        return context


# ============================================================
# 9. DAILY BRIEFING
# ============================================================

class DailyBriefing:
    """Generate comprehensive daily briefing"""

    def generate(self) -> str:
        """Generate morning briefing"""
        parts = []
        now = datetime.now()

        # Greeting
        hour = now.hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        from config.settings import USER_NAME
        parts.append(f"{greeting}, {USER_NAME}! Here's your daily briefing for {now.strftime('%A, %B %d')}.")
        parts.append("")

        # Weather
        try:
            from core.weather import get_weather_service
            weather = get_weather_service()
            data = weather.get_weather()
            if data.get('success'):
                curr = data['current']
                loc = data['location']
                parts.append(f"Weather in {loc['city']}: {curr['description']}, {curr['temperature_c']}°C (feels like {curr['feels_like_c']}°C)")
        except Exception:
            pass

        # Tasks
        try:
            from core.database import get_db
            db = get_db()
            tasks = db.get_pending_tasks()
            high = [t for t in tasks if t['priority'] == 'high']

            if tasks:
                parts.append(f"\nYou have {len(tasks)} pending task(s).")
                if high:
                    parts.append(f"  High priority:")
                    for t in high[:3]:
                        parts.append(f"    - {t['title']}")
            else:
                parts.append("\nNo pending tasks. Your slate is clean!")
        except Exception:
            pass

        # Reminders
        try:
            reminder_sys = get_reminder_system()
            pending = reminder_sys.get_pending()
            if pending:
                parts.append(f"\nUpcoming reminders:")
                for r in pending[:3]:
                    t = datetime.fromisoformat(r['time']).strftime('%I:%M %p')
                    parts.append(f"  - {t}: {r['message']}")
        except Exception:
            pass

        # System
        try:
            ctrl = SystemController()
            wifi = ctrl.get_wifi_status()
            battery = ctrl.get_battery()
            parts.append(f"\n{wifi}")
            parts.append(battery)
        except Exception:
            pass

        # Motivation
        try:
            from core.features import DailyMotivation
            quote, author = DailyMotivation.get_daily_quote()
            parts.append(f'\n"{quote}" — {author}')
        except Exception:
            pass

        return "\n".join(parts)


# ============================================================
# 10. AUTOMATION WORKFLOWS / MACROS
# ============================================================

class AutomationEngine:
    """Custom voice-triggered action sequences"""

    def __init__(self):
        self._workflows: Dict[str, List[Dict]] = {}
        self._load_workflows()

    def _get_workflows_file(self) -> Path:
        from config.settings import DATA_DIR
        return DATA_DIR / "workflows.json"

    def _load_workflows(self):
        path = self._get_workflows_file()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    self._workflows = json.load(f)
            except Exception:
                self._workflows = {}

    def _save_workflows(self):
        path = self._get_workflows_file()
        try:
            with open(path, 'w') as f:
                json.dump(self._workflows, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save workflows: {e}")

    def create_workflow(self, name: str, steps: List[Dict]) -> str:
        """Create a new workflow"""
        self._workflows[name.lower()] = steps
        self._save_workflows()
        return f"Workflow '{name}' created with {len(steps)} steps."

    def run_workflow(self, name: str) -> str:
        """Execute a workflow"""
        name_lower = name.lower()
        if name_lower not in self._workflows:
            return f"Workflow '{name}' not found."

        steps = self._workflows[name_lower]
        results = []

        for step in steps:
            action = step.get('action', '')
            param = step.get('param', '')

            try:
                if action == 'launch':
                    from core.features import QuickCommands
                    success, msg = QuickCommands.launch_arbitrary_app(f"open {param}")
                    results.append(msg)
                elif action == 'volume':
                    subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', param], capture_output=True)
                    results.append(f"Volume: {param}")
                elif action == 'mute':
                    subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', 'toggle'], capture_output=True)
                    results.append("Toggled mute.")
                elif action == 'brightness':
                    ctrl = SystemController()
                    results.append(ctrl.set_brightness(int(param)))
                elif action == 'lock':
                    subprocess.run(['gnome-screensaver-command', '-l'], capture_output=True)
                    results.append("Screen locked.")
                elif action == 'say':
                    results.append(param)
                elif action == 'wait':
                    time.sleep(float(param))
                    results.append(f"Waited {param}s.")
                elif action == 'notify':
                    try:
                        subprocess.run(['notify-send', 'JARVIS', param], capture_output=True)
                    except Exception:
                        pass
                    results.append(f"Notification: {param}")
                elif action == 'shutdown':
                    ctrl = SystemController()
                    results.append(ctrl.shutdown(param))
                elif action == 'kill':
                    ctrl = SystemController()
                    results.append(ctrl.kill_process(param))
                else:
                    results.append(f"Unknown action: {action}")
            except Exception as e:
                results.append(f"Step error: {e}")

        return f"Workflow '{name}' completed:\n" + "\n".join(f"  - {r}" for r in results)

    def list_workflows(self) -> str:
        """List all workflows"""
        if not self._workflows:
            return "No workflows defined. Create one with: 'create workflow goodnight: lock screen, mute volume'"

        result = "Workflows:\n"
        for name, steps in self._workflows.items():
            actions = ", ".join(s.get('action', '?') for s in steps)
            result += f"  - {name}: {actions}\n"
        return result

    def delete_workflow(self, name: str) -> str:
        """Delete a workflow"""
        if name.lower() in self._workflows:
            del self._workflows[name.lower()]
            self._save_workflows()
            return f"Workflow '{name}' deleted."
        return f"Workflow '{name}' not found."

    # Pre-built workflows
    DEFAULT_WORKFLOWS = {
        'goodnight': [
            {'action': 'say', 'param': 'Goodnight! Locking screen and muting volume.'},
            {'action': 'mute', 'param': ''},
            {'action': 'lock', 'param': ''},
        ],
        'work mode': [
            {'action': 'say', 'param': 'Starting work mode.'},
            {'action': 'launch', 'param': 'google-chrome-stable'},
            {'action': 'launch', 'param': 'code'},
            {'action': 'launch', 'param': 'gnome-terminal'},
        ],
        'break time': [
            {'action': 'say', 'param': 'Time for a break! Stretch and hydrate.'},
            {'action': 'notify', 'param': 'Break time! Stand up and stretch.'},
        ],
    }

    def install_defaults(self):
        """Install default workflows if none exist"""
        if not self._workflows:
            self._workflows = dict(self.DEFAULT_WORKFLOWS)
            self._save_workflows()


# ============================================================
# SINGLETON INSTANCES
# ============================================================

_screen = None
_search = None
_reminders = None
_music = None
_files = None
_notes = None
_system = None
_memory = None
_briefing = None
_automation = None


def get_screen() -> ScreenAwareness:
    global _screen
    if _screen is None:
        _screen = ScreenAwareness()
    return _screen

def get_web_search() -> WebSearch:
    global _search
    if _search is None:
        _search = WebSearch()
    return _search

def get_reminder_system(callback=None) -> ReminderSystem:
    global _reminders
    if _reminders is None:
        _reminders = ReminderSystem(on_reminder=callback)
    return _reminders

def get_music() -> MusicController:
    global _music
    if _music is None:
        _music = MusicController()
    return _music

def get_file_manager() -> FileManager:
    global _files
    if _files is None:
        _files = FileManager()
    return _files

def get_notes() -> NoteTaker:
    global _notes
    if _notes is None:
        _notes = NoteTaker()
    return _notes

def get_system_controller() -> SystemController:
    global _system
    if _system is None:
        _system = SystemController()
    return _system

def get_memory() -> PersistentMemory:
    global _memory
    if _memory is None:
        _memory = PersistentMemory()
    return _memory

def get_briefing() -> DailyBriefing:
    global _briefing
    if _briefing is None:
        _briefing = DailyBriefing()
    return _briefing

def get_automation() -> AutomationEngine:
    global _automation
    if _automation is None:
        _automation = AutomationEngine()
        _automation.install_defaults()
    return _automation
