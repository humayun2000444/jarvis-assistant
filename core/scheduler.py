#!/usr/bin/env python3
"""
JARVIS Scheduler - Robust automated tasks with error recovery and monitoring
"""
import sys
import os
import threading
import time
import signal
import atexit
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

from config.settings import (
    ASSISTANT_NAME, USER_NAME, WORK_START_HOUR, WORK_END_HOUR,
    ENABLE_VOICE, ENABLE_DESKTOP_NOTIFICATIONS, REMINDER_INTERVAL_MINUTES
)
from core.database import get_db
from core.logger import get_logger, log_exceptions, ExceptionHandler

logger = get_logger("scheduler")


def safe_job(func: Callable) -> Callable:
    """Decorator to make jobs safe (catch all exceptions)"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Job {func.__name__} failed: {e}", exc_info=True)
            return None
    return wrapper


class TTSManager:
    """Thread-safe text-to-speech manager"""

    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self._speaking = False
        self._enabled = TTS_AVAILABLE and ENABLE_VOICE
        self._initialized = False

    def _init_engine(self):
        """Lazy initialize TTS engine"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            if not TTS_AVAILABLE:
                self._initialized = True
                return

            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', 150)
                self._initialized = True
                logger.info("TTS engine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize TTS: {e}")
                self._engine = None
                self._initialized = True

    def speak(self, text: str, block: bool = False):
        """Speak text (thread-safe)"""
        if not self._enabled:
            return

        self._init_engine()

        if not self._engine:
            return

        def _speak():
            with self._lock:
                if self._speaking:
                    return
                self._speaking = True

            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                logger.warning(f"TTS error: {e}")
            finally:
                self._speaking = False

        if block:
            _speak()
        else:
            thread = threading.Thread(target=_speak, daemon=True)
            thread.start()

    def stop(self):
        """Stop speaking"""
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        self._speaking = False


class NotificationManager:
    """Manage desktop notifications with rate limiting"""

    def __init__(self):
        self._last_notification = {}
        self._min_interval = 60  # Minimum seconds between same notifications
        self._lock = threading.Lock()

    def notify(self, title: str, message: str, category: str = "general") -> bool:
        """Send notification with rate limiting"""
        if not NOTIFICATIONS_AVAILABLE or not ENABLE_DESKTOP_NOTIFICATIONS:
            return False

        with self._lock:
            now = time.time()
            last = self._last_notification.get(category, 0)

            if (now - last) < self._min_interval:
                logger.debug(f"Rate limited notification: {category}")
                return False

            self._last_notification[category] = now

        try:
            notification.notify(
                title=title,
                message=message[:200],  # Truncate long messages
                app_name=ASSISTANT_NAME,
                timeout=10
            )
            logger.debug(f"Notification sent: {title}")
            return True
        except Exception as e:
            logger.warning(f"Notification error: {e}")
            return False


class JobMonitor:
    """Monitor job execution and health"""

    def __init__(self):
        self._job_stats: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def record_execution(self, job_id: str, success: bool, duration: float, error: str = None):
        """Record job execution"""
        with self._lock:
            if job_id not in self._job_stats:
                self._job_stats[job_id] = {
                    'total_runs': 0,
                    'successful_runs': 0,
                    'failed_runs': 0,
                    'total_duration': 0,
                    'last_run': None,
                    'last_error': None,
                    'consecutive_failures': 0,
                }

            stats = self._job_stats[job_id]
            stats['total_runs'] += 1
            stats['total_duration'] += duration
            stats['last_run'] = datetime.now()

            if success:
                stats['successful_runs'] += 1
                stats['consecutive_failures'] = 0
            else:
                stats['failed_runs'] += 1
                stats['consecutive_failures'] += 1
                stats['last_error'] = error

    def get_stats(self, job_id: str = None) -> Dict:
        """Get job statistics"""
        with self._lock:
            if job_id:
                return self._job_stats.get(job_id, {}).copy()
            return {k: v.copy() for k, v in self._job_stats.items()}

    def is_healthy(self, job_id: str, max_failures: int = 5) -> bool:
        """Check if job is healthy"""
        with self._lock:
            stats = self._job_stats.get(job_id)
            if not stats:
                return True
            return stats['consecutive_failures'] < max_failures


