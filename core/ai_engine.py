"""
JARVIS AI Engine - Robust Ollama Integration with retry logic and fallbacks
"""
import subprocess
import json
import time
import threading
import queue
import hashlib
from typing import List, Dict, Optional, Generator, Callable
from datetime import datetime, date
from functools import wraps

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config.settings import AI_MODEL, AI_TEMPERATURE, PERSONALITY_PROMPT, USER_NAME, ASSISTANT_NAME
from core.database import get_db
from core.logger import get_logger, log_exceptions, ExceptionHandler

# Import weather service
try:
    from core.weather import get_weather_service, get_weather_speech
    WEATHER_AVAILABLE = True
except ImportError:
    WEATHER_AVAILABLE = False

logger = get_logger("ai_engine")


class AIError(Exception):
    """Custom AI engine exception"""
    pass


class OllamaHealthCheck:
    """Monitor Ollama service health"""

    def __init__(self):
        self._healthy = False
        self._last_check = 0
        self._check_interval = 30  # seconds
        self._lock = threading.Lock()

    def is_healthy(self, force_check: bool = False) -> bool:
        """Check if Ollama is healthy"""
        now = time.time()

        with self._lock:
            if not force_check and (now - self._last_check) < self._check_interval:
                return self._healthy

            self._last_check = now

            if not OLLAMA_AVAILABLE:
                self._healthy = False
                return False

            try:
                ollama.list()
                self._healthy = True
            except Exception as e:
                logger.debug(f"Ollama health check failed: {e}")
                self._healthy = False

            return self._healthy

    def wait_for_healthy(self, timeout: float = 30.0) -> bool:
        """Wait for Ollama to become healthy"""
        start = time.time()
        while (time.time() - start) < timeout:
            if self.is_healthy(force_check=True):
                return True
            time.sleep(1)
        return False


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 30.0, exponential: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt"""
        if self.exponential:
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay
        return min(delay, self.max_delay)


def with_retry(retry_config: RetryConfig = None):
    """Decorator for retry logic"""
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(retry_config.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < retry_config.max_retries - 1:
                        delay = retry_config.get_delay(attempt)
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
                        time.sleep(delay)

            raise AIError(f"Operation failed after {retry_config.max_retries} attempts: {last_error}")

        return wrapper
    return decorator


class ResponseBuffer:
    """Thread-safe buffer for streaming responses"""

    def __init__(self):
        self._buffer = queue.Queue()
        self._complete = threading.Event()
        self._error = None

    def put(self, text: str):
        """Add text to buffer"""
        self._buffer.put(text)

    def set_error(self, error: Exception):
        """Set error state"""
        self._error = error
        self._complete.set()

    def mark_complete(self):
        """Mark streaming as complete"""
        self._complete.set()

    def get_chunks(self, timeout: float = 0.1) -> Generator[str, None, None]:
        """Yield chunks from buffer"""
        while not self._complete.is_set() or not self._buffer.empty():
            try:
                chunk = self._buffer.get(timeout=timeout)
                yield chunk
            except queue.Empty:
                continue

        if self._error:
            raise self._error


class JarvisAI:
    """Robust AI engine with health checks and retry logic"""

    # Token budget for context (conservative estimate for small models)
    MAX_CONTEXT_TOKENS = 2048
    SYSTEM_PROMPT_TOKEN_BUDGET = 512
    CHARS_PER_TOKEN = 4  # rough heuristic

    def __init__(self, model: str = None):
        import os
        self.model = model or os.environ.get('JARVIS_MODEL') or AI_MODEL
        self._db = None
        self.context = []
        self._health_check = OllamaHealthCheck()
        self._retry_config = RetryConfig(max_retries=3, base_delay=1.0)
        self._response_cache = {}
        self._cache_lock = threading.Lock()
        self._cache_max_size = 100

        logger.info(f"AI Engine initialized with model: {self.model}")

    @property
    def db(self):
        """Lazy load database"""
        if self._db is None:
            self._db = get_db()
        return self._db

    @property
    def ollama_available(self) -> bool:
        """Check if Ollama is available"""
        return self._health_check.is_healthy()

    def ensure_ollama_ready(self) -> bool:
        """Ensure Ollama is ready, attempting to start if needed"""
        if self._health_check.is_healthy():
            return True

        logger.info("Ollama not responding, checking service...")

        # Try to start Ollama if not running
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            logger.info("Started Ollama service")

            # Wait for it to be ready
            if self._health_check.wait_for_healthy(timeout=30):
                logger.info("Ollama is now ready")
                return True
        except FileNotFoundError:
            logger.warning("Ollama not installed")
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")

        return False

    def _build_context(self) -> str:
        """Build context from recent activity, tasks, and patterns"""
        context_parts = []

        try:
            # Add pending tasks
            tasks = self.db.get_pending_tasks()
            if tasks:
                task_list = "\n".join([f"- [{t['priority']}] {t['title']}" for t in tasks[:5]])
                context_parts.append(f"Current pending tasks:\n{task_list}")

            # Add today's activities
            logs = self.db.get_today_logs()
            if logs:
                log_list = "\n".join([f"- {l['time'][:5]}: {l['activity']}" for l in logs[-5:]])
                context_parts.append(f"Today's activities:\n{log_list}")

            # Add learned patterns/preferences
            prefs = self.db.get_all_preferences()
            if prefs:
                pref_list = "\n".join([f"- {k}: {v}" for k, v in list(prefs.items())[:5]])
                context_parts.append(f"User preferences:\n{pref_list}")

            # Add productivity stats
            stats = self.db.get_productivity_stats(7)
            context_parts.append(
                f"Last 7 days: {stats['tasks_completed']} tasks completed, "
                f"{stats['activities_logged']} activities logged"
            )

            # Add persistent memories
            try:
                from core.smart_features import get_memory
                memory_context = get_memory().get_context_for_ai()
                if memory_context:
                    context_parts.append(memory_context)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Error building context: {e}")

        return "\n\n".join(context_parts)

    def _get_system_prompt(self) -> str:
        """Generate system prompt with current context"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        context = self._build_context()

        return f"""{PERSONALITY_PROMPT}

Current time: {current_time}

{context}

Remember to:
1. Be helpful and proactive
2. Remind about important tasks when relevant
3. Learn from user's patterns and preferences
4. Provide actionable suggestions
5. Keep responses concise but friendly
"""

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough heuristic: ~4 chars per token)"""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def _trim_messages_to_budget(self, messages: List[Dict], budget_tokens: int) -> List[Dict]:
        """Trim oldest messages to fit within token budget"""
        if not messages:
            return messages

        total = sum(self._estimate_tokens(m.get('content', '')) for m in messages)
        if total <= budget_tokens:
            return messages

        # Remove oldest messages until within budget
        trimmed = list(messages)
        while trimmed and total > budget_tokens:
            removed = trimmed.pop(0)
            total -= self._estimate_tokens(removed.get('content', ''))

        return trimmed

    def _get_cache_key(self, message: str) -> str:
        """Generate deterministic cache key for message"""
        return hashlib.sha256(message.encode()).hexdigest()

    def _handle_direct_queries(self, message: str) -> Optional[str]:
        """Handle queries that should be answered directly without AI"""
        # App launch commands
        app_result = self._handle_app_launch(message)
        if app_result:
            return app_result

        # Smart features (search, reminders, music, files, notes, system, memory, etc.)
        smart_result = self._handle_smart_features(message)
        if smart_result:
            return smart_result

        # Weather queries
        if any(word in message for word in ['weather', 'temperature', 'forecast']):
            return self._get_weather_response(message)

        # Time queries
        if any(phrase in message for phrase in ['what time', 'current time', "what's the time"]):
            return f"The current time is {datetime.now().strftime('%H:%M on %A, %B %d, %Y')}"

        # Date queries
        if any(phrase in message for phrase in ['what date', "what's the date", 'today date', "what day"]):
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"

        return None

    def _handle_smart_features(self, message: str) -> Optional[str]:
        """Route to smart features based on natural language"""
        msg = message.lower().strip()

        try:
            from core.smart_features import (
                get_screen, get_web_search, get_reminder_system, get_music,
                get_file_manager, get_notes, get_system_controller, get_memory,
                get_briefing, get_automation, get_startup_manager
            )

            # ---- CLIPBOARD ----
            if any(p in msg for p in ['clipboard', 'what did i copy', "what's copied", 'paste']):
                clip = get_screen().get_clipboard()
                if clip:
                    return f"Clipboard contents:\n{clip[:500]}"
                return "Clipboard is empty."

            # ---- SCREENSHOT / SCREEN ----
            if any(p in msg for p in ["what's on my screen", 'read my screen', 'screen text', 'ocr']):
                return get_screen().ocr_screenshot()

            if any(p in msg for p in ['take screenshot', 'take a screenshot', 'screenshot', 'capture screen']):
                path = get_screen().take_screenshot()
                if path:
                    return f"Screenshot saved to {path}"
                return "Could not take screenshot."

            # ---- WEB SEARCH ----
            if any(p in msg for p in ['search for', 'search the web', 'google', 'look up', 'find out', 'what is', 'who is', 'define']):
                # Extract search query
                for prefix in ['search for', 'search the web for', 'google', 'look up', 'find out about', 'find out', 'define', 'what is', 'who is']:
                    if prefix in msg:
                        query = msg.split(prefix, 1)[-1].strip().rstrip('?.')
                        if query:
                            if prefix in ('what is', 'who is', 'define'):
                                return get_web_search().quick_answer(query)
                            return get_web_search().search_summary(query)
                return None

            # ---- REMINDERS ----
            if any(p in msg for p in ['remind me', 'set a reminder', 'set reminder', 'alarm']):
                return self._parse_reminder(msg)

            if any(p in msg for p in ['my reminders', 'pending reminders', 'show reminders', 'list reminders']):
                pending = get_reminder_system().get_pending()
                if not pending:
                    return "No pending reminders."
                result = "Pending reminders:\n"
                for r in pending:
                    t = datetime.fromisoformat(r['time']).strftime('%I:%M %p')
                    result += f"  - {t}: {r['message']}\n"
                return result

            # ---- MUSIC ----
            music = get_music()
            if any(p in msg for p in ['play music', 'resume music', 'resume playback']):
                return music.play()
            if any(p in msg for p in ['pause music', 'pause playback', 'stop music']):
                return music.pause()
            if any(p in msg for p in ['next song', 'next track', 'skip song', 'skip track']):
                return music.next_track()
            if any(p in msg for p in ['previous song', 'previous track', 'last song']):
                return music.previous_track()
            if any(p in msg for p in ["what's playing", 'now playing', 'current song', 'what song']):
                return music.now_playing()

            # ---- FILES ----
            if any(p in msg for p in ['find file', 'find my', 'search file', 'where is my', 'locate']):
                for prefix in ['find file', 'find my', 'search file', 'where is my', 'locate']:
                    if prefix in msg:
                        query = msg.split(prefix, 1)[-1].strip()
                        if query:
                            return get_file_manager().find_files_summary(query)
                return None

            if any(p in msg for p in ['recent downloads', 'show downloads', 'my downloads', 'downloaded files']):
                return get_file_manager().list_recent_downloads()

            if 'disk usage' in msg or 'disk space' in msg or 'storage' in msg:
                return get_file_manager().get_disk_usage()

            # ---- NOTES ----
            if any(p in msg for p in ['take a note', 'take note', 'note this', 'save note', 'write down']):
                for prefix in ['take a note', 'take note', 'note this', 'save note', 'write down']:
                    if prefix in msg:
                        content = msg.split(prefix, 1)[-1].strip().lstrip(':').strip()
                        if content:
                            return get_notes().add_note(content)
                return "What would you like me to note?"

            if any(p in msg for p in ['my notes', 'show notes', 'list notes', 'recent notes']):
                return get_notes().list_recent()

            if any(p in msg for p in ['search notes', 'find note', 'find in notes']):
                for prefix in ['search notes', 'find note', 'find in notes']:
                    if prefix in msg:
                        query = msg.split(prefix, 1)[-1].strip()
                        if query:
                            return get_notes().search_notes(query)
                return None

            # ---- SYSTEM ----
            if any(p in msg for p in ['system info', 'system status', 'how is my system', 'cpu usage', 'ram usage', 'memory usage']):
                return get_system_controller().get_system_info()

            if any(p in msg for p in ['kill process', 'kill app', 'force close', 'force quit']):
                for prefix in ['kill process', 'kill app', 'force close', 'force quit']:
                    if prefix in msg:
                        proc = msg.split(prefix, 1)[-1].strip()
                        if proc:
                            return get_system_controller().kill_process(proc)
                return None

            if any(p in msg for p in ['wifi status', 'wifi', 'internet connection', 'am i connected']):
                return get_system_controller().get_wifi_status()

            if any(p in msg for p in ['battery', 'battery status', 'battery level', 'charge level']):
                return get_system_controller().get_battery()

            if any(p in msg for p in ['ip address', 'my ip', 'what is my ip']):
                return get_system_controller().get_ip_address()

            if any(p in msg for p in ['brightness']):
                match = re.search(r'(\d+)', msg)
                if match:
                    return get_system_controller().set_brightness(int(match.group(1)))
                return "Set brightness to what level? (0-100)"

            if msg in ['shutdown', 'shut down', 'power off', 'turn off']:
                return get_system_controller().shutdown('shutdown')
            if msg in ['restart', 'reboot']:
                return get_system_controller().shutdown('restart')
            if msg in ['sleep', 'go to sleep', 'suspend']:
                return get_system_controller().shutdown('sleep')
            if msg in ['logout', 'log out', 'sign out']:
                return get_system_controller().shutdown('logout')

            # ---- MEMORY ----
            if any(p in msg for p in ['remember that', 'remember this', 'remember my']):
                for prefix in ['remember that', 'remember this', 'remember my']:
                    if prefix in msg:
                        content = msg.split(prefix, 1)[-1].strip()
                        if content:
                            # Try to split "key is value" pattern
                            if ' is ' in content:
                                key, _, value = content.partition(' is ')
                                return get_memory().remember(key.strip(), value.strip())
                            return get_memory().remember(content[:50], content)
                return None

            if any(p in msg for p in ['what do you remember', 'my memories', 'show memories', 'list memories']):
                return get_memory().list_memories()

            if any(p in msg for p in ['do you remember', 'recall', 'what is my', "what's my"]):
                for prefix in ['do you remember', 'recall', 'what is my', "what's my"]:
                    if prefix in msg:
                        query = msg.split(prefix, 1)[-1].strip().rstrip('?')
                        if query:
                            return get_memory().recall(query)
                return None

            if any(p in msg for p in ['forget about', 'forget my', 'delete memory']):
                for prefix in ['forget about', 'forget my', 'delete memory']:
                    if prefix in msg:
                        key = msg.split(prefix, 1)[-1].strip()
                        if key:
                            return get_memory().forget(key)
                return None

            # ---- DAILY BRIEFING ----
            if any(p in msg for p in ['daily briefing', 'morning briefing', 'brief me', "what's my day look like", 'my day']):
                return get_briefing().generate()

            # ---- WORKFLOWS ----
            if any(p in msg for p in ['goodnight', 'good night']):
                return get_automation().run_workflow('goodnight')
            if any(p in msg for p in ['work mode', 'start work', 'time to work']):
                return get_automation().run_workflow('work mode')
            if any(p in msg for p in ['break time', 'take a break']):
                return get_automation().run_workflow('break time')

            if any(p in msg for p in ['list workflows', 'my workflows', 'show workflows']):
                return get_automation().list_workflows()

            if 'run workflow' in msg:
                name = msg.split('run workflow', 1)[-1].strip()
                if name:
                    return get_automation().run_workflow(name)

            # ---- STARTUP APPS ----
            if any(p in msg for p in ['startup apps', 'startup list', 'my startup', 'show startup', 'list startup']):
                return get_startup_manager().list_apps()

            if any(p in msg for p in ['run startup', 'launch startup', 'start my apps', 'open my apps', 'run my apps']):
                return get_startup_manager().run_startup()

            if any(p in msg for p in ['add to startup', 'add startup']):
                for prefix in ['add to startup', 'add startup']:
                    if prefix in msg:
                        app = msg.split(prefix, 1)[-1].strip()
                        if app:
                            return get_startup_manager().add_app(app)
                return "Which app should I add to startup?"

            if any(p in msg for p in ['remove from startup', 'remove startup']):
                for prefix in ['remove from startup', 'remove startup']:
                    if prefix in msg:
                        app = msg.split(prefix, 1)[-1].strip()
                        if app:
                            return get_startup_manager().remove_app(app)
                return "Which app should I remove from startup?"

        except ImportError as e:
            logger.error(f"Smart features import error: {e}")
        except Exception as e:
            logger.error(f"Smart features error: {e}")

        return None

    def _parse_reminder(self, msg: str) -> str:
        """Parse natural language reminder"""
        from core.smart_features import get_reminder_system

        # "remind me in 30 minutes to call mom"
        match = re.search(r'in\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)', msg)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            # Extract the reminder message
            reminder_msg = msg
            for prefix in ['remind me', 'set a reminder', 'set reminder']:
                if prefix in reminder_msg:
                    reminder_msg = reminder_msg.split(prefix, 1)[-1]
            # Remove the time part
            reminder_msg = re.sub(r'in\s+\d+\s*(minutes?|mins?|hours?|hrs?)', '', reminder_msg)
            for word in ['to', 'that', 'about']:
                reminder_msg = reminder_msg.lstrip().removeprefix(word).strip()
            reminder_msg = reminder_msg.strip() or "Reminder!"

            if 'hour' in unit or 'hr' in unit:
                return get_reminder_system().add_reminder(reminder_msg, hours=amount)
            return get_reminder_system().add_reminder(reminder_msg, minutes=amount)

        # "remind me at 3pm to call mom"
        match = re.search(r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)', msg)
        if match:
            time_str = match.group(1)
            reminder_msg = msg
            for prefix in ['remind me', 'set a reminder', 'set reminder']:
                if prefix in reminder_msg:
                    reminder_msg = reminder_msg.split(prefix, 1)[-1]
            reminder_msg = re.sub(r'at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?', '', reminder_msg)
            for word in ['to', 'that', 'about']:
                reminder_msg = reminder_msg.lstrip().removeprefix(word).strip()
            reminder_msg = reminder_msg.strip() or "Reminder!"

            return get_reminder_system().add_reminder(reminder_msg, at_time=time_str)

        # Simple: "remind me to buy milk"
        reminder_msg = msg
        for prefix in ['remind me', 'set a reminder', 'set reminder']:
            if prefix in reminder_msg:
                reminder_msg = reminder_msg.split(prefix, 1)[-1]
        for word in ['to', 'that', 'about']:
            reminder_msg = reminder_msg.lstrip().removeprefix(word).strip()
        reminder_msg = reminder_msg.strip() or "Reminder!"

        return get_reminder_system().add_reminder(reminder_msg, minutes=5)

    def _handle_app_launch(self, message: str) -> Optional[str]:
        """Detect and execute app launch commands from natural language"""
        launch_triggers = ['open', 'start', 'launch', 'run', 'execute', 'show me', 'bring up']

        message_lower = message.lower().strip()
        has_trigger = any(trigger in message_lower for trigger in launch_triggers)

        if not has_trigger:
            return None

        try:
            from core.features import QuickCommands

            # Try predefined commands first
            cmd_name = QuickCommands.resolve_app_command(message_lower)
            if cmd_name:
                success = QuickCommands.execute(cmd_name)
                app_desc = QuickCommands.COMMANDS[cmd_name]['description']
                if success:
                    return f"Done! {app_desc}."
                else:
                    return f"I tried to {app_desc.lower()}, but it didn't work."

            # Fall back to arbitrary app launch — find any installed app
            success, msg = QuickCommands.launch_arbitrary_app(message_lower)
            return msg

        except Exception as e:
            logger.error(f"App launch error: {e}")

        return None

    @log_exceptions("ai_engine")
    def chat(self, message: str, stream: bool = False, use_cache: bool = True) -> str:
        """Send a message to the AI and get response"""
        if not message or not message.strip():
            return "I didn't catch that. Could you please repeat?"

        # Check cache for repeated queries
        cache_key = self._get_cache_key(message)
        if use_cache:
            with self._cache_lock:
                if cache_key in self._response_cache:
                    logger.debug("Returning cached response")
                    return self._response_cache[cache_key]

        # Save user message to DB
        try:
            self.db.add_message("user", message)
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")

        # Handle special queries directly (weather, time, etc.) - don't send to Ollama
        message_lower = message.lower().strip()
        reply = self._handle_direct_queries(message_lower)

        if reply is None:
            # Get recent conversation history with token-aware trimming
            try:
                recent = self.db.get_recent_messages(20)
                messages = [{"role": m["role"], "content": m["content"]} for m in recent]
                context_budget = self.MAX_CONTEXT_TOKENS - self.SYSTEM_PROMPT_TOKEN_BUDGET
                messages = self._trim_messages_to_budget(messages, context_budget)
            except Exception as e:
                logger.warning(f"Failed to get recent messages: {e}")
                messages = []

            # Try Ollama first
            if self.ensure_ollama_ready():
                reply = self._chat_with_ollama(message, messages)

            # Fallback to rule-based if Ollama unavailable
            if reply is None:
                reply = self._fallback_response(message)

        # Save response
        try:
            self.db.add_message("assistant", reply)
        except Exception as e:
            logger.warning(f"Failed to save assistant message: {e}")

        # Cache response
        with self._cache_lock:
            if len(self._response_cache) >= self._cache_max_size:
                # Remove oldest entries
                keys = list(self._response_cache.keys())[:10]
                for k in keys:
                    del self._response_cache[k]
            self._response_cache[cache_key] = reply

        # Learn from interaction
        self._learn_from_interaction(message, reply)

        return reply

    @with_retry(RetryConfig(max_retries=3, base_delay=1.0))
    def _chat_with_ollama(self, message: str, messages: List[Dict]) -> Optional[str]:
        """Chat with Ollama with retry logic"""
        if not OLLAMA_AVAILABLE:
            return None

        system_prompt = self._get_system_prompt()

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                    {"role": "user", "content": message}
                ],
                options={
                    "temperature": AI_TEMPERATURE,
                    "num_predict": 1000,
                }
            )
            return response['message']['content']
        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                logger.error(f"Model {self.model} not found. Pulling...")
                self._pull_model()
                raise  # Retry after pulling
            raise

    def _pull_model(self):
        """Pull the configured model"""
        try:
            logger.info(f"Pulling model {self.model}...")
            ollama.pull(self.model)
            logger.info(f"Model {self.model} pulled successfully")
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")

    def stream_chat(self, message: str) -> Generator[str, None, None]:
        """Stream response from AI"""
        if not message or not message.strip():
            yield "I didn't catch that. Could you please repeat?"
            return

        try:
            self.db.add_message("user", message)
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")

        # Handle direct queries (app launch, weather, time) before Ollama
        message_lower = message.lower().strip()
        direct_reply = self._handle_direct_queries(message_lower)
        if direct_reply:
            try:
                self.db.add_message("assistant", direct_reply)
            except Exception as e:
                logger.warning(f"Failed to save assistant message: {e}")
            yield direct_reply
            return

        try:
            recent = self.db.get_recent_messages(20)
            messages = [{"role": m["role"], "content": m["content"]} for m in recent]
            context_budget = self.MAX_CONTEXT_TOKENS - self.SYSTEM_PROMPT_TOKEN_BUDGET
            messages = self._trim_messages_to_budget(messages, context_budget)
        except Exception as e:
            logger.warning(f"Failed to get recent messages: {e}")
            messages = []

        full_response = ""
        system_prompt = self._get_system_prompt()

        if self.ensure_ollama_ready() and OLLAMA_AVAILABLE:
            try:
                stream = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *messages,
                        {"role": "user", "content": message}
                    ],
                    stream=True,
                    options={
                        "temperature": AI_TEMPERATURE,
                        "num_predict": 1000,
                    }
                )
                for chunk in stream:
                    text = chunk['message']['content']
                    full_response += text
                    yield text
            except Exception as e:
                error_msg = f"AI error: {e}"
                logger.error(error_msg)
                yield error_msg
                full_response = error_msg
        else:
            response = self._fallback_response(message)
            full_response = response
            yield response

        try:
            self.db.add_message("assistant", full_response)
        except Exception as e:
            logger.warning(f"Failed to save assistant message: {e}")

    def _fallback_response(self, message: str) -> str:
        """Intelligent rule-based responses when AI is not available"""
        message_lower = message.lower().strip()
        logger.debug(f"Using fallback response for: {message[:50]}...")

        # Greetings
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']):
            hour = datetime.now().hour
            if hour < 12:
                greeting = "Good morning"
            elif hour < 17:
                greeting = "Good afternoon"
            else:
                greeting = "Good evening"
            return f"{greeting}, {USER_NAME}! I'm {ASSISTANT_NAME}, your personal assistant. How can I help you today?"

        # Weather queries (check early before "today" triggers activity check)
        if any(word in message_lower for word in ['weather', 'temperature', 'forecast', 'rain', 'sunny', 'cloudy']):
            return self._get_weather_response(message_lower)

        # Task queries
        if any(word in message_lower for word in ['task', 'todo', 'pending', 'what do i need']):
            tasks = self.db.get_pending_tasks()
            if tasks:
                high = [t for t in tasks if t['priority'] == 'high']
                task_list = "\n".join([f"  {i+1}. [{t['priority']}] {t['title']}" for i, t in enumerate(tasks[:10])])
                msg = f"You have {len(tasks)} pending task(s)"
                if high:
                    msg += f" ({len(high)} high priority)"
                return f"{msg}:\n{task_list}"
            return "You have no pending tasks. Great job staying on top of things!"

        # Activity/log queries
        if any(word in message_lower for word in ['today', 'activity', 'activities', 'log', 'what did i']):
            logs = self.db.get_today_logs()
            if logs:
                log_list = "\n".join([f"  - {l['time'][:5]}: {l['activity']}" for l in logs])
                return f"Today's activities ({len(logs)} logged):\n{log_list}"
            return "No activities logged today yet. Would you like to log something?"

        # Summary
        if 'summary' in message_lower:
            return self.generate_daily_summary()

        # Stats
        if any(word in message_lower for word in ['stats', 'statistics', 'productivity', 'progress']):
            stats = self.db.get_productivity_stats(7)
            hours = stats['total_work_minutes'] // 60
            mins = stats['total_work_minutes'] % 60
            return (
                f"Your last 7 days:\n"
                f"  - Tasks completed: {stats['tasks_completed']}\n"
                f"  - Activities logged: {stats['activities_logged']}\n"
                f"  - Total tracked time: {hours}h {mins}m"
            )

        # Help
        if any(word in message_lower for word in ['help', 'what can you do', 'capabilities']):
            weather_status = "Available" if WEATHER_AVAILABLE else "Not installed"
            return f"""I'm {ASSISTANT_NAME}, your personal assistant. I can help you with:

