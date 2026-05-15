"""Tests for JARVIS database module"""
import pytest
import tempfile
from pathlib import Path

from core.database import JarvisDB, DatabaseError


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test"""
    db_path = tmp_path / "test_jarvis.db"
    return JarvisDB(db_path)


class TestTaskCRUD:
    def test_add_task(self, db):
        task_id = db.add_task("Test task")
        assert task_id > 0

    def test_add_task_with_priority(self, db):
        task_id = db.add_task("High priority task", priority="high")
        tasks = db.get_pending_tasks()
        assert len(tasks) == 1
        assert tasks[0]['priority'] == 'high'

    def test_add_task_invalid_priority_defaults_medium(self, db):
        task_id = db.add_task("Task", priority="invalid")
        tasks = db.get_pending_tasks()
        assert tasks[0]['priority'] == 'medium'

    def test_add_task_empty_title_raises(self, db):
        with pytest.raises(DatabaseError):
            db.add_task("")

    def test_add_task_whitespace_title_raises(self, db):
        with pytest.raises(DatabaseError):
            db.add_task("   ")

    def test_get_pending_tasks_sorted_by_priority(self, db):
        db.add_task("Low task", priority="low")
        db.add_task("High task", priority="high")
        db.add_task("Medium task", priority="medium")

        tasks = db.get_pending_tasks()
        assert tasks[0]['priority'] == 'high'
        assert tasks[1]['priority'] == 'medium'
        assert tasks[2]['priority'] == 'low'

    def test_complete_task(self, db):
        task_id = db.add_task("To complete")
        assert db.complete_task(task_id) is True

        pending = db.get_pending_tasks()
        assert len(pending) == 0

    def test_complete_nonexistent_task(self, db):
        assert db.complete_task(9999) is False

    def test_complete_already_completed_task(self, db):
        task_id = db.add_task("Done task")
        db.complete_task(task_id)
        assert db.complete_task(task_id) is False

    def test_delete_task(self, db):
        task_id = db.add_task("To delete")
        assert db.delete_task(task_id) is True
        assert len(db.get_pending_tasks()) == 0

    def test_delete_nonexistent_task(self, db):
        assert db.delete_task(9999) is False

    def test_add_task_with_due_date(self, db):
        task_id = db.add_task("Due task", due_date="2026-12-31")
        tasks = db.get_pending_tasks()
        assert tasks[0]['due_date'] == '2026-12-31'


class TestActivityLog:
    def test_log_activity(self, db):
        log_id = db.log_activity("Worked on tests")
        assert log_id > 0

    def test_log_activity_empty_raises(self, db):
        with pytest.raises(DatabaseError):
            db.log_activity("")

    def test_get_today_logs(self, db):
        db.log_activity("Activity 1")
        db.log_activity("Activity 2")
        logs = db.get_today_logs()
        assert len(logs) == 2

    def test_log_with_duration(self, db):
        db.log_activity("Coding", duration_minutes=60)
        logs = db.get_today_logs()
        assert logs[0]['duration_minutes'] == 60


class TestConversations:
    def test_add_and_get_messages(self, db):
        db.add_message("user", "Hello")
        db.add_message("assistant", "Hi there")
        messages = db.get_recent_messages(10)
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[1]['role'] == 'assistant'

    def test_invalid_role_defaults_to_user(self, db):
        db.add_message("invalid_role", "Test")
        messages = db.get_recent_messages(10)
        assert messages[0]['role'] == 'user'

    def test_message_limit(self, db):
        for i in range(25):
            db.add_message("user", f"Message {i}")
        messages = db.get_recent_messages(10)
        assert len(messages) == 10


class TestPreferences:
    def test_set_and_get_preference(self, db):
        db.set_preference("theme", "dark")
        assert db.get_preference("theme") == "dark"

    def test_get_nonexistent_preference(self, db):
        assert db.get_preference("nonexistent") is None

    def test_update_preference(self, db):
        db.set_preference("key", "value1")
        db.set_preference("key", "value2")
        assert db.get_preference("key") == "value2"

    def test_get_all_preferences(self, db):
        db.set_preference("a", "1")
        db.set_preference("b", "2")
        prefs = db.get_all_preferences()
        assert prefs == {"a": "1", "b": "2"}


class TestStats:
    def test_productivity_stats_empty(self, db):
        stats = db.get_productivity_stats(7)
        assert stats['tasks_completed'] == 0
        assert stats['activities_logged'] == 0
        assert stats['total_work_minutes'] == 0

    def test_productivity_stats_with_data(self, db):
        db.add_task("Task 1")
        task_id = db.add_task("Task 2")
        db.complete_task(task_id)
        db.log_activity("Work", duration_minutes=30)

        stats = db.get_productivity_stats(7)
        assert stats['tasks_completed'] == 1
        assert stats['activities_logged'] == 1


class TestIntegrity:
    def test_integrity_check(self, db):
        assert db.integrity_check() is True

    def test_vacuum(self, db):
        db.add_task("Test")
        db.delete_task(1)
        db.vacuum()  # Should not raise
