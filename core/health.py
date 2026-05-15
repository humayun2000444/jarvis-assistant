#!/usr/bin/env python3
"""
JARVIS Health Check and Self-Diagnostics System
"""
import os
import sys
import time
import threading
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from core.logger import get_logger

logger = get_logger("health")


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    checks: List[HealthCheckResult]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def summary(self) -> str:
        """Get health summary"""
        healthy = sum(1 for c in self.checks if c.status == HealthStatus.HEALTHY)
        total = len(self.checks)
        return f"{healthy}/{total} checks passed"


class HealthChecker:
    """Performs health checks on JARVIS components"""

    def __init__(self):
        self._checks = []
        self._last_check: Optional[SystemHealth] = None
        self._lock = threading.Lock()

        # Register default checks
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check("database", self._check_database)
        self.register_check("ai_engine", self._check_ai_engine)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory", self._check_memory)
        self.register_check("config", self._check_config)
        self.register_check("logs", self._check_logs)
        self.register_check("dependencies", self._check_dependencies)

    def register_check(self, name: str, check_func):
        """Register a health check"""
        self._checks.append((name, check_func))

    def _run_check(self, name: str, check_func) -> HealthCheckResult:
        """Run a single health check"""
        start = time.time()
        try:
            status, message, details = check_func()
            duration = (time.time() - start) * 1000
            return HealthCheckResult(
                name=name,
                status=status,
                message=message,
                details=details,
                duration_ms=duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Health check {name} failed: {e}")
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                duration_ms=duration
            )

    def run_all_checks(self) -> SystemHealth:
        """Run all health checks"""
        with self._lock:
            results = []
            for name, check_func in self._checks:
                result = self._run_check(name, check_func)
                results.append(result)

            # Determine overall status
            if all(r.status == HealthStatus.HEALTHY for r in results):
                overall = HealthStatus.HEALTHY
            elif any(r.status == HealthStatus.UNHEALTHY for r in results):
                overall = HealthStatus.UNHEALTHY
            elif any(r.status == HealthStatus.DEGRADED for r in results):
                overall = HealthStatus.DEGRADED
            else:
                overall = HealthStatus.UNKNOWN

            self._last_check = SystemHealth(
                status=overall,
                checks=results
            )

            return self._last_check

    def get_last_check(self) -> Optional[SystemHealth]:
        """Get last health check result"""
        return self._last_check

    # ============ Individual Health Checks ============

    def _check_database(self) -> Tuple[HealthStatus, str, Dict]:
        """Check database health"""
        from core.database import get_db

        try:
            db = get_db()

            # Check connection
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")

            # Check integrity
            is_ok = db.integrity_check()
            if not is_ok:
                return HealthStatus.UNHEALTHY, "Database integrity check failed", {}

            # Get stats
            stats = db.get_productivity_stats(1)

            return HealthStatus.HEALTHY, "Database is healthy", {
                "tasks_today": stats.get('tasks_completed', 0),
                "activities_today": stats.get('activities_logged', 0),
            }

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Database error: {e}", {}

    def _check_ai_engine(self) -> Tuple[HealthStatus, str, Dict]:
        """Check AI engine health"""
        from core.ai_engine import get_ai, OLLAMA_AVAILABLE

        try:
            ai = get_ai()
            status = ai.get_status()

            if not OLLAMA_AVAILABLE:
                return HealthStatus.DEGRADED, "Ollama library not installed", status

            if not status.get('ollama_available'):
                return HealthStatus.DEGRADED, "Ollama service not running", status

            return HealthStatus.HEALTHY, "AI engine is ready", status

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"AI engine error: {e}", {}

    def _check_disk_space(self) -> Tuple[HealthStatus, str, Dict]:
        """Check available disk space"""
        from config.settings import BASE_DIR

        try:
            usage = shutil.disk_usage(BASE_DIR)
            percent_used = (usage.used / usage.total) * 100
            free_gb = usage.free / (1024**3)

            details = {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(free_gb, 2),
                "percent_used": round(percent_used, 1),
            }

            if percent_used > 95:
                return HealthStatus.UNHEALTHY, f"Disk almost full ({percent_used:.1f}%)", details
            elif percent_used > 85:
                return HealthStatus.DEGRADED, f"Disk space low ({free_gb:.1f} GB free)", details

            return HealthStatus.HEALTHY, f"{free_gb:.1f} GB free", details

        except Exception as e:
            return HealthStatus.UNKNOWN, f"Could not check disk space: {e}", {}

    def _check_memory(self) -> Tuple[HealthStatus, str, Dict]:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()

            details = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent_used": memory.percent,
            }

            if memory.percent > 95:
                return HealthStatus.UNHEALTHY, f"Memory critical ({memory.percent}%)", details
            elif memory.percent > 85:
                return HealthStatus.DEGRADED, f"Memory high ({memory.percent}%)", details

            return HealthStatus.HEALTHY, f"{memory.available / (1024**3):.1f} GB available", details

        except ImportError:
            return HealthStatus.UNKNOWN, "psutil not installed", {}
        except Exception as e:
            return HealthStatus.UNKNOWN, f"Could not check memory: {e}", {}

    def _check_config(self) -> Tuple[HealthStatus, str, Dict]:
        """Check configuration"""
        try:
            from config.settings import (
                BASE_DIR, DATA_DIR, DB_PATH, AI_MODEL,
                USER_NAME, ASSISTANT_NAME
            )

            issues = []
            details = {
                "base_dir": str(BASE_DIR),
                "data_dir": str(DATA_DIR),
                "ai_model": AI_MODEL,
                "user_name": USER_NAME,
                "assistant_name": ASSISTANT_NAME,
            }

            # Check directories exist
            if not BASE_DIR.exists():
                issues.append("Base directory missing")
            if not DATA_DIR.exists():
                issues.append("Data directory missing")

            # Check database file
            if not DB_PATH.exists():
                issues.append("Database file not found (will be created)")

            if issues:
                return HealthStatus.DEGRADED, "; ".join(issues), details

            return HealthStatus.HEALTHY, "Configuration valid", details

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Config error: {e}", {}

    def _check_logs(self) -> Tuple[HealthStatus, str, Dict]:
        """Check log files"""
        try:
            from config.settings import BASE_DIR

            log_dir = BASE_DIR / "data" / "logs"
            details = {"log_dir": str(log_dir)}

            if not log_dir.exists():
                return HealthStatus.DEGRADED, "Log directory not found", details

            # Check log file sizes
            total_size = 0
            log_files = list(log_dir.glob("*.log"))
            details["log_files"] = len(log_files)

            for log_file in log_files:
                total_size += log_file.stat().st_size

            details["total_size_mb"] = round(total_size / (1024*1024), 2)

            if total_size > 100 * 1024 * 1024:  # 100 MB
                return HealthStatus.DEGRADED, "Log files are large", details

            return HealthStatus.HEALTHY, f"{len(log_files)} log files", details

        except Exception as e:
            return HealthStatus.UNKNOWN, f"Could not check logs: {e}", {}

    def _check_dependencies(self) -> Tuple[HealthStatus, str, Dict]:
        """Check required dependencies"""
        # Map package names to their import names
        required = {
            'PyQt6': 'PyQt6.QtCore',
            'apscheduler': 'apscheduler',
            'rich': 'rich'
        }
        optional = {
            'ollama': 'ollama',
            'psutil': 'psutil',
            'pyttsx3': 'pyttsx3',
            'plyer': 'plyer'
        }

        details = {"required": {}, "optional": {}}
        missing_required = []
        missing_optional = []

        for pkg, import_name in required.items():
            try:
                __import__(import_name)
                details["required"][pkg] = "installed"
            except ImportError:
                details["required"][pkg] = "missing"
                missing_required.append(pkg)

        for pkg, import_name in optional.items():
            try:
                __import__(import_name)
                details["optional"][pkg] = "installed"
            except ImportError:
                details["optional"][pkg] = "missing"
                missing_optional.append(pkg)

        if missing_required:
            return HealthStatus.UNHEALTHY, f"Missing: {', '.join(missing_required)}", details

        if missing_optional:
            return HealthStatus.DEGRADED, f"Optional missing: {', '.join(missing_optional)}", details

        return HealthStatus.HEALTHY, "All dependencies installed", details


