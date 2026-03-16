"""
JARVIS AI Engine - Robust Ollama Integration with retry logic and fallbacks
"""
import subprocess
import json
import time
import threading
import queue
from typing import List, Dict, Optional, Generator, Callable
from datetime import datetime, date
from functools import wraps

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import AI_MODEL, AI_TEMPERATURE, PERSONALITY_PROMPT, USER_NAME, ASSISTANT_NAME
from core.database import get_db
from core.logger import get_logger, log_exceptions, ExceptionHandler

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

    def __init__(self):
        self.model = AI_MODEL
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

    def _get_cache_key(self, message: str) -> str:
        """Generate cache key for message"""
        return hash(message)

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

        # Get recent conversation history
        try:
            recent = self.db.get_recent_messages(10)
            messages = [{"role": m["role"], "content": m["content"]} for m in recent]
        except Exception as e:
            logger.warning(f"Failed to get recent messages: {e}")
            messages = []

        # Try Ollama first
        reply = None
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

        try:
            recent = self.db.get_recent_messages(10)
            messages = [{"role": m["role"], "content": m["content"]} for m in recent]
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
            return f"""I'm {ASSISTANT_NAME}, your personal assistant. I can help you with:

- Task Management: "Add task...", "Show tasks", "Complete task #..."
- Activity Logging: "Log activity...", "What did I do today?"
- Daily Summaries: "Show summary", "How was my day?"
- Productivity Stats: "Show stats", "How productive am I?"
- Reminders: "Remind me to..."
- Suggestions: "Give me suggestions"

Note: For full AI capabilities, Ollama should be running.
Current status: {'Ready' if self.ollama_available else 'Offline (using basic responses)'}"""

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
        elif any(word in message_lower for word in ['log', 'activity', 'work']):
            return "activity_logging"
        elif any(word in message_lower for word in ['summary', 'report', 'stats']):
            return "reporting"
        elif any(word in message_lower for word in ['help', 'how', 'what']):
            return "help_query"
        return "general"

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
