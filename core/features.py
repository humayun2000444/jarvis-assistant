#!/usr/bin/env python3
"""
JARVIS Advanced Features Module
- System Monitor
- Voice Output
- Pomodoro Timer
- Health Reminders
- Ambient Sounds
- Quick Commands
- Daily Motivation
- App Usage Tracking
"""
import os
import sys
import threading
import time
import random
import subprocess
from datetime import datetime, timedelta
from typing import Callable, Optional

# System monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Voice output
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class SystemMonitor:
    """Real-time system monitoring"""

    @staticmethod
    def get_cpu_percent() -> float:
        if PSUTIL_AVAILABLE:
            return psutil.cpu_percent(interval=0.1)
        return 0.0

    @staticmethod
    def get_memory_percent() -> float:
        if PSUTIL_AVAILABLE:
            return psutil.virtual_memory().percent
        return 0.0

    @staticmethod
    def get_disk_percent() -> float:
        if PSUTIL_AVAILABLE:
            return psutil.disk_usage('/').percent
        return 0.0

    @staticmethod
    def get_network_speed() -> dict:
        if PSUTIL_AVAILABLE:
            net = psutil.net_io_counters()
            return {
                'bytes_sent': net.bytes_sent,
                'bytes_recv': net.bytes_recv
            }
        return {'bytes_sent': 0, 'bytes_recv': 0}

    @staticmethod
    def get_battery_status() -> dict:
        if PSUTIL_AVAILABLE and hasattr(psutil, 'sensors_battery'):
            battery = psutil.sensors_battery()
            if battery:
                return {
                    'percent': battery.percent,
                    'plugged': battery.power_plugged,
                    'time_left': battery.secsleft if battery.secsleft > 0 else None
                }
        return {'percent': 100, 'plugged': True, 'time_left': None}

    @staticmethod
    def get_all_stats() -> dict:
        return {
            'cpu': SystemMonitor.get_cpu_percent(),
            'memory': SystemMonitor.get_memory_percent(),
            'disk': SystemMonitor.get_disk_percent(),
            'network': SystemMonitor.get_network_speed(),
            'battery': SystemMonitor.get_battery_status()
        }


