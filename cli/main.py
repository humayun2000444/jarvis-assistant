#!/usr/bin/env python3
"""
JARVIS CLI - Command Line Interface
"""
import sys
import os

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from datetime import datetime

from config.settings import ASSISTANT_NAME, USER_NAME
from core.database import get_db
from core.ai_engine import get_ai

console = Console()
db = get_db()
ai = get_ai()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """JARVIS - Your Personal AI Assistant"""
    if ctx.invoked_subcommand is None:
        # Interactive mode
        interactive_mode()


def interactive_mode():
    """Run interactive chat mode"""
    console.print(Panel.fit(
        f"[bold cyan]{ASSISTANT_NAME}[/bold cyan] - Personal AI Assistant\n"
        f"Type 'help' for commands, 'exit' to quit",
        title="Welcome",
        border_style="cyan"
    ))

    # Show welcome message
    welcome = ai.generate_welcome_message()
    console.print(f"\n[cyan]{ASSISTANT_NAME}:[/cyan] {welcome}\n")

    while True:
        try:
            user_input = Prompt.ask(f"[green]{USER_NAME}[/green]")

            if not user_input.strip():
                continue

            if user_input.lower() in ['exit', 'quit', 'bye']:
                console.print(f"\n[cyan]{ASSISTANT_NAME}:[/cyan] Goodbye, {USER_NAME}! Have a great day!\n")
                break

            # Check for quick commands
            if user_input.startswith('/'):
                handle_command(user_input[1:])
            else:
                # Chat with AI
                console.print(f"\n[cyan]{ASSISTANT_NAME}:[/cyan] ", end="")
                for chunk in ai.stream_chat(user_input):
                    console.print(chunk, end="")
                console.print("\n")

        except KeyboardInterrupt:
            console.print(f"\n\n[cyan]{ASSISTANT_NAME}:[/cyan] Goodbye!\n")
            break
        except Exception as e:
            error_msg = str(e)
            if "database" in error_msg.lower() or "sqlite" in error_msg.lower():
                console.print(f"[red]Database error: {e}[/red]")
                console.print("[yellow]Try: jarvis --repair database[/yellow]")
            elif "ollama" in error_msg.lower() or "connection" in error_msg.lower():
                console.print(f"[red]AI connection error: {e}[/red]")
                console.print("[yellow]Ensure Ollama is running: ollama serve[/yellow]")
            else:
                console.print(f"[red]Error: {e}[/red]")


def handle_command(cmd: str):
    """Handle slash commands"""
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == 'help':
        show_help()
    elif command == 'tasks':
        show_tasks()
    elif command == 'add':
        add_task_interactive(args)
    elif command == 'done':
        complete_task(args)
    elif command == 'log':
        log_activity(args)
    elif command == 'today':
        show_today()
    elif command == 'summary':
        show_summary()
    elif command == 'suggest':
        show_suggestions()
    elif command == 'stats':
        show_stats()
    elif command == 'weather':
        show_weather(args)
    elif command == 'search':
        cli_search(args)
    elif command == 'note':
        cli_note(args)
    elif command == 'notes':
        cli_notes()
    elif command == 'remind':
        cli_remind(args)
    elif command == 'reminders':
        cli_reminders()
    elif command == 'system':
        cli_system()
    elif command == 'briefing':
        cli_briefing()
    elif command == 'remember':
        cli_remember(args)
    elif command == 'recall':
        cli_recall(args)
    elif command == 'workflows':
        cli_workflows()
    elif command == 'music':
        cli_music(args)
    elif command == 'startup':
        cli_startup()
    elif command in ('startup-add', 'startup_add'):
        cli_startup_add(args)
    elif command in ('startup-remove', 'startup_remove'):
        cli_startup_remove(args)
    elif command in ('startup-run', 'startup_run'):
        cli_startup_run()
    else:
        # Check plugin commands
        try:
            from plugins.loader import get_registry
            registry = get_registry()
            if command in registry.commands:
                handler = registry.commands[command].get('handler')
                if handler:
                    handler(args)
                    return
        except ImportError:
            pass
        console.print(f"[yellow]Unknown command: {command}. Type /help for available commands.[/yellow]")


def show_help():
    """Show available commands"""
    help_text = """
## Available Commands

| Command | Description |
|---------|-------------|
| /tasks | Show all pending tasks |
| /add [task] | Add a new task |
| /done [id] | Mark task as complete |
| /log [activity] | Log an activity |
| /today | Show today's activities |
| /summary | Show daily summary |
| /suggest | Get behavior suggestions |
| /stats | Show productivity stats |
| /weather [city] | Show weather info |
| /search [query] | Search the web |
| /note [text] | Save a quick note |
| /notes | List recent notes |
| /remind [text] | Set a reminder |
| /reminders | List pending reminders |
| /music [play/pause/next] | Control music |
| /system | Show system info |
| /briefing | Daily briefing |
| /remember [fact] | Store a memory |
| /recall [query] | Recall a memory |
| /workflows | List automation workflows |
| /startup | List startup apps |
| /startup-add [app] | Add app to startup list |
| /startup-remove [app] | Remove app from startup list |
| /startup-run | Launch all startup apps now |
| /help | Show this help |
| exit | Exit the assistant |

You can also just type naturally to chat with me!
"""
    console.print(Markdown(help_text))


