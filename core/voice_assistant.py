#!/usr/bin/env python3
"""
JARVIS Voice Assistant - Two-way voice conversation with human-like speech
"""
import os
import sys
import threading
import queue
import time
from typing import Optional, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Speech Recognition
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

from core.features import VoiceEngine
from core.ai_engine import get_ai
from core.logger import get_logger

logger = get_logger("voice_assistant")


class VoiceAssistant:
    """Interactive voice assistant with speech recognition and natural speech"""

    # Wake words to activate listening
    WAKE_WORDS = ['jarvis', 'hey jarvis', 'ok jarvis', 'hello jarvis']

    def __init__(self, on_listening: Callable = None, on_speaking: Callable = None,
                 on_response: Callable = None):
        self.voice = VoiceEngine()
        self.ai = get_ai()
        self.recognizer = sr.Recognizer() if SR_AVAILABLE else None
        self.microphone = None

        # Callbacks for GUI integration
        self.on_listening = on_listening  # Called when listening starts
        self.on_speaking = on_speaking    # Called when speaking starts
        self.on_response = on_response    # Called with text response

        # State
        self.is_listening = False
        self.is_active = False
        self.continuous_mode = False
        self._stop_event = threading.Event()
        self._command_queue = queue.Queue()

        # Configure recognizer
        if self.recognizer:
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

        logger.info("Voice Assistant initialized")

    def _init_microphone(self):
        """Initialize microphone (lazy loading)"""
        if self.microphone is None and SR_AVAILABLE:
            try:
                self.microphone = sr.Microphone()
                # Calibrate for ambient noise
                with self.microphone as source:
                    logger.info("Calibrating microphone...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Microphone ready")
            except Exception as e:
                logger.error(f"Microphone init failed: {e}")
                self.microphone = None

    def listen_once(self, timeout: float = 5.0, phrase_time_limit: float = 10.0) -> Optional[str]:
        """Listen for a single phrase and return the text"""
        if not SR_AVAILABLE or not self.recognizer:
            logger.warning("Speech recognition not available")
            return None

        self._init_microphone()
        if not self.microphone:
            return None

        try:
            self.is_listening = True
            if self.on_listening:
                self.on_listening(True)

            with self.microphone as source:
                logger.debug("Listening...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

            # Recognize speech using Google's free service
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Recognized: {text}")
            return text.lower()

        except sr.WaitTimeoutError:
            logger.debug("Listening timeout")
            return None
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Listening error: {e}")
            return None
        finally:
            self.is_listening = False
            if self.on_listening:
                self.on_listening(False)

    def speak(self, text: str, block: bool = True):
        """Speak text with human-like voice"""
        if self.on_speaking:
            self.on_speaking(True)

        self.voice.speak(text, block=block)

        if self.on_speaking:
            self.on_speaking(False)

    def respond_to(self, text: str) -> str:
        """Get AI response and speak it"""
        # Get AI response
        response = self.ai.chat(text)

        # Notify callback
        if self.on_response:
            self.on_response(text, response)

        # Speak the response
        self.speak(response)

        return response

    def conversation_turn(self, prompt: str = "I'm listening...") -> Optional[str]:
        """Single conversation turn: prompt, listen, respond"""
        # Prompt
        self.speak(prompt)

        # Listen
        user_text = self.listen_once()
        if not user_text:
            self.speak("I didn't catch that. Could you repeat?")
            return None

        # Respond
        response = self.respond_to(user_text)
        return response

    def wait_for_wake_word(self, timeout: float = None) -> bool:
        """Wait for wake word activation"""
        start = time.time()

        while not self._stop_event.is_set():
            if timeout and (time.time() - start) > timeout:
                return False

            text = self.listen_once(timeout=3.0, phrase_time_limit=3.0)
            if text and any(wake in text for wake in self.WAKE_WORDS):
                logger.info("Wake word detected!")
                return True

        return False

    def start_continuous_conversation(self):
        """Start continuous conversation mode"""
        if not SR_AVAILABLE:
            logger.error("Speech recognition not available")
            return

        self._stop_event.clear()
        self.continuous_mode = True
        self.is_active = True

        def _conversation_loop():
            # Greeting
            self.speak("Hello! I'm JARVIS, your personal assistant. How can I help you?")

            while not self._stop_event.is_set():
                # Listen for user input
                user_text = self.listen_once(timeout=10.0)

                if not user_text:
                    continue

                # Check for exit commands
                if any(cmd in user_text for cmd in ['goodbye', 'bye', 'exit', 'quit', 'stop listening']):
                    self.speak("Goodbye! Call me anytime you need help.")
                    break

                # Check for wake word to continue
                if any(wake in user_text for wake in self.WAKE_WORDS):
                    self.speak("Yes?")
                    continue

                # Respond to the query
                self.respond_to(user_text)

            self.is_active = False
            self.continuous_mode = False

        thread = threading.Thread(target=_conversation_loop, daemon=True)
        thread.start()

    def start_wake_word_mode(self):
        """Start wake word detection mode"""
        if not SR_AVAILABLE:
            logger.error("Speech recognition not available")
            return

        self._stop_event.clear()
        self.is_active = True

        def _wake_word_loop():
            logger.info("Wake word mode started. Say 'JARVIS' to activate.")

            while not self._stop_event.is_set():
                # Wait for wake word
                if self.wait_for_wake_word(timeout=None):
                    # Acknowledge
                    self.speak("Yes, how can I help?")

                    # Listen for command
                    user_text = self.listen_once(timeout=5.0, phrase_time_limit=15.0)

                    if user_text:
                        # Check for exit
                        if any(cmd in user_text for cmd in ['goodbye', 'bye', 'exit', 'stop']):
                            self.speak("Goodbye!")
                            break

                        # Respond
                        self.respond_to(user_text)

            self.is_active = False

        thread = threading.Thread(target=_wake_word_loop, daemon=True)
        thread.start()

    def stop(self):
        """Stop conversation mode"""
        self._stop_event.set()
        self.voice.stop()
        self.is_active = False
        self.continuous_mode = False

    def get_status(self) -> dict:
        """Get voice assistant status"""
        return {
            'speech_recognition_available': SR_AVAILABLE,
            'microphone_ready': self.microphone is not None,
            'voice_engine': 'edge-tts' if self.voice.edge_tts_available else 'pyttsx3',
            'current_voice': self.voice.voice,
            'is_listening': self.is_listening,
            'is_active': self.is_active,
            'continuous_mode': self.continuous_mode,
        }


class VoiceCommandHandler:
    """Handle voice commands for quick actions"""

    COMMANDS = {
        'what time is it': lambda: f"The time is {time.strftime('%I:%M %p')}",
        'what is the date': lambda: f"Today is {time.strftime('%A, %B %d, %Y')}",
        'open tasks': 'show_tasks',
        'show my tasks': 'show_tasks',
        'add task': 'add_task',
        'take a break': 'start_break',
        'start pomodoro': 'start_pomodoro',
        'how am i doing': 'show_stats',
        'give me a summary': 'show_summary',
    }

    def __init__(self, assistant: VoiceAssistant):
        self.assistant = assistant

    def handle_command(self, text: str) -> Optional[str]:
        """Check if text is a known command and handle it"""
        text_lower = text.lower().strip()

        for phrase, action in self.COMMANDS.items():
            if phrase in text_lower:
                if callable(action):
                    return action()
                else:
                    # Return action name for GUI to handle
                    return f"__command__:{action}"

        return None


# Convenience functions
_assistant_instance = None


def get_voice_assistant() -> VoiceAssistant:
    """Get the voice assistant instance"""
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = VoiceAssistant()
    return _assistant_instance


def quick_speak(text: str):
    """Quick function to speak text"""
    assistant = get_voice_assistant()
    assistant.speak(text, block=False)


def quick_listen() -> Optional[str]:
    """Quick function to listen for speech"""
    assistant = get_voice_assistant()
    return assistant.listen_once()


def start_voice_mode():
    """Start interactive voice mode"""
    assistant = get_voice_assistant()

    print("\n" + "=" * 50)
    print("JARVIS Voice Mode")
    print("=" * 50)
    print("Say 'JARVIS' to activate, or speak directly.")
    print("Say 'goodbye' to exit.")
    print("=" * 50 + "\n")

    assistant.start_continuous_conversation()

    # Keep running until stopped
    try:
        while assistant.is_active:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    assistant.stop()
    print("\nVoice mode ended.")


if __name__ == '__main__':
    # Test voice assistant
    start_voice_mode()
