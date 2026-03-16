#!/usr/bin/env python3
"""
JARVIS - Personal AI Assistant
Main entry point with robust error handling and graceful shutdown
"""
import sys
import os
import signal
import argparse
import atexit
import threading
from typing import Optional

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Global shutdown flag
_shutdown_event = threading.Event()
_cleanup_functions = []


def register_cleanup(func):
    """Register a cleanup function to be called on shutdown"""
    _cleanup_functions.append(func)


def graceful_shutdown(signum=None, frame=None):
    """Handle graceful shutdown"""
    if _shutdown_event.is_set():
        return  # Already shutting down

    _shutdown_event.set()
    print("\nShutting down JARVIS...")

    # Run cleanup functions in reverse order
    for func in reversed(_cleanup_functions):
        try:
            func()
        except Exception as e:
            print(f"Cleanup error: {e}")


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    atexit.register(graceful_shutdown)


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS - Your Personal AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jarvis              # Start interactive CLI
  jarvis --gui        # Start GUI application
  jarvis --daemon     # Run as background daemon
  jarvis --health     # Check system health
  jarvis --diagnose   # Run full diagnostics
  jarvis task add "Buy groceries" --priority high
  jarvis log "Working on project"
  jarvis summary      # Show daily summary
        """
    )

    parser.add_argument('--gui', '-g', action='store_true',
                        help='Launch GUI application')
    parser.add_argument('--daemon', '-d', action='store_true',
                        help='Run as background daemon with scheduler')
    parser.add_argument('--welcome', '-w', action='store_true',
                        help='Show welcome message')
    parser.add_argument('--summary', '-s', action='store_true',
                        help='Show daily summary')
    parser.add_argument('--setup', action='store_true',
                        help='Run initial setup')
    parser.add_argument('--health', action='store_true',
                        help='Check system health')
    parser.add_argument('--diagnose', action='store_true',
                        help='Run full diagnostics')
    parser.add_argument('--repair', metavar='COMPONENT',
                        help='Attempt to repair a component (database, logs, config)')
    parser.add_argument('--version', '-v', action='store_true',
                        help='Show version information')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--voice', action='store_true',
                        help='Start interactive voice conversation mode')
    parser.add_argument('--talk', action='store_true',
                        help='Quick voice interaction (listen and respond once)')

    # Parse known args to allow CLI subcommands
    args, remaining = parser.parse_known_args()

    # Setup signal handlers
    setup_signal_handlers()

    # Enable debug mode if requested
    if args.debug:
        os.environ['JARVIS_DEBUG'] = '1'

    try:
        if args.version:
            show_version()
        elif args.setup:
            run_setup()
        elif args.health:
            check_health()
        elif args.diagnose:
            run_diagnostics()
        elif args.repair:
            run_repair(args.repair)
        elif args.voice:
            run_voice_mode()
        elif args.talk:
            quick_talk()
        elif args.gui:
            run_gui()
        elif args.daemon:
            run_daemon()
        elif args.welcome:
            show_welcome()
        elif args.summary:
            show_summary()
        else:
            # Run CLI with remaining arguments
            run_cli(remaining)
    except KeyboardInterrupt:
        graceful_shutdown()
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def show_version():
    """Show version information"""
    print("JARVIS - Personal AI Assistant")
    print("Version: 1.0.0")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")


def run_setup():
    """Run initial setup with improved error handling"""
    print("=" * 50)
    print("JARVIS - Initial Setup")
    print("=" * 50)

    # Initialize logging first
    try:
        from core.logger import get_logger, setup_crash_handler
        setup_crash_handler()
        logger = get_logger("setup")
        logger.info("Starting setup")
    except Exception as e:
        print(f"Warning: Could not initialize logging: {e}")

    # Check Python version
    print(f"\n1. Python version: {sys.version}")
    if sys.version_info < (3, 8):
        print("   WARNING: Python 3.8+ is recommended")

    # Check for Ollama
    print("\n2. Checking Ollama...")
    try:
        import ollama
        models = ollama.list()
        print(f"   Ollama is installed. Available models:")
        for model in models.get('models', []):
            print(f"   - {model['name']}")
    except ImportError:
        print("   Ollama Python package not installed.")
        print("   Run: pip install ollama")
    except Exception as e:
        print(f"   Ollama not running: {e}")
        print("   Install: curl -fsSL https://ollama.ai/install.sh | sh")
        print("   Then run: ollama pull llama3.2:1b")

    # Check dependencies
    print("\n3. Checking dependencies...")
    dependencies = {
        'PyQt6': ('GUI application', True),
        'rich': ('CLI interface', True),
        'click': ('CLI commands', True),
        'apscheduler': ('Task scheduling', True),
        'plyer': ('Desktop notifications', False),
        'pyttsx3': ('Voice output', False),
        'psutil': ('System monitoring', False),
    }

    missing_required = []
    missing_optional = []

    for dep, (purpose, required) in dependencies.items():
        try:
            __import__(dep.lower().replace('-', '_').split('[')[0])
            print(f"   [OK] {dep} - {purpose}")
        except ImportError:
            status = "[MISSING]" if required else "[OPTIONAL]"
            print(f"   {status} {dep} - {purpose}")
            if required:
                missing_required.append(dep)
            else:
                missing_optional.append(dep)

    if missing_required:
        print(f"\n   Install required: pip install {' '.join(missing_required)}")

    if missing_optional:
        print(f"   Install optional: pip install {' '.join(missing_optional)}")

    # Initialize database
    print("\n4. Initializing database...")
    try:
        from core.database import get_db
        db = get_db()
        if db.integrity_check():
            print("   Database initialized and verified!")
        else:
            print("   WARNING: Database integrity check failed")
    except Exception as e:
        print(f"   ERROR: Database initialization failed: {e}")
        return

    # Create required directories
    print("\n5. Setting up directories...")
    from config.settings import BASE_DIR, DATA_DIR
    dirs = [
        DATA_DIR,
        DATA_DIR / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"   [OK] {d}")

    # Run health check
    print("\n6. Running health check...")
    try:
        from core.health import quick_health_check, HealthStatus
        status, summary = quick_health_check()
        status_str = {
            HealthStatus.HEALTHY: "[OK]",
            HealthStatus.DEGRADED: "[WARN]",
            HealthStatus.UNHEALTHY: "[FAIL]",
        }.get(status, "[???]")
        print(f"   {status_str} {summary}")
    except Exception as e:
        print(f"   Could not run health check: {e}")

    print("\n" + "=" * 50)
    print("Setup complete! Run 'jarvis' to start.")
    print("=" * 50)


def run_voice_mode():
    """Start interactive voice conversation mode"""
    try:
        from core.voice_assistant import start_voice_mode
        print("Starting JARVIS Voice Mode...")
        print("Speak naturally - JARVIS will listen and respond.")
        print("Say 'goodbye' to exit.\n")
        start_voice_mode()
    except ImportError as e:
        print(f"Error: Voice dependencies not installed: {e}")
        print("Install with: pip install SpeechRecognition edge-tts")
        sys.exit(1)
    except Exception as e:
        print(f"Voice mode error: {e}")
        sys.exit(1)


def quick_talk():
    """Quick voice interaction - listen once and respond"""
    try:
        from core.voice_assistant import get_voice_assistant

        assistant = get_voice_assistant()

        print("JARVIS is listening... (speak now)")
        text = assistant.listen_once(timeout=10.0)

        if text:
            print(f"You said: {text}")
            print("\nJARVIS is responding...")
            response = assistant.respond_to(text)
            print(f"\nJARVIS: {response}")
        else:
            print("Didn't catch that. Try again with: jarvis --talk")

    except ImportError as e:
        print(f"Error: Voice dependencies not installed: {e}")
        print("Install with: pip install SpeechRecognition edge-tts")
        sys.exit(1)
    except Exception as e:
        print(f"Voice error: {e}")
        sys.exit(1)


def run_gui():
    """Launch GUI application with crash protection"""
    try:
        from core.logger import setup_crash_handler
        setup_crash_handler()
    except Exception:
        pass

    try:
        from gui.main_window import run_gui as start_gui
        start_gui()
    except ImportError as e:
        print(f"Error: GUI dependencies not installed: {e}")
        print("Install with: pip install PyQt6")
        sys.exit(1)
    except Exception as e:
        print(f"GUI Error: {e}")
        # Try to save crash info
        try:
            from core.logger import get_logger
            logger = get_logger("gui")
            logger.critical(f"GUI crashed: {e}", exc_info=True)
        except Exception:
            pass
        sys.exit(1)


def run_daemon():
    """Run as background daemon with improved error handling"""
    try:
        from core.logger import setup_crash_handler, get_logger
        setup_crash_handler()
        logger = get_logger("daemon")
        logger.info("Starting JARVIS daemon")
    except Exception:
        pass

    from core.scheduler import get_scheduler

    scheduler = get_scheduler()
    register_cleanup(scheduler.stop)

    print("Starting JARVIS daemon...")
    scheduler.start()

    try:
        while not _shutdown_event.is_set():
            _shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()


def run_cli(args):
    """Run CLI interface"""
    try:
        from cli.main import cli
        sys.argv = ['jarvis'] + args
        cli()
    except ImportError as e:
        print(f"Error: CLI dependencies not installed: {e}")
        print("Install with: pip install rich click")
        sys.exit(1)


def show_welcome():
    """Show welcome message"""
    try:
        from core.ai_engine import get_ai
        ai = get_ai()
        print(ai.generate_welcome_message())
    except Exception as e:
        print(f"Error generating welcome: {e}")
        print("Welcome! JARVIS is ready to assist you.")


def show_summary():
    """Show daily summary"""
    try:
        from core.ai_engine import get_ai
        ai = get_ai()
        print(ai.generate_daily_summary())
    except Exception as e:
        print(f"Error generating summary: {e}")


def check_health():
    """Quick health check"""
    try:
        from core.health import quick_health_check, HealthStatus

        status, summary = quick_health_check()

        status_icon = {
            HealthStatus.HEALTHY: "[HEALTHY]",
            HealthStatus.DEGRADED: "[DEGRADED]",
            HealthStatus.UNHEALTHY: "[UNHEALTHY]",
            HealthStatus.UNKNOWN: "[UNKNOWN]",
        }.get(status, "[???]")

        print(f"JARVIS Health: {status_icon}")
        print(f"Summary: {summary}")

        if status == HealthStatus.UNHEALTHY:
            print("\nRun 'jarvis --diagnose' for detailed information")
            print("Run 'jarvis --repair <component>' to attempt repairs")
            sys.exit(1)
        elif status == HealthStatus.DEGRADED:
            print("\nSome components need attention. Run 'jarvis --diagnose' for details")

    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)


def run_diagnostics():
    """Run full diagnostics"""
    try:
        from core.health import get_diagnostics
        diag = get_diagnostics()
        print(diag.get_report())
    except Exception as e:
        print(f"Diagnostics failed: {e}")
        sys.exit(1)


def run_repair(component: str):
    """Attempt to repair a component"""
    try:
        from core.health import get_diagnostics
        diag = get_diagnostics()

        if not diag.can_repair(component):
            print(f"No repair available for '{component}'")
            print("Available repairs: database, logs, config")
            sys.exit(1)

        print(f"Attempting to repair {component}...")
        success, message = diag.repair(component)

        if success:
            print(f"[OK] {message}")
        else:
            print(f"[FAILED] {message}")
            sys.exit(1)

    except Exception as e:
        print(f"Repair failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
