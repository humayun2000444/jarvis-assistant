"""
JARVIS Database Module - Robust SQLite storage with error handling and recovery
"""
import sqlite3
import threading
import time
import atexit
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import json

from core.logger import get_logger, log_exceptions, ExceptionHandler, audit_log

logger = get_logger("database")


class DatabaseError(Exception):
    """Custom database exception"""
    pass


class ConnectionPool:
    """Thread-safe connection pool for SQLite"""

    def __init__(self, db_path: Path, max_connections: int = 5):
        self.db_path = str(db_path)
        self.max_connections = max_connections
        self._pool: List[sqlite3.Connection] = []
        self._in_use: Dict[int, sqlite3.Connection] = {}
        self._lock = threading.Lock()
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool"""
        thread_id = threading.get_ident()

        with self._lock:
            # Check if this thread already has a connection
            if thread_id in self._in_use:
                return self._in_use[thread_id]

            # Try to get from pool
            if self._pool:
                conn = self._pool.pop()
            else:
                # Create new connection
                conn = self._create_connection()

            self._in_use[thread_id] = conn
            return conn

    def release_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool"""
        thread_id = threading.get_ident()

        with self._lock:
            if thread_id in self._in_use:
                del self._in_use[thread_id]

            if len(self._pool) < self.max_connections:
                self._pool.append(conn)
            else:
                conn.close()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper settings"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
            isolation_level='DEFERRED'
        )
        conn.row_factory = sqlite3.Row

        # Enable foreign keys and WAL mode for better concurrency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout

        return conn

    def close_all(self):
        """Close all connections"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()

            for conn in self._in_use.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._in_use.clear()


class JarvisDB:
    """Robust database manager with error handling and retry logic"""

    MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._pool = ConnectionPool(db_path)
        self._lock = threading.RLock()
        self._initialized = False

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.init_db()
        atexit.register(self.close)
        logger.info(f"Database initialized at {db_path}")

    @contextmanager
    def get_connection(self):
        """Context manager for getting a database connection"""
        conn = self._pool.get_connection()
        try:
            yield conn
        finally:
            pass  # Keep connection in pool for thread reuse

    @contextmanager
    def transaction(self):
        """Context manager for transactions with automatic rollback"""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction rolled back: {e}")
                raise

    def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute database operation with retry logic"""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return operation(*args, **kwargs)
            except sqlite3.OperationalError as e:
                last_error = e
                if "database is locked" in str(e).lower():
                    logger.warning(f"Database locked, attempt {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise
            except sqlite3.IntegrityError as e:
                logger.error(f"Integrity error: {e}")
                raise DatabaseError(f"Data integrity error: {e}")
            except Exception as e:
                logger.error(f"Database error: {e}")
                raise DatabaseError(f"Database operation failed: {e}")

        raise DatabaseError(f"Operation failed after {self.MAX_RETRIES} attempts: {last_error}")

    @log_exceptions("database")
    def init_db(self):
        """Initialize database with required tables"""
        if self._initialized:
            return

        def _init():
            with self.transaction() as conn:
                cursor = conn.cursor()

                # Tasks table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
                        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'cancelled')),
                        due_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        completed_at TEXT,
                        category TEXT,
                        reminder_time TEXT
                    )
                ''')

                # Daily notes/work log
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS daily_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        activity TEXT NOT NULL,
                        category TEXT,
                        duration_minutes INTEGER CHECK(duration_minutes >= 0),
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Conversation history
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                        content TEXT NOT NULL,
                        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Behavior patterns
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_type TEXT NOT NULL,
                        pattern_data TEXT NOT NULL,
                        occurrences INTEGER DEFAULT 1 CHECK(occurrences > 0),
                        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        suggestion TEXT
                    )
                ''')

                # Daily summaries
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT UNIQUE NOT NULL,
                        summary TEXT NOT NULL,
                        tasks_completed INTEGER DEFAULT 0,
                        tasks_pending INTEGER DEFAULT 0,
                        total_work_hours REAL DEFAULT 0,
                        highlights TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # User preferences
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        learned_from TEXT,
                        confidence REAL DEFAULT 0.5 CHECK(confidence >= 0 AND confidence <= 1),
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_logs_date ON daily_logs(date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)')

                self._initialized = True
                logger.info("Database tables initialized successfully")

        self._execute_with_retry(_init)

    # ============ TASK METHODS ============
    def add_task(self, title: str, description: str = "", priority: str = "medium",
                 due_date: str = None, category: str = None, reminder_time: str = None) -> int:
        """Add a new task"""
        if not title or not title.strip():
            raise DatabaseError("Task title cannot be empty")

        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        def _add():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tasks (title, description, priority, due_date, category, reminder_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (title.strip(), description, priority, due_date, category, reminder_time))
                task_id = cursor.lastrowid
                audit_log("task_created", f"Task #{task_id}: {title}")
                return task_id

        return self._execute_with_retry(_add)

    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks sorted by priority"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM tasks WHERE status = 'pending'
                    ORDER BY
                        CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                        due_date NULLS LAST
                ''')
                return [dict(row) for row in cursor.fetchall()]

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    def get_tasks_for_today(self) -> List[Dict]:
        """Get tasks due today"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                today = date.today().isoformat()
                cursor.execute('''
                    SELECT * FROM tasks
                    WHERE (due_date = ? OR due_date IS NULL) AND status = 'pending'
                    ORDER BY priority
                ''', (today,))
                return [dict(row) for row in cursor.fetchall()]

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed"""
        def _complete():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks SET status = 'completed', completed_at = ?
                    WHERE id = ? AND status = 'pending'
                ''', (datetime.now().isoformat(), task_id))
                success = cursor.rowcount > 0
                if success:
                    audit_log("task_completed", f"Task #{task_id}")
                return success

        return self._execute_with_retry(_complete)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task"""
        def _delete():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
                success = cursor.rowcount > 0
                if success:
                    audit_log("task_deleted", f"Task #{task_id}")
                return success

        return self._execute_with_retry(_delete)

    # ============ DAILY LOG METHODS ============
    def log_activity(self, activity: str, category: str = None,
                     duration_minutes: int = None, notes: str = None) -> int:
        """Log a daily activity"""
        if not activity or not activity.strip():
            raise DatabaseError("Activity cannot be empty")

        def _log():
            with self.transaction() as conn:
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute('''
                    INSERT INTO daily_logs (date, time, activity, category, duration_minutes, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (now.date().isoformat(), now.time().isoformat(), activity.strip(),
                      category, duration_minutes, notes))
                return cursor.lastrowid

        return self._execute_with_retry(_log)

    def get_today_logs(self) -> List[Dict]:
        """Get today's activity logs"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                today = date.today().isoformat()
                cursor.execute('SELECT * FROM daily_logs WHERE date = ? ORDER BY time', (today,))
                return [dict(row) for row in cursor.fetchall()]

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    def get_logs_for_date(self, target_date: str) -> List[Dict]:
        """Get logs for a specific date"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM daily_logs WHERE date = ? ORDER BY time', (target_date,))
                return [dict(row) for row in cursor.fetchall()]

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    # ============ CONVERSATION METHODS ============
    def add_message(self, role: str, content: str):
        """Add a conversation message"""
        if role not in ('user', 'assistant', 'system'):
            role = 'user'

        def _add():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO conversations (role, content) VALUES (?, ?)',
                               (role, content))

        with ExceptionHandler("database", reraise=False):
            self._execute_with_retry(_add)

    def get_recent_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent conversation messages"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT role, content, timestamp FROM conversations
                    ORDER BY timestamp DESC LIMIT ?
                ''', (min(limit, 100),))  # Cap at 100 for safety
                messages = [dict(row) for row in cursor.fetchall()]
                messages.reverse()
                return messages

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    def cleanup_old_messages(self, keep_days: int = 30):
        """Clean up old conversation messages"""
        def _cleanup():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM conversations
                    WHERE timestamp < datetime('now', ?)
                ''', (f'-{keep_days} days',))
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old conversation messages")
                return deleted

        return self._execute_with_retry(_cleanup)

    # ============ PATTERN METHODS ============
    def record_pattern(self, pattern_type: str, pattern_data: dict, suggestion: str = None):
        """Record a behavior pattern"""
        def _record():
            with self.transaction() as conn:
                cursor = conn.cursor()
                data_json = json.dumps(pattern_data, sort_keys=True)

                cursor.execute('''
                    SELECT id, occurrences FROM patterns
                    WHERE pattern_type = ? AND pattern_data = ?
                ''', (pattern_type, data_json))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE patterns SET occurrences = occurrences + 1, last_seen = ?
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), existing['id']))
                else:
                    cursor.execute('''
                        INSERT INTO patterns (pattern_type, pattern_data, suggestion)
                        VALUES (?, ?, ?)
                    ''', (pattern_type, data_json, suggestion))

        with ExceptionHandler("database", reraise=False):
            self._execute_with_retry(_record)

    def get_patterns(self, min_occurrences: int = 3) -> List[Dict]:
        """Get learned patterns"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM patterns WHERE occurrences >= ?
                    ORDER BY occurrences DESC
                ''', (min_occurrences,))
                patterns = []
                for row in cursor.fetchall():
                    p = dict(row)
                    try:
                        p['pattern_data'] = json.loads(p['pattern_data'])
                    except json.JSONDecodeError:
                        p['pattern_data'] = {}
                    patterns.append(p)
                return patterns

        with ExceptionHandler("database", reraise=False, fallback=[]):
            return self._execute_with_retry(_get)
        return []

    # ============ SUMMARY METHODS ============
    def save_daily_summary(self, summary: str, tasks_completed: int,
                          tasks_pending: int, work_hours: float, highlights: str = None):
        """Save daily summary"""
        def _save():
            with self.transaction() as conn:
                cursor = conn.cursor()
                today = date.today().isoformat()
                cursor.execute('''
                    INSERT OR REPLACE INTO summaries
                    (date, summary, tasks_completed, tasks_pending, total_work_hours, highlights)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (today, summary, tasks_completed, tasks_pending, work_hours, highlights))
                audit_log("summary_saved", f"Daily summary for {today}")

        with ExceptionHandler("database", reraise=False):
            self._execute_with_retry(_save)

    def get_summary(self, target_date: str = None) -> Optional[Dict]:
        """Get daily summary"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if target_date is None:
                    target_date_str = date.today().isoformat()
                else:
                    target_date_str = target_date
                cursor.execute('SELECT * FROM summaries WHERE date = ?', (target_date_str,))
                row = cursor.fetchone()
                return dict(row) if row else None

        with ExceptionHandler("database", reraise=False, fallback=None):
            return self._execute_with_retry(_get)
        return None

    # ============ PREFERENCES METHODS ============
    def set_preference(self, key: str, value: str, learned_from: str = None, confidence: float = 0.5):
        """Set a user preference"""
        def _set():
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO preferences (key, value, learned_from, confidence, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (key, value, learned_from, max(0, min(1, confidence)), datetime.now().isoformat()))

        with ExceptionHandler("database", reraise=False):
            self._execute_with_retry(_set)

    def get_preference(self, key: str) -> Optional[str]:
        """Get a preference value"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM preferences WHERE key = ?', (key,))
                row = cursor.fetchone()
                return row['value'] if row else None

        with ExceptionHandler("database", reraise=False, fallback=None):
            return self._execute_with_retry(_get)
        return None

    def get_all_preferences(self) -> Dict[str, str]:
        """Get all preferences"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM preferences')
                return {row['key']: row['value'] for row in cursor.fetchall()}

        with ExceptionHandler("database", reraise=False, fallback={}):
            return self._execute_with_retry(_get)
        return {}

    # ============ STATS METHODS ============
    def get_productivity_stats(self, days: int = 7) -> Dict:
        """Get productivity statistics"""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT COUNT(*) as count FROM tasks
                    WHERE status = 'completed'
                    AND completed_at >= date('now', ?)
                ''', (f'-{days} days',))
                tasks_completed = cursor.fetchone()['count']

                cursor.execute('''
                    SELECT COUNT(*) as count, COALESCE(SUM(duration_minutes), 0) as total_minutes
                    FROM daily_logs
                    WHERE date >= date('now', ?)
                ''', (f'-{days} days',))
                row = cursor.fetchone()

                return {
                    'tasks_completed': tasks_completed,
                    'activities_logged': row['count'] or 0,
                    'total_work_minutes': row['total_minutes'] or 0,
                    'period_days': days
                }

        with ExceptionHandler("database", reraise=False, fallback={
            'tasks_completed': 0, 'activities_logged': 0, 'total_work_minutes': 0, 'period_days': days
        }):
            return self._execute_with_retry(_get)
        return {'tasks_completed': 0, 'activities_logged': 0, 'total_work_minutes': 0, 'period_days': days}

    def vacuum(self):
        """Optimize database by running VACUUM"""
        def _vacuum():
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")

        with ExceptionHandler("database", reraise=False):
            self._execute_with_retry(_vacuum)

    def integrity_check(self) -> bool:
        """Check database integrity"""
        def _check():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                is_ok = result == "ok"
                if not is_ok:
                    logger.error(f"Database integrity check failed: {result}")
                return is_ok

        with ExceptionHandler("database", reraise=False, fallback=False):
            return self._execute_with_retry(_check)
        return False

    def close(self):
        """Close all database connections"""
        logger.info("Closing database connections")
        self._pool.close_all()


# Global instance
_db_instance = None
_db_lock = threading.Lock()


def get_db() -> JarvisDB:
    """Get the database instance (thread-safe singleton)"""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                from config.settings import DB_PATH
                _db_instance = JarvisDB(DB_PATH)
    return _db_instance