class JarvisScheduler:
    """Robust scheduler with monitoring and error recovery"""

    def __init__(self):
        self._db = None
        self._ai = None
        self._scheduler = None
        self._tts = TTSManager()
        self._notifications = NotificationManager()
        self._monitor = JobMonitor()
        self._running = False
        self._lock = threading.Lock()

        # Setup signal handlers
        self._setup_signal_handlers()

        logger.info("Scheduler initialized")

    @property
    def db(self):
        """Lazy load database"""
        if self._db is None:
            self._db = get_db()
        return self._db

    @property
    def ai(self):
        """Lazy load AI engine"""
        if self._ai is None:
            from core.ai_engine import get_ai
            self._ai = get_ai()
        return self._ai

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        try:
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        except Exception:
            pass  # Signal handling may not work in all contexts

        atexit.register(self.stop)

    def _job_listener(self, event):
        """Listen to job events for monitoring"""
        job_id = event.job_id
        duration = 0

        if hasattr(event, 'scheduled_run_time') and hasattr(event, 'retval'):
            duration = (datetime.now() - event.scheduled_run_time).total_seconds()

        if event.code == EVENT_JOB_ERROR:
            error = str(event.exception) if event.exception else "Unknown error"
            self._monitor.record_execution(job_id, False, duration, error)
            logger.error(f"Job {job_id} failed: {error}")

            # Check if job needs to be disabled
            if not self._monitor.is_healthy(job_id):
                logger.warning(f"Job {job_id} has too many failures, consider checking")

        elif event.code == EVENT_JOB_EXECUTED:
            self._monitor.record_execution(job_id, True, duration)
            logger.debug(f"Job {job_id} completed successfully")

        elif event.code == EVENT_JOB_MISSED:
            logger.warning(f"Job {job_id} missed its scheduled time")

    def _setup_scheduler(self):
        """Setup the APScheduler instance"""
        if self._scheduler:
            return

        self._scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300,  # 5 minutes grace period
            }
        )

        # Add job listener
        self._scheduler.add_listener(
            self._job_listener,
            EVENT_JOB_ERROR | EVENT_JOB_EXECUTED | EVENT_JOB_MISSED
        )

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        # Morning welcome - at work start hour
        self._scheduler.add_job(
            self.morning_welcome,
            CronTrigger(hour=WORK_START_HOUR, minute=0),
            id='morning_welcome',
            replace_existing=True,
            name='Morning Welcome'
        )

        # End of day summary - at work end hour
        self._scheduler.add_job(
            self.end_of_day_summary,
            CronTrigger(hour=WORK_END_HOUR, minute=0),
            id='end_of_day_summary',
            replace_existing=True,
            name='End of Day Summary'
        )

        # Task reminders - every N minutes during work hours
        self._scheduler.add_job(
            self.check_pending_tasks,
            CronTrigger(minute=f'*/{REMINDER_INTERVAL_MINUTES}'),
            id='task_reminder',
            replace_existing=True,
            name='Task Reminder'
        )

        # Pattern learning - at midnight
        self._scheduler.add_job(
            self.learn_daily_patterns,
            CronTrigger(hour=0, minute=5),  # 5 minutes after midnight
            id='pattern_learning',
            replace_existing=True,
            name='Pattern Learning'
        )

        # Database maintenance - at 3 AM
        self._scheduler.add_job(
            self.database_maintenance,
            CronTrigger(hour=3, minute=0),
            id='db_maintenance',
            replace_existing=True,
            name='Database Maintenance'
        )

        # Health check - every hour
        self._scheduler.add_job(
            self.health_check,
            CronTrigger(minute=0),
            id='health_check',
            replace_existing=True,
            name='Health Check'
        )

        logger.info(f"Scheduled {len(self._scheduler.get_jobs())} jobs")

    def start(self):
        """Start the scheduler"""
        with self._lock:
            if self._running:
                logger.warning("Scheduler already running")
                return

            self._setup_scheduler()
            self._setup_jobs()
            self._scheduler.start()
            self._running = True

        logger.info(f"[{ASSISTANT_NAME}] Scheduler started")

    def stop(self):
        """Stop the scheduler gracefully"""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._scheduler:
                try:
                    self._scheduler.shutdown(wait=True)
                    logger.info(f"[{ASSISTANT_NAME}] Scheduler stopped gracefully")
                except Exception as e:
                    logger.error(f"Error stopping scheduler: {e}")
                finally:
                    self._scheduler = None

            self._tts.stop()

    def notify(self, title: str, message: str, speak: bool = True, category: str = "general"):
        """Send notification to user"""
        # Desktop notification
        self._notifications.notify(title, message, category)

        # Voice notification
        if speak and ENABLE_VOICE:
            self._tts.speak(message)

    @safe_job
    def morning_welcome(self):
        """Morning welcome routine"""
        logger.info("Running morning welcome")

        welcome = self.ai.generate_welcome_message()

        self.notify(
            f"Good Morning, {USER_NAME}!",
            welcome[:150],
            speak=True,
            category="welcome"
        )

    @safe_job
    def end_of_day_summary(self):
        """End of day summary"""
        logger.info("Running end of day summary")

        summary = self.ai.generate_daily_summary()
        stats = self.db.get_productivity_stats(1)

        short_summary = (
            f"Today's summary: {stats['tasks_completed']} tasks completed, "
            f"{stats['activities_logged']} activities logged. "
            "Great work today!"
        )

        self.notify(
            f"{ASSISTANT_NAME} - Daily Summary",
            short_summary,
            speak=True,
            category="summary"
        )

    @safe_job
    def check_pending_tasks(self):
        """Check for pending tasks and remind user"""
        now = datetime.now()

        # Only remind during work hours
        if now.hour < WORK_START_HOUR or now.hour >= WORK_END_HOUR:
            return

        # Check for high-priority tasks
        tasks = self.db.get_pending_tasks()
        high_priority = [t for t in tasks if t['priority'] == 'high']

        if high_priority:
            task_names = ", ".join([t['title'][:30] for t in high_priority[:3]])
            self.notify(
                "Task Reminder",
                f"You have {len(high_priority)} high-priority task(s): {task_names}",
                speak=False,
                category="task_high"
            )

        # Check for overdue tasks
        today = now.date().isoformat()
        overdue = [t for t in tasks if t['due_date'] and t['due_date'] < today]

        if overdue:
            self.notify(
                "Overdue Tasks",
                f"You have {len(overdue)} overdue task(s)!",
                speak=True,
                category="task_overdue"
            )

    @safe_job
    def learn_daily_patterns(self):
        """Learn patterns from daily activities"""
        logger.info("Running pattern learning")

        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        logs = self.db.get_logs_for_date(yesterday)

        if not logs:
            return

        # Analyze activity categories
        categories = {}
        for log in logs:
            cat = log['category'] or 'uncategorized'
            categories[cat] = categories.get(cat, 0) + 1

        # Record most common category
        if categories:
            most_common = max(categories, key=categories.get)
            self.db.record_pattern(
                "daily_focus",
                {"day": datetime.now().strftime("%A"), "category": most_common},
                f"You tend to focus on {most_common} tasks"
            )

        # Analyze activity times
        morning_logs = [l for l in logs if l['time'] < "12:00:00"]
        afternoon_logs = [l for l in logs if "12:00:00" <= l['time'] < "17:00:00"]
        evening_logs = [l for l in logs if l['time'] >= "17:00:00"]

        counts = {
            "morning": len(morning_logs),
            "afternoon": len(afternoon_logs),
            "evening": len(evening_logs)
        }
        most_productive = max(counts, key=counts.get)

        self.db.record_pattern(
            "productive_time",
            {"time_of_day": most_productive, "activity_count": counts[most_productive]},
            f"You're most productive in the {most_productive}"
        )

        logger.info(f"Learned patterns: focus={most_common if categories else 'none'}, productive_time={most_productive}")

    @safe_job
    def database_maintenance(self):
        """Perform database maintenance"""
        logger.info("Running database maintenance")

        # Clean up old conversation messages
        self.db.cleanup_old_messages(keep_days=30)

        # Vacuum database
        self.db.vacuum()

        # Check integrity
        if not self.db.integrity_check():
            logger.error("Database integrity check failed!")

    @safe_job
    def health_check(self):
        """Perform system health check"""
        logger.debug("Running health check")

        issues = []

        # Check database
        try:
            stats = self.db.get_productivity_stats(1)
        except Exception as e:
            issues.append(f"Database: {e}")

        # Check AI engine
        try:
            status = self.ai.get_status()
            if not status.get('ollama_available'):
                issues.append("Ollama AI not available")
        except Exception as e:
            issues.append(f"AI Engine: {e}")

        # Check job health
        for job_id, stats in self._monitor.get_stats().items():
            if stats.get('consecutive_failures', 0) >= 3:
                issues.append(f"Job {job_id} has {stats['consecutive_failures']} consecutive failures")

        if issues:
            logger.warning(f"Health check issues: {issues}")
        else:
            logger.debug("Health check passed")

    def remind_at(self, reminder_time: datetime, message: str) -> str:
        """Schedule a one-time reminder"""
        job_id = f"reminder_{int(datetime.now().timestamp())}"

        self._scheduler.add_job(
            lambda: self.notify("Reminder", message, speak=True, category="reminder"),
            'date',
            run_date=reminder_time,
            id=job_id,
            name=f"Reminder: {message[:30]}"
        )

        logger.info(f"Scheduled reminder '{message[:30]}' for {reminder_time}")
        return job_id

    def cancel_reminder(self, job_id: str) -> bool:
        """Cancel a scheduled reminder"""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Cancelled reminder {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel reminder {job_id}: {e}")
            return False

    def get_scheduled_jobs(self) -> list:
        """Get list of scheduled jobs"""
        if not self._scheduler:
            return []

        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger),
                'stats': self._monitor.get_stats(job.id),
            }
            for job in self._scheduler.get_jobs()
        ]

    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            'running': self._running,
            'jobs_count': len(self._scheduler.get_jobs()) if self._scheduler else 0,
            'tts_available': TTS_AVAILABLE,
            'notifications_available': NOTIFICATIONS_AVAILABLE,
            'job_stats': self._monitor.get_stats(),
        }


# Global instance
_scheduler_instance = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> JarvisScheduler:
    """Get the scheduler instance (thread-safe singleton)"""
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_lock:
            if _scheduler_instance is None:
                _scheduler_instance = JarvisScheduler()
    return _scheduler_instance


def run_scheduler():
    """Run scheduler as standalone process"""
    logger.info("Starting scheduler as standalone process")
    scheduler = get_scheduler()
    scheduler.start()

    try:
        while scheduler._running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        scheduler.stop()


if __name__ == '__main__':
    run_scheduler()