class SelfDiagnostics:
    """Self-diagnostics and repair capabilities"""

    def __init__(self):
        self._health_checker = HealthChecker()
        self._repairs_available = {
            "database": self._repair_database,
            "logs": self._repair_logs,
            "config": self._repair_config,
        }

    def diagnose(self) -> SystemHealth:
        """Run full diagnostics"""
        return self._health_checker.run_all_checks()

    def can_repair(self, check_name: str) -> bool:
        """Check if a component can be repaired"""
        return check_name in self._repairs_available

    def repair(self, check_name: str) -> Tuple[bool, str]:
        """Attempt to repair a component"""
        if check_name not in self._repairs_available:
            return False, f"No repair available for {check_name}"

        try:
            return self._repairs_available[check_name]()
        except Exception as e:
            logger.error(f"Repair failed for {check_name}: {e}")
            return False, str(e)

    def _repair_database(self) -> Tuple[bool, str]:
        """Attempt database repair"""
        from core.database import get_db

        try:
            db = get_db()

            # Try to vacuum and check integrity
            db.vacuum()

            if db.integrity_check():
                return True, "Database repaired successfully"
            else:
                return False, "Database integrity still failing after repair"

        except Exception as e:
            return False, f"Repair failed: {e}"

    def _repair_logs(self) -> Tuple[bool, str]:
        """Repair log directory"""
        from config.settings import BASE_DIR

        try:
            log_dir = BASE_DIR / "data" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            # Rotate large log files
            for log_file in log_dir.glob("*.log"):
                if log_file.stat().st_size > 50 * 1024 * 1024:  # 50 MB
                    backup = log_file.with_suffix('.log.old')
                    if backup.exists():
                        backup.unlink()
                    log_file.rename(backup)
                    log_file.touch()

            return True, "Log directory repaired"

        except Exception as e:
            return False, f"Repair failed: {e}"

    def _repair_config(self) -> Tuple[bool, str]:
        """Repair configuration"""
        from config.settings import BASE_DIR, DATA_DIR

        try:
            # Ensure directories exist
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            (DATA_DIR / "logs").mkdir(exist_ok=True)

            return True, "Configuration directories created"

        except Exception as e:
            return False, f"Repair failed: {e}"

    def get_report(self) -> str:
        """Generate diagnostic report"""
        health = self.diagnose()
        lines = [
            "=" * 50,
            "JARVIS DIAGNOSTIC REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            "",
            f"Overall Status: {health.status.value.upper()}",
            f"Summary: {health.summary}",
            "",
            "-" * 50,
            "Component Details:",
            "-" * 50,
        ]

        for check in health.checks:
            status_icon = {
                HealthStatus.HEALTHY: "[OK]",
                HealthStatus.DEGRADED: "[WARN]",
                HealthStatus.UNHEALTHY: "[FAIL]",
                HealthStatus.UNKNOWN: "[???]",
            }.get(check.status, "[???]")

            lines.append(f"\n{status_icon} {check.name.upper()}")
            lines.append(f"    Status: {check.status.value}")
            lines.append(f"    Message: {check.message}")
            lines.append(f"    Duration: {check.duration_ms:.1f}ms")

            if check.details:
                lines.append("    Details:")
                for key, value in check.details.items():
                    lines.append(f"      - {key}: {value}")

        lines.extend([
            "",
            "=" * 50,
            "END OF REPORT",
            "=" * 50,
        ])

        return "\n".join(lines)


# Global instances
_health_checker = None
_diagnostics = None


def get_health_checker() -> HealthChecker:
    """Get the health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def get_diagnostics() -> SelfDiagnostics:
    """Get the diagnostics instance"""
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = SelfDiagnostics()
    return _diagnostics


def quick_health_check() -> Tuple[HealthStatus, str]:
    """Quick health check returning status and message"""
    checker = get_health_checker()
    health = checker.run_all_checks()
    return health.status, health.summary


if __name__ == "__main__":
    # Run diagnostics when executed directly
    diag = get_diagnostics()
    print(diag.get_report())