@cli.command()
def tasks():
    """Show pending tasks"""
    show_tasks()


def show_tasks():
    """Display pending tasks in a table"""
    tasks_list = db.get_pending_tasks()

    if not tasks_list:
        console.print("[green]No pending tasks! You're all caught up.[/green]")
        return

    table = Table(title="Pending Tasks", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Priority", width=8)
    table.add_column("Task", width=40)
    table.add_column("Due", width=12)
    table.add_column("Category", width=10)

    priority_colors = {'high': 'red', 'medium': 'yellow', 'low': 'green'}

    for task in tasks_list:
        priority = task['priority']
        color = priority_colors.get(priority, 'white')
        table.add_row(
            str(task['id']),
            f"[{color}]{priority}[/{color}]",
            task['title'],
            task['due_date'] or "-",
            task['category'] or "-"
        )

    console.print(table)


@cli.command()
@click.argument('title', nargs=-1, required=True)
@click.option('--priority', '-p', default='medium', type=click.Choice(['high', 'medium', 'low']))
@click.option('--due', '-d', default=None, help='Due date (YYYY-MM-DD)')
@click.option('--category', '-c', default=None, help='Task category')
def add(title, priority, due, category):
    """Add a new task"""
    task_title = ' '.join(title)
    add_task_interactive(task_title, priority, due, category)


def add_task_interactive(title: str = "", priority: str = "medium", due: str = None, category: str = None):
    """Add a task interactively"""
    if not title:
        title = Prompt.ask("Task title")

    if not priority:
        priority = Prompt.ask("Priority", choices=["high", "medium", "low"], default="medium")

    task_id = db.add_task(title, priority=priority, due_date=due, category=category)
    console.print(f"[green]Task added successfully (ID: {task_id})[/green]")


@cli.command()
@click.argument('task_id', type=int)
def done(task_id):
    """Mark a task as complete"""
    complete_task(str(task_id))


def complete_task(task_id_str: str):
    """Mark task as completed"""
    try:
        task_id = int(task_id_str)
        # Get task title before completing
        tasks = db.get_pending_tasks()
        task_title = next((t['title'] for t in tasks if t['id'] == task_id), None)

        if db.complete_task(task_id):
            if task_title:
                console.print(f"[green]Task {task_id} '{task_title}' marked as complete![/green]")
            else:
                console.print(f"[green]Task {task_id} marked as complete![/green]")
        else:
            console.print(f"[red]Task {task_id} not found or already completed[/red]")
    except ValueError:
        console.print("[red]Please provide a valid task ID[/red]")


@cli.command()
@click.argument('activity', nargs=-1, required=True)
@click.option('--duration', '-d', type=int, default=None, help='Duration in minutes')
@click.option('--category', '-c', default=None, help='Activity category')
def log(activity, duration, category):
    """Log an activity"""
    activity_text = ' '.join(activity)
    log_activity(activity_text, duration, category)


def log_activity(activity: str = "", duration: int = None, category: str = None):
    """Log an activity"""
    if not activity:
        activity = Prompt.ask("What did you work on?")

    log_id = db.log_activity(activity, category=category, duration_minutes=duration)
    console.print(f"[green]Activity logged (ID: {log_id})[/green]")


@cli.command()
def today():
    """Show today's activities"""
    show_today()


def show_today():
    """Display today's activities"""
    logs = db.get_today_logs()

    if not logs:
        console.print("[yellow]No activities logged today yet.[/yellow]")
        return

    table = Table(title=f"Today's Activities ({datetime.now().strftime('%Y-%m-%d')})",
                  show_header=True, header_style="bold blue")
    table.add_column("Time", width=8)
    table.add_column("Activity", width=40)
    table.add_column("Duration", width=10)
    table.add_column("Category", width=12)

    total_minutes = 0
    for log in logs:
        duration_str = f"{log['duration_minutes']}m" if log['duration_minutes'] else "-"
        total_minutes += log['duration_minutes'] or 0
        table.add_row(
            log['time'][:5],
            log['activity'],
            duration_str,
            log['category'] or "-"
        )

    console.print(table)
    if total_minutes > 0:
        hours = total_minutes // 60
        mins = total_minutes % 60
        console.print(f"[cyan]Total tracked time: {hours}h {mins}m[/cyan]")


@cli.command()
def summary():
    """Show daily summary"""
    show_summary()


def show_summary():
    """Display daily summary"""
    summary_text = ai.generate_daily_summary()
    console.print(Panel(summary_text, title="Daily Summary", border_style="blue"))


@cli.command()
def suggest():
    """Get behavior suggestions"""
    show_suggestions()


def show_suggestions():
    """Display behavior suggestions"""
    suggestions = ai.get_behavior_suggestions()
    console.print(Panel.fit(
        "\n".join([f"- {s}" for s in suggestions]),
        title="Suggestions",
        border_style="green"
    ))


@cli.command()
def stats():
    """Show productivity stats"""
    show_stats()


def show_stats():
    """Display productivity statistics"""
    stats_data = db.get_productivity_stats(7)

    table = Table(title="Productivity Stats (Last 7 Days)", show_header=True, header_style="bold green")
    table.add_column("Metric", width=25)
    table.add_column("Value", width=15)

    table.add_row("Tasks Completed", str(stats_data['tasks_completed']))
    table.add_row("Activities Logged", str(stats_data['activities_logged']))

    total_hours = stats_data['total_work_minutes'] / 60
    table.add_row("Total Tracked Time", f"{total_hours:.1f} hours")

    console.print(table)


def cli_search(query: str):
    if not query:
        query = Prompt.ask("Search for")
    try:
        from core.smart_features import get_web_search
        result = get_web_search().quick_answer(query)
        console.print(Panel(result, title="Search Results", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]")

def cli_note(content: str):
    if not content:
        content = Prompt.ask("Note")
    try:
        from core.smart_features import get_notes
        console.print(f"[green]{get_notes().add_note(content)}[/green]")
    except Exception as e:
        console.print(f"[red]Note error: {e}[/red]")

def cli_notes():
    try:
        from core.smart_features import get_notes
        console.print(Panel(get_notes().list_recent(), title="Notes", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_remind(args: str):
    if not args:
        args = Prompt.ask("Remind me to")
    try:
        response = ai.chat(f"remind me {args}")
        console.print(f"[green]{response}[/green]")
    except Exception as e:
        console.print(f"[red]Reminder error: {e}[/red]")

def cli_reminders():
    try:
        from core.smart_features import get_reminder_system
        pending = get_reminder_system().get_pending()
        if not pending:
            console.print("[green]No pending reminders.[/green]")
        else:
            text = "Pending reminders:\n"
            for r in pending:
                t = r['time'][:16]
                text += f"  - {t}: {r['message']}\n"
            console.print(Panel(text, title="Reminders", border_style="yellow"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_system():
    try:
        from core.smart_features import get_system_controller
        console.print(Panel(get_system_controller().get_system_info(), title="System", border_style="green"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_briefing():
    try:
        from core.smart_features import get_briefing
        console.print(Panel(get_briefing().generate(), title="Daily Briefing", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_remember(args: str):
    if not args:
        args = Prompt.ask("Remember what")
    try:
        response = ai.chat(f"remember that {args}")
        console.print(f"[green]{response}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_recall(args: str):
    if not args:
        args = Prompt.ask("Recall what")
    try:
        from core.smart_features import get_memory
        console.print(get_memory().recall(args))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_workflows():
    try:
        from core.smart_features import get_automation
        console.print(Panel(get_automation().list_workflows(), title="Workflows", border_style="green"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_music(args: str):
    try:
        from core.smart_features import get_music
        m = get_music()
        cmd = args.lower().strip()
        if cmd in ('play', 'resume'):
            console.print(m.play())
        elif cmd in ('pause', 'stop'):
            console.print(m.pause())
        elif cmd in ('next', 'skip'):
            console.print(m.next_track())
        elif cmd in ('prev', 'previous', 'back'):
            console.print(m.previous_track())
        elif cmd in ('status', 'now', ''):
            console.print(m.status())
        else:
            console.print(f"[yellow]Unknown music command: {cmd}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def cli_startup():
    try:
        from core.smart_features import get_startup_manager
        console.print(Panel(get_startup_manager().list_apps(), title="Startup Apps", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_startup_add(args: str):
    if not args:
        args = Prompt.ask("App name to add")
    try:
        from core.smart_features import get_startup_manager
        result = get_startup_manager().add_app(args)
        console.print(f"[green]{result}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_startup_remove(args: str):
    if not args:
        args = Prompt.ask("App name to remove")
    try:
        from core.smart_features import get_startup_manager
        result = get_startup_manager().remove_app(args)
        console.print(f"[green]{result}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def cli_startup_run():
    try:
        from core.smart_features import get_startup_manager
        from core.features import VoiceEngine

        startup = get_startup_manager()
        voice = VoiceEngine()

        def speak_and_print(text):
            console.print(f"  [cyan]JARVIS:[/cyan] {text}")
            voice.speak(text, block=True)

        console.print(Panel("Launching startup apps...", title="Startup", border_style="green"))
        result = startup.run_startup(speak_func=speak_and_print)
        console.print(Panel(result, title="Startup Complete", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")



    """Show weather information"""
    try:
        from core.weather import get_weather
        loc = location.strip() if location else "auto"
        weather = get_weather(loc)
        console.print(Panel(weather, title="Weather", border_style="cyan"))
    except ImportError:
        console.print("[red]Weather service not available. Install: pip install requests[/red]")
    except Exception as e:
        console.print(f"[red]Weather error: {e}[/red]")


@cli.command()
def welcome():
    """Show welcome message"""
    welcome_msg = ai.generate_welcome_message()
    console.print(Panel(welcome_msg, title=f"Welcome, {USER_NAME}!", border_style="cyan"))


if __name__ == '__main__':
    cli()
