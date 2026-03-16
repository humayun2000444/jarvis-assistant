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
    """Text-to-speech engine for JARVIS voice"""

    def __init__(self):
        self.engine = None
        self.enabled = True
        self.speaking = False

        if TTS_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                # Configure voice
                voices = self.engine.getProperty('voices')
                # Try to find a male voice for JARVIS
                for voice in voices:
                    if 'male' in voice.name.lower() or 'david' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
                self.engine.setProperty('rate', 175)  # Speed
                self.engine.setProperty('volume', 0.9)
            except Exception:
                self.engine = None

    def speak(self, text: str, block: bool = False):
        """Speak text"""
        if not self.enabled or not self.engine:
            return

        def _speak():
            self.speaking = True
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except:
                pass
            self.speaking = False

        if block:
            _speak()
        else:
            thread = threading.Thread(target=_speak)
            thread.daemon = True
            thread.start()

    def stop(self):
        """Stop speaking"""
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass
        self.speaking = False

    def toggle(self):
        """Toggle voice on/off"""
        self.enabled = not self.enabled
        return self.enabled


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
        'lock': {
            'description': 'Lock the screen',
            'action': lambda: subprocess.run(['gnome-screensaver-command', '-l'], capture_output=True)
        },
        'screenshot': {
            'description': 'Take a screenshot',
            'action': lambda: subprocess.run(['gnome-screenshot'], capture_output=True)
        },
        'terminal': {
            'description': 'Open terminal',
            'action': lambda: subprocess.Popen(['gnome-terminal'])
        },
        'files': {
            'description': 'Open file manager',
            'action': lambda: subprocess.Popen(['nautilus', '.'])
        },
        'browser': {
            'description': 'Open web browser',
            'action': lambda: subprocess.Popen(['xdg-open', 'https://google.com'])
        },
        'calculator': {
            'description': 'Open calculator',
            'action': lambda: subprocess.Popen(['gnome-calculator'])
        },
        'settings': {
            'description': 'Open system settings',
            'action': lambda: subprocess.Popen(['gnome-control-center'])
        },
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


# Initialize global instances
system_monitor = SystemMonitor()
voice_engine = VoiceEngine()
daily_motivation = DailyMotivation()
quick_commands = QuickCommands()
screen_time = ScreenTimeTracker()