class VoiceEngine:
    """Human-like text-to-speech engine using Edge TTS neural voices"""

    # Natural-sounding voice options (Microsoft Neural Voices)
    VOICES = {
        'jarvis': 'en-GB-RyanNeural',        # British male - JARVIS style
        'jarvis_us': 'en-US-GuyNeural',      # American male
        'female': 'en-US-JennyNeural',        # American female
        'british_female': 'en-GB-SoniaNeural', # British female
    }

    def __init__(self):
        self.enabled = True
        self.speaking = False
        self.voice = self.VOICES['jarvis']  # Default JARVIS voice
        self.rate = "+0%"  # Speech rate adjustment
        self.pitch = "+0Hz"  # Pitch adjustment
        self._process = None
        self._temp_file = "/tmp/jarvis_speech.mp3"

        # Check if edge-tts is available
        try:
            import edge_tts
            self.edge_tts_available = True
        except ImportError:
            self.edge_tts_available = False

        # Persistent asyncio event loop for edge-tts
        self._async_loop = None
        self._async_thread = None
        if self.edge_tts_available:
            self._start_async_loop()

        # Fallback to pyttsx3 if edge-tts not available
        self.pyttsx_engine = None
        if not self.edge_tts_available and TTS_AVAILABLE:
            try:
                self.pyttsx_engine = pyttsx3.init()
                voices = self.pyttsx_engine.getProperty('voices')
                for voice in voices:
                    if 'male' in voice.name.lower():
                        self.pyttsx_engine.setProperty('voice', voice.id)
                        break
                self.pyttsx_engine.setProperty('rate', 175)
            except Exception:
                pass

    def _start_async_loop(self):
        """Start a persistent asyncio event loop on a background thread"""
        import asyncio

        def _run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=_run_loop, args=(self._async_loop,), daemon=True)
        self._async_thread.start()

    def set_voice(self, voice_name: str):
        """Set the voice to use"""
        if voice_name in self.VOICES:
            self.voice = self.VOICES[voice_name]
        elif voice_name.startswith('en-'):
            self.voice = voice_name

    def set_rate(self, rate: int):
        """Set speech rate (-50 to +50 percent)"""
        rate = max(-50, min(50, rate))
        self.rate = f"{'+' if rate >= 0 else ''}{rate}%"

    def set_pitch(self, pitch: int):
        """Set pitch adjustment in Hz (-50 to +50)"""
        pitch = max(-50, min(50, pitch))
        self.pitch = f"{'+' if pitch >= 0 else ''}{pitch}Hz"

    def speak(self, text: str, block: bool = False):
        """Speak text with human-like voice"""
        if not self.enabled:
            return

        def _speak_edge():
            self.speaking = True
            try:
                import edge_tts
                import asyncio

                async def generate_and_play():
                    communicate = edge_tts.Communicate(
                        text,
                        self.voice,
                        rate=self.rate,
                        pitch=self.pitch
                    )
                    await communicate.save(self._temp_file)

                    # Play using available audio player
                    players = ['mpv', 'ffplay', 'aplay', 'paplay']
                    for player in players:
                        try:
                            if player == 'mpv':
                                cmd = ['mpv', '--no-video', '--really-quiet', self._temp_file]
                            elif player == 'ffplay':
                                cmd = ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', self._temp_file]
                            else:
                                cmd = [player, self._temp_file]

                            self._process = subprocess.Popen(
                                cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                            self._process.wait()
                            break
                        except FileNotFoundError:
                            continue

                # Use persistent event loop
                if self._async_loop and self._async_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(generate_and_play(), self._async_loop)
                    future.result(timeout=30)
                else:
                    # Fallback if loop not available
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(generate_and_play())
                    finally:
                        loop.close()

            except Exception as e:
                print(f"Voice error: {e}")
            finally:
                self.speaking = False
                # Cleanup temp file
                try:
                    if os.path.exists(self._temp_file):
                        os.remove(self._temp_file)
                except Exception:
                    pass

        def _speak_pyttsx():
            self.speaking = True
            try:
                self.pyttsx_engine.say(text)
                self.pyttsx_engine.runAndWait()
            except:
                pass
            self.speaking = False

        # Choose speech method
        if self.edge_tts_available:
            speak_func = _speak_edge
        elif self.pyttsx_engine:
            speak_func = _speak_pyttsx
        else:
            return

        if block:
            speak_func()
        else:
            thread = threading.Thread(target=speak_func)
            thread.daemon = True
            thread.start()

    def speak_ssml(self, ssml_text: str, block: bool = False):
        """Speak using SSML for advanced control (pauses, emphasis, etc.)"""
        if not self.enabled or not self.edge_tts_available:
            # Fallback to regular speak
            import re
            plain_text = re.sub('<[^>]+>', '', ssml_text)
            self.speak(plain_text, block)
            return

        def _speak_ssml():
            self.speaking = True
            try:
                import edge_tts
                import asyncio

                async def generate_and_play():
                    communicate = edge_tts.Communicate(ssml_text, self.voice)
                    await communicate.save(self._temp_file)

                    subprocess.run(
                        ['mpv', '--no-video', '--really-quiet', self._temp_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                # Use persistent event loop
                if self._async_loop and self._async_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(generate_and_play(), self._async_loop)
                    future.result(timeout=30)
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(generate_and_play())
                    finally:
                        loop.close()

            except Exception:
                pass
            finally:
                self.speaking = False

        if block:
            _speak_ssml()
        else:
            thread = threading.Thread(target=_speak_ssml)
            thread.daemon = True
            thread.start()

    def stop(self):
        """Stop speaking"""
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        if self.pyttsx_engine:
            try:
                self.pyttsx_engine.stop()
            except Exception:
                pass
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        self.speaking = False

    def toggle(self):
        """Toggle voice on/off"""
        self.enabled = not self.enabled
        return self.enabled

    def get_available_voices(self) -> dict:
        """Get available voice options"""
        return self.VOICES.copy()

    def test_voice(self):
        """Test the current voice"""
        self.speak("Hello, I am JARVIS, your personal AI assistant. How may I help you today?", block=True)


class PomodoroTimer:
    """Pomodoro technique timer"""

    def __init__(self, on_tick: Callable = None, on_complete: Callable = None):
        self.work_duration = 25 * 60  # 25 minutes
        self.break_duration = 5 * 60  # 5 minutes
        self.long_break_duration = 15 * 60  # 15 minutes
        self.sessions_before_long_break = 4

        self.current_session = 0
        self.is_break = False
        self.remaining_seconds = self.work_duration
        self.is_running = False
        self.is_paused = False

        self.on_tick = on_tick
        self.on_complete = on_complete
        self.timer_thread = None

    def start(self):
        """Start the timer"""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self.timer_thread = threading.Thread(target=self._run)
        self.timer_thread.daemon = True
        self.timer_thread.start()

    def _run(self):
        """Timer loop"""
        while self.is_running and self.remaining_seconds > 0:
            if not self.is_paused:
                time.sleep(1)
                self.remaining_seconds -= 1
                if self.on_tick:
                    self.on_tick(self.remaining_seconds, self.is_break)
            else:
                time.sleep(0.1)

        if self.is_running:
            self._complete()

    def _complete(self):
        """Handle timer completion"""
        if self.is_break:
            # Break finished, start new work session
            self.is_break = False
            self.remaining_seconds = self.work_duration
        else:
            # Work session finished
            self.current_session += 1
            self.is_break = True

            if self.current_session % self.sessions_before_long_break == 0:
                self.remaining_seconds = self.long_break_duration
            else:
                self.remaining_seconds = self.break_duration

        self.is_running = False
        if self.on_complete:
            self.on_complete(self.is_break, self.current_session)

    def pause(self):
        """Pause the timer"""
        self.is_paused = True

    def resume(self):
        """Resume the timer"""
        self.is_paused = False

    def stop(self):
        """Stop the timer"""
        self.is_running = False
        self.is_paused = False

    def reset(self):
        """Reset the timer"""
        self.stop()
        self.remaining_seconds = self.work_duration
        self.current_session = 0
        self.is_break = False

    def get_time_string(self) -> str:
        """Get formatted time string"""
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_status(self) -> str:
        """Get current status"""
        if self.is_break:
            return "BREAK TIME"
        return f"FOCUS SESSION {self.current_session + 1}"


class HealthReminder:
    """Health and wellness reminders"""

    def __init__(self, callback: Callable = None):
        self.callback = callback
        self.enabled = True
        self.reminders = {
            'water': {
                'interval': 30 * 60,  # 30 minutes
                'message': "Time to hydrate! Drink some water.",
                'last_reminded': None
            },
            'posture': {
                'interval': 45 * 60,  # 45 minutes
                'message': "Posture check! Sit up straight and relax your shoulders.",
                'last_reminded': None
            },
            'eyes': {
                'interval': 20 * 60,  # 20 minutes (20-20-20 rule)
                'message': "Eye break! Look at something 20 feet away for 20 seconds.",
                'last_reminded': None
            },
            'stretch': {
                'interval': 60 * 60,  # 1 hour
                'message': "Time to stretch! Stand up and move around.",
                'last_reminded': None
            }
        }
        self.running = False
        self.thread = None

    def start(self):
        """Start reminder system"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        """Check reminders periodically"""
        while self.running:
            if self.enabled:
                now = datetime.now()
                for name, reminder in self.reminders.items():
                    if reminder['last_reminded'] is None:
                        reminder['last_reminded'] = now
                        continue

                    elapsed = (now - reminder['last_reminded']).total_seconds()
                    if elapsed >= reminder['interval']:
                        if self.callback:
                            self.callback(name, reminder['message'])
                        reminder['last_reminded'] = now

            time.sleep(60)  # Check every minute

    def stop(self):
        """Stop reminder system"""
        self.running = False

    def toggle(self):
        """Toggle reminders on/off"""
        self.enabled = not self.enabled
        return self.enabled

    def snooze(self, reminder_type: str, minutes: int = 10):
        """Snooze a specific reminder"""
        if reminder_type in self.reminders:
            self.reminders[reminder_type]['last_reminded'] = datetime.now() + timedelta(minutes=minutes)


class DailyMotivation:
    """Daily motivational quotes"""

    QUOTES = [
        ("The only way to do great work is to love what you do.", "Steve Jobs"),
        ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
        ("Stay hungry, stay foolish.", "Steve Jobs"),
        ("Your time is limited, don't waste it living someone else's life.", "Steve Jobs"),
        ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
        ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
        ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill"),
        ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
        ("The only impossible journey is the one you never begin.", "Tony Robbins"),
        ("What you get by achieving your goals is not as important as what you become.", "Zig Ziglar"),
        ("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb"),
        ("Your limitation—it's only your imagination.", "Unknown"),
        ("Push yourself, because no one else is going to do it for you.", "Unknown"),
        ("Sometimes later becomes never. Do it now.", "Unknown"),
        ("Dream it. Wish it. Do it.", "Unknown"),
        ("Success doesn't just find you. You have to go out and get it.", "Unknown"),
        ("The harder you work for something, the greater you'll feel when you achieve it.", "Unknown"),
        ("Don't stop when you're tired. Stop when you're done.", "Unknown"),
        ("Wake up with determination. Go to bed with satisfaction.", "Unknown"),
        ("Do something today that your future self will thank you for.", "Unknown"),
        ("I am not a product of my circumstances. I am a product of my decisions.", "Stephen Covey"),
        ("The mind is everything. What you think you become.", "Buddha"),
        ("An unexamined life is not worth living.", "Socrates"),
        ("Genius is one percent inspiration and ninety-nine percent perspiration.", "Thomas Edison"),
        ("Life is what happens when you're busy making other plans.", "John Lennon"),
    ]

    @classmethod
    def get_quote(cls) -> tuple:
        """Get a random quote"""
        return random.choice(cls.QUOTES)

    @classmethod
    def get_daily_quote(cls) -> tuple:
        """Get quote based on day (same quote each day)"""
        day_of_year = datetime.now().timetuple().tm_yday
        index = day_of_year % len(cls.QUOTES)
        return cls.QUOTES[index]


class QuickCommands:
    """Quick command palette system"""

    COMMANDS = {
        # Browsers
        'chrome': {
            'description': 'Open Google Chrome',
            'action': lambda: subprocess.Popen(['google-chrome-stable'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        },
        'firefox': {
            'description': 'Open Firefox',
            'action': lambda: subprocess.Popen(['firefox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        },
        'browser': {
            'description': 'Open default web browser',
            'action': lambda: subprocess.Popen(['xdg-open', 'https://google.com'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        },
        # Development
        'vscode': {
            'description': 'Open VS Code',
            'action': lambda: subprocess.Popen(['code'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        },
        'terminal': {
            'description': 'Open terminal',
            'action': lambda: subprocess.Popen(['gnome-terminal'])
        },
        # System
        'files': {
            'description': 'Open file manager',
            'action': lambda: subprocess.Popen(['nautilus', '.'])
        },
        'calculator': {
            'description': 'Open calculator',
            'action': lambda: subprocess.Popen(['gnome-calculator'])
        },
        'settings': {
            'description': 'Open system settings',
            'action': lambda: subprocess.Popen(['gnome-control-center'])
        },
        'lock': {
            'description': 'Lock the screen',
            'action': lambda: subprocess.run(['gnome-screensaver-command', '-l'], capture_output=True)
        },
        'screenshot': {
            'description': 'Take a screenshot',
            'action': lambda: subprocess.run(['gnome-screenshot'], capture_output=True)
        },
        # Volume
        'volume_up': {
            'description': 'Increase volume',
            'action': lambda: subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '+10%'], capture_output=True)
        },
        'volume_down': {
            'description': 'Decrease volume',
            'action': lambda: subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '-10%'], capture_output=True)
        },
        'mute': {
            'description': 'Toggle mute',
            'action': lambda: subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', 'toggle'], capture_output=True)
        },
    }

    # Natural language aliases -> command names
    APP_ALIASES = {
        'google chrome': 'chrome', 'google-chrome': 'chrome', 'chromium': 'chrome',
        'mozilla firefox': 'firefox',
        'visual studio code': 'vscode', 'vs code': 'vscode', 'code editor': 'vscode',
        'file manager': 'files', 'nautilus': 'files', 'folder': 'files', 'folders': 'files',
        'file explorer': 'files',
        'gnome terminal': 'terminal', 'console': 'terminal', 'shell': 'terminal',
        'command line': 'terminal', 'cmd': 'terminal',
        'calc': 'calculator',
        'system settings': 'settings', 'preferences': 'settings', 'control center': 'settings',
        'web browser': 'browser',
        'screen lock': 'lock', 'lock screen': 'lock',
        'volume up': 'volume_up', 'louder': 'volume_up', 'turn up': 'volume_up',
        'volume down': 'volume_down', 'quieter': 'volume_down', 'turn down': 'volume_down',
        'unmute': 'mute', 'toggle mute': 'mute',
    }

    @classmethod
    def resolve_app_command(cls, text: str) -> Optional[str]:
        """Resolve natural language to a command name. Returns command name or None."""
        text_lower = text.lower().strip()

        # Direct command match
        if text_lower in cls.COMMANDS:
            return text_lower

        # Alias match
        for alias, cmd_name in cls.APP_ALIASES.items():
            if alias in text_lower:
                return cmd_name

        # Fuzzy: check if any command name appears in the text
        for cmd_name in cls.COMMANDS:
            if cmd_name in text_lower:
                return cmd_name

        return None

    @classmethod
    def launch_arbitrary_app(cls, app_name: str) -> tuple:
        """
        Try to launch any installed application by name.
        Returns (success: bool, message: str)
        """
        import shutil

        app_clean = app_name.lower().strip()

        # Strip common prefixes from the voice/text input
        for prefix in ['open', 'start', 'launch', 'run', 'execute', 'bring up']:
            if app_clean.startswith(prefix):
                app_clean = app_clean[len(prefix):].strip()

        if not app_clean:
            return False, "No application name provided."

        # Build candidate binary names to try
        candidates = [
            app_clean,                              # e.g. "spotify"
            app_clean.replace(' ', '-'),             # e.g. "google-chrome"
            app_clean.replace(' ', ''),              # e.g. "googlechrome"
        ]

        # Common app name -> binary mappings
        app_binary_map = {
            'chrome': 'google-chrome-stable',
            'google chrome': 'google-chrome-stable',
            'vs code': 'code',
            'vscode': 'code',
            'visual studio code': 'code',
            'file manager': 'nautilus',
            'files': 'nautilus',
            'text editor': 'gedit',
            'notepad': 'gedit',
            'music': 'rhythmbox',
            'videos': 'totem',
            'image viewer': 'eog',
            'photos': 'eog',
            'disk usage': 'baobab',
            'system monitor': 'gnome-system-monitor',
            'task manager': 'gnome-system-monitor',
            'bluetooth': 'blueman-manager',
            'screen recorder': 'gnome-screenshot',
        }

        # Check known mappings first
        if app_clean in app_binary_map:
            candidates.insert(0, app_binary_map[app_clean])

        # Try each candidate
        for binary in candidates:
            binary_path = shutil.which(binary)
            if binary_path:
                try:
                    subprocess.Popen(
                        [binary_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    return True, f"Launched {app_clean}."
                except Exception as e:
                    return False, f"Found {binary} but couldn't launch it: {e}"

        # Try finding .desktop files as last resort
        desktop_result = cls._find_and_launch_desktop_app(app_clean)
        if desktop_result:
            return desktop_result

        return False, f"Couldn't find '{app_clean}' on your system."

    @classmethod
    def _find_and_launch_desktop_app(cls, app_name: str) -> Optional[tuple]:
        """Search .desktop files for an application and launch it"""
        import glob

        search_dirs = [
            os.path.expanduser("~/.local/share/applications"),
            "/usr/share/applications",
            "/usr/local/share/applications",
            "/var/lib/snapd/desktop/applications",
            "/var/lib/flatpak/exports/share/applications",
        ]

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue

            for desktop_file in glob.glob(os.path.join(search_dir, "*.desktop")):
                try:
                    name = ""
                    exec_cmd = ""
                    with open(desktop_file, 'r', errors='ignore') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("Name="):
                                name = line[5:].lower()
                            elif line.startswith("Exec="):
                                exec_cmd = line[5:]
                            if name and exec_cmd:
                                break

                    if app_name in name and exec_cmd:
                        # Clean exec command (remove %u, %f, etc.)
                        exec_parts = exec_cmd.split()
                        clean_cmd = []
                        for part in exec_parts:
                            if part.startswith('%'):
                                continue
                            clean_cmd.append(part)

                        if clean_cmd:
                            subprocess.Popen(
                                clean_cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True
                            )
                            return True, f"Launched {name}."
                except Exception:
                    continue

        return None

    @classmethod
    def execute(cls, command: str) -> bool:
        """Execute a quick command"""
        cmd = command.lower().strip()
        if cmd in cls.COMMANDS:
            try:
                cls.COMMANDS[cmd]['action']()
                return True
            except Exception:
                return False
        return False

    @classmethod
    def search(cls, query: str) -> list:
        """Search commands"""
        query = query.lower()
        results = []
        for name, cmd in cls.COMMANDS.items():
            if query in name or query in cmd['description'].lower():
                results.append((name, cmd['description']))
        return results

    @classmethod
    def get_all(cls) -> list:
        """Get all commands"""
        return [(name, cmd['description']) for name, cmd in cls.COMMANDS.items()]


class AmbientSound:
    """Ambient sound player for focus"""

    SOUNDS = {
        'rain': 'Rain sounds',
        'forest': 'Forest ambience',
        'ocean': 'Ocean waves',
        'fire': 'Fireplace crackling',
        'cafe': 'Coffee shop ambience',
        'white_noise': 'White noise',
    }

    def __init__(self):
        self.current_sound = None
        self.process = None

    def play(self, sound_type: str):
        """Play ambient sound (placeholder - would need actual audio files)"""
        self.stop()
        self.current_sound = sound_type
        # In a real implementation, this would play actual audio files
        # For now, it's a placeholder
        print(f"Playing {sound_type} ambient sound...")

    def stop(self):
        """Stop playing"""
        if self.process:
            self.process.terminate()
            self.process = None
        self.current_sound = None

    def get_available(self) -> dict:
        """Get available sounds"""
        return self.SOUNDS


class ScreenTimeTracker:
    """Track screen time and app usage"""

    def __init__(self):
        self.start_time = datetime.now()
        self.daily_limit_minutes = 480  # 8 hours default
        self.break_intervals = []

    def get_session_time(self) -> timedelta:
        """Get current session time"""
        return datetime.now() - self.start_time

    def get_session_time_string(self) -> str:
        """Get formatted session time"""
        delta = self.get_session_time()
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"

    def reset_session(self):
        """Reset session timer"""
        self.start_time = datetime.now()

    def add_break(self):
        """Record a break"""
        self.break_intervals.append(datetime.now())

    def get_productivity_score(self) -> int:
        """Calculate productivity score (0-100)"""
        session = self.get_session_time()
        hours = session.total_seconds() / 3600

        # Base score
        score = 70

        # Bonus for breaks
        breaks_per_hour = len(self.break_intervals) / max(hours, 1)
        if 1 <= breaks_per_hour <= 3:
            score += 15

        # Penalty for too much time
        if hours > 10:
            score -= 20
        elif hours > 8:
            score -= 10

        return max(0, min(100, int(score)))


class AppUsageTracker:
    """Track which applications the user is actively using via active window polling"""

    def __init__(self):
        self._running = False
        self._thread = None
        self._current_app = None
        self._current_title = None
        self._current_session_id = None
        self._session_start = None
        self._lock = threading.Lock()
        self._poll_interval = 5  # seconds

        # Check if xdotool is available
        self._xdotool_available = self._check_xdotool()

    def _check_xdotool(self) -> bool:
        try:
            subprocess.run(['xdotool', '--version'], capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def start(self):
        """Start tracking in background"""
        if self._running or not self._xdotool_available:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop tracking"""
        self._running = False
        self._finalize_current_session()

    def _poll_loop(self):
        """Main polling loop — checks active window every N seconds"""
        from core.database import get_db

        while self._running:
            try:
                app_name, window_title = self._get_active_window()
                if app_name:
                    with self._lock:
                        if app_name != self._current_app:
                            # App switched — finalize old session, start new one
                            self._finalize_current_session()
                            db = get_db()
                            self._current_session_id = db.log_app_switch(app_name, window_title)
                            self._current_app = app_name
                            self._current_title = window_title
                            self._session_start = time.time()
                        else:
                            # Same app — update duration
                            if self._current_session_id and self._session_start:
                                duration = int(time.time() - self._session_start)
                                db = get_db()
                                db.update_app_session(self._current_session_id, duration)
            except Exception:
                pass

            time.sleep(self._poll_interval)

    def _finalize_current_session(self):
        """Save final duration of current session"""
        if self._current_session_id and self._session_start:
            try:
                duration = int(time.time() - self._session_start)
                from core.database import get_db
                get_db().update_app_session(self._current_session_id, duration)
            except Exception:
                pass
        self._current_session_id = None
        self._current_app = None
        self._session_start = None

    def _get_active_window(self) -> tuple:
        """Get the currently active window's app name and title"""
        try:
            # Get active window ID
            result = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode != 0:
                return None, None

            window_id = result.stdout.strip()

            # Get window name
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True, timeout=3
            )
            window_title = result.stdout.strip() if result.returncode == 0 else ""

            # Get WM_CLASS (app identifier)
            result = subprocess.run(
                ['xprop', '-id', window_id, 'WM_CLASS'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and '=' in result.stdout:
                # WM_CLASS format: WM_CLASS(STRING) = "instance", "Class"
                parts = result.stdout.split('=', 1)[1].strip()
                classes = [c.strip().strip('"') for c in parts.split(',')]
                app_name = classes[-1] if classes else "Unknown"
            else:
                # Fallback: derive app name from window title
                app_name = window_title.split(' - ')[-1].strip() if window_title else "Unknown"

            # Clean up common app names
            app_name = self._clean_app_name(app_name)
            return app_name, window_title

        except Exception:
            return None, None

    def _clean_app_name(self, name: str) -> str:
        """Normalize app names for consistent tracking"""
        name_map = {
            'Google-chrome': 'Chrome',
            'google-chrome': 'Chrome',
            'Google-chrome-stable': 'Chrome',
            'firefox': 'Firefox',
            'Firefox': 'Firefox',
            'Navigator': 'Firefox',
            'Code': 'VS Code',
            'code': 'VS Code',
            'Gnome-terminal': 'Terminal',
            'gnome-terminal': 'Terminal',
            'org.gnome.Terminal': 'Terminal',
            'Nautilus': 'Files',
            'org.gnome.Nautilus': 'Files',
            'Spotify': 'Spotify',
            'spotify': 'Spotify',
            'discord': 'Discord',
            'Discord': 'Discord',
            'Slack': 'Slack',
            'slack': 'Slack',
            'Telegram': 'Telegram',
            'telegram-desktop': 'Telegram',
            'Thunderbird': 'Thunderbird',
            'Gedit': 'Text Editor',
            'org.gnome.gedit': 'Text Editor',
            'Evince': 'Document Viewer',
            'Eog': 'Image Viewer',
            'Totem': 'Videos',
            'vlc': 'VLC',
            'obs': 'OBS',
            'Gimp-2.10': 'GIMP',
            'libreoffice': 'LibreOffice',
        }
        return name_map.get(name, name)

    def get_current_app(self) -> Optional[str]:
        """Get the app currently being tracked"""
        with self._lock:
            return self._current_app

    def get_today_summary(self) -> str:
        """Get a formatted summary of today's app usage"""
        from core.database import get_db
        usage = get_db().get_app_usage_today()
        if not usage:
            return "No app usage tracked today yet."

        lines = ["Today's App Usage:\n"]
        total_seconds = 0
        for app in usage:
            secs = app['total_seconds'] or 0
            total_seconds += secs
            h = secs // 3600
            m = (secs % 3600) // 60
            time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            sessions = app['sessions']
            lines.append(f"  {app['app_name']:20s}  {time_str:>8s}  ({sessions} session{'s' if sessions != 1 else ''})")

        total_h = total_seconds // 3600
        total_m = (total_seconds % 3600) // 60
        lines.append(f"\n  {'TOTAL':20s}  {total_h}h {total_m}m")
        return "\n".join(lines)

    def get_top_apps(self, days: int = 7) -> str:
        """Get top used apps over N days"""
        from core.database import get_db
        usage = get_db().get_app_usage_range(days)
        if not usage:
            return f"No app usage data for the last {days} days."

        lines = [f"Top Apps (Last {days} Days):\n"]
        for i, app in enumerate(usage[:10], 1):
            secs = app['total_seconds'] or 0
            h = secs // 3600
            m = (secs % 3600) // 60
            time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            lines.append(f"  {i:2d}. {app['app_name']:20s}  {time_str:>8s}  ({app['days_used']}d)")
        return "\n".join(lines)


# Initialize global instances
system_monitor = SystemMonitor()
voice_engine = VoiceEngine()
daily_motivation = DailyMotivation()
quick_commands = QuickCommands()
screen_time = ScreenTimeTracker()
app_usage_tracker = AppUsageTracker()