- Task Management: "Add task...", "Show tasks", "Complete task #..."
- Activity Logging: "Log activity...", "What did I do today?"
- Daily Summaries: "Show summary", "How was my day?"
- Productivity Stats: "Show stats", "How productive am I?"
- Weather: "What's the weather?", "Weather in London"
- Reminders: "Remind me to..."
- Suggestions: "Give me suggestions"

Note: For full AI capabilities, Ollama should be running.
AI status: {'Ready' if self.ollama_available else 'Offline (using basic responses)'}
Weather: {weather_status}"""

        # Time
        if any(word in message_lower for word in ['time', 'what time', 'current time']):
            return f"The current time is {datetime.now().strftime('%H:%M on %A, %B %d, %Y')}"

        # Thank you
        if any(word in message_lower for word in ['thank', 'thanks']):
            return "You're welcome! Let me know if you need anything else."

        # Default response
        return (
            f"I understand you said: '{message[:100]}{'...' if len(message) > 100 else ''}'. "
            f"I'm currently operating in basic mode. "
            f"For full AI capabilities, ensure Ollama is running with: ollama serve"
        )

    def _learn_from_interaction(self, user_msg: str, ai_response: str):
        """Learn patterns from user interactions"""
        try:
            now = datetime.now()
            hour = now.hour

            # Track activity patterns by time
            pattern_data = {
                "hour": hour,
                "day_of_week": now.strftime("%A"),
                "message_type": self._categorize_message(user_msg)
            }

            self.db.record_pattern(
                "interaction_time",
                pattern_data,
                f"User often interacts around {hour}:00 on {now.strftime('%A')}s"
            )
        except Exception as e:
            logger.debug(f"Failed to learn from interaction: {e}")

    def _categorize_message(self, message: str) -> str:
        """Categorize user message type"""
        message_lower = message.lower()
        if any(word in message_lower for word in ['task', 'todo', 'remind']):
            return "task_management"
        elif any(word in message_lower for word in ['weather', 'temperature', 'forecast']):
            return "weather_query"
        elif any(word in message_lower for word in ['log', 'activity', 'work']):
            return "activity_logging"
        elif any(word in message_lower for word in ['summary', 'report', 'stats']):
            return "reporting"
        elif any(word in message_lower for word in ['help', 'how', 'what']):
            return "help_query"
        return "general"

    def _get_weather_response(self, message: str) -> str:
        """Get weather information for user query"""
        if not WEATHER_AVAILABLE:
            return "Weather service is not available. Please install the requests library: pip install requests"

        try:
            # Extract location from message
            location = self._extract_location(message)
            weather_service = get_weather_service()

            # Get weather data
            return weather_service.get_weather_summary(location)

        except Exception as e:
            logger.error(f"Weather service error: {e}")
            return f"I couldn't fetch the weather information: {str(e)}"

    # Known multi-word cities for better extraction
    _KNOWN_CITIES = {
        'new york', 'new york city', 'los angeles', 'san francisco',
        'las vegas', 'hong kong', 'kuala lumpur', 'buenos aires',
        'rio de janeiro', 'sao paulo', 'mexico city', 'cape town',
        'tel aviv', 'abu dhabi', 'sri lanka', 'costa rica',
        'el paso', 'salt lake city', 'kansas city', 'oklahoma city',
        'san diego', 'san antonio', 'st louis', 'st petersburg',
    }

    def _extract_location(self, message: str) -> str:
        """Extract location from user message"""
        message_lower = message.lower().strip()

        # Check for known multi-word cities first
        for city in self._KNOWN_CITIES:
            if city in message_lower:
                return city

        # Noise words to strip from location
        noise_words = {'today', 'tomorrow', 'now', 'please', 'the', 'like',
                       'right', 'currently', 'outside', 'there', 'is', 'it',
                       "what's", "what", "how", "tell", "me', 'about", 'show'}

        # Keywords that precede a location
        location_keywords = ['in', 'for', 'at', 'near']
        words = message_lower.split()

        # Try to find location after keywords
        for i, word in enumerate(words):
            if word in location_keywords and i + 1 < len(words):
                # Get remaining words as potential location
                remaining = words[i + 1:]
                # Strip noise words from end
                while remaining and remaining[-1].rstrip('?.,!') in noise_words:
                    remaining.pop()
                # Strip noise words from start
                while remaining and remaining[0] in noise_words:
                    remaining.pop(0)
                potential_location = ' '.join(remaining).strip('?.,! ')
                if potential_location:
                    return potential_location

        # Default to auto-detection
        return "auto"

    def generate_welcome_message(self) -> str:
        """Generate personalized welcome message"""
        now = datetime.now()
        hour = now.hour

        # Time-based greeting
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        try:
            # Get pending tasks
            tasks = self.db.get_pending_tasks()
            high_priority = [t for t in tasks if t['priority'] == 'high']
            today_tasks = self.db.get_tasks_for_today()

            message_parts = [f"{greeting}, {USER_NAME}! Welcome back."]

            if high_priority:
                message_parts.append(f"\n\nYou have {len(high_priority)} high-priority task(s):")
                for t in high_priority[:3]:
                    message_parts.append(f"  - {t['title']}")

            if today_tasks and len(today_tasks) != len(high_priority):
                message_parts.append(f"\n{len(today_tasks)} task(s) due today.")

            # Add productivity insight
            stats = self.db.get_productivity_stats(7)
            if stats['tasks_completed'] > 0:
                message_parts.append(f"\nYou've completed {stats['tasks_completed']} tasks this week!")

            message_parts.append("\n\nHow can I help you today?")

            return "\n".join(message_parts)

        except Exception as e:
            logger.warning(f"Error generating welcome: {e}")
            return f"{greeting}, {USER_NAME}! How can I help you today?"

    def generate_daily_summary(self) -> str:
        """Generate end-of-day summary"""
        today = date.today().isoformat()

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM tasks
                    WHERE status = 'completed' AND date(completed_at) = ?
                ''', (today,))
                completed = [dict(row) for row in cursor.fetchall()]

            pending = self.db.get_pending_tasks()
            logs = self.db.get_today_logs()
            total_minutes = sum(l['duration_minutes'] or 0 for l in logs)

            # Build summary
            summary_parts = [f"Daily Summary for {today}", "=" * 40]

            summary_parts.append(f"\nTasks Completed: {len(completed)}")
            if completed:
                for t in completed[:5]:
                    summary_parts.append(f"  - {t['title']}")
                if len(completed) > 5:
                    summary_parts.append(f"  ... and {len(completed) - 5} more")

            summary_parts.append(f"\nPending Tasks: {len(pending)}")
            high_pending = [t for t in pending if t['priority'] == 'high']
            if high_pending:
                summary_parts.append(f"  ({len(high_pending)} high priority)")

            summary_parts.append(f"\nActivities Logged: {len(logs)}")
            if total_minutes > 0:
                hours = total_minutes // 60
                mins = total_minutes % 60
                summary_parts.append(f"Total tracked time: {hours}h {mins}m")

            # Productivity score
            if completed or logs:
                score = min(100, (len(completed) * 10) + (len(logs) * 5))
                summary_parts.append(f"\nProductivity Score: {score}/100")

            summary = "\n".join(summary_parts)

            # Save summary to DB
            self.db.save_daily_summary(
                summary=summary,
                tasks_completed=len(completed),
                tasks_pending=len(pending),
                work_hours=total_minutes / 60,
                highlights=f"Completed {len(completed)} tasks" if completed else None
            )

            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Unable to generate summary: {e}"

    def get_behavior_suggestions(self) -> List[str]:
        """Analyze patterns and provide behavior suggestions"""
        suggestions = []

        try:
            patterns = self.db.get_patterns(3)
            stats = self.db.get_productivity_stats(7)

            # Productivity suggestions
            if stats['tasks_completed'] < 5:
                suggestions.append("Try breaking down large tasks into smaller, manageable pieces.")

            if stats['activities_logged'] < 10:
                suggestions.append("Consider logging more activities to better track your productivity.")

            # Pattern-based suggestions
            for pattern in patterns:
                if pattern.get('suggestion'):
                    suggestions.append(pattern['suggestion'])

            # Time-based suggestions
            hour = datetime.now().hour
            if hour >= 22:
                suggestions.append("It's getting late. Consider wrapping up and getting some rest.")
            elif 17 <= hour < 18:
                suggestions.append("End of work day approaching. Time to review today's progress!")

        except Exception as e:
            logger.warning(f"Error getting suggestions: {e}")

        return suggestions if suggestions else ["Keep up the great work!"]

    def get_status(self) -> Dict:
        """Get AI engine status"""
        return {
            "model": self.model,
            "ollama_available": self.ollama_available,
            "ollama_library_available": OLLAMA_AVAILABLE,
            "last_health_check": self._health_check._last_check,
            "cache_size": len(self._response_cache),
        }


# Global instance
_ai_instance = None
_ai_lock = threading.Lock()


def get_ai() -> JarvisAI:
    """Get the AI engine instance (thread-safe singleton)"""
    global _ai_instance
    if _ai_instance is None:
        with _ai_lock:
            if _ai_instance is None:
                _ai_instance = JarvisAI()
    return _ai_instance
