#!/usr/bin/env python3
"""
JARVIS GUI - Iron Man Style Futuristic Interface
Enhanced with System Monitor, Voice, Pomodoro, Health Reminders
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QSystemTrayIcon, QMenu,
    QDialog, QFormLayout, QComboBox, QMessageBox, QFrame,
    QGraphicsDropShadowEffect, QSpinBox, QDateEdit, QProgressBar,
    QSlider, QGridLayout, QScrollArea, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QDate, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize
from PyQt6.QtGui import (
    QIcon, QFont, QAction, QTextCursor, QColor, QPainter,
    QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath,
    QFontDatabase, QShortcut, QKeySequence
)

from datetime import datetime
from config.settings import ASSISTANT_NAME, USER_NAME
from core.database import get_db
from core.ai_engine import get_ai
from core.features import (
    SystemMonitor, VoiceEngine, PomodoroTimer, HealthReminder,
    DailyMotivation, QuickCommands, ScreenTimeTracker, system_monitor,
    voice_engine, daily_motivation, screen_time
)

# Voice Assistant for conversation
try:
    from core.voice_assistant import VoiceAssistant
    VOICE_ASSISTANT_AVAILABLE = True
except ImportError:
    VOICE_ASSISTANT_AVAILABLE = False


# Iron Man Color Scheme
COLORS = {
    'bg_dark': '#0a0a0f',
    'bg_panel': '#0d1117',
    'arc_blue': '#00d4ff',
    'arc_blue_dim': '#0088aa',
    'arc_glow': '#00f5ff',
    'gold': '#f0a500',
    'gold_dim': '#b87800',
    'red': '#ff3333',
    'red_dim': '#aa2222',
    'text': '#e0e0e0',
    'text_dim': '#808080',
    'success': '#00ff88',
    'warning': '#ffaa00',
    'border': '#1a3a4a',
    'purple': '#aa00ff',
}


class CircularProgress(QWidget):
    """Circular progress indicator"""

    def __init__(self, size=60, thickness=6, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.value = 0
        self.max_value = 100
        self.thickness = thickness
        self.color = QColor(COLORS['arc_blue'])
        self.bg_color = QColor(COLORS['border'])
        self.text = ""
        self.show_text = True

    def setValue(self, value):
        self.value = min(value, self.max_value)
        self.update()

    def setColor(self, color):
        self.color = QColor(color)
        self.update()

    def setText(self, text):
        self.text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(self.thickness, self.thickness,
                                    -self.thickness, -self.thickness)

        # Background arc
        pen = QPen(self.bg_color, self.thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress arc
        if self.value > 0:
            pen.setColor(self.color)
            painter.setPen(pen)
            span = int((self.value / self.max_value) * 360 * 16)
            painter.drawArc(rect, 90 * 16, -span)

        # Text
        if self.show_text and self.text:
            painter.setPen(QColor(COLORS['text']))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class WaveformWidget(QWidget):
    """Audio waveform visualization"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.bars = 20
        self.values = [0] * self.bars
        self.active = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)

    def start(self):
        self.active = True
        self.timer.start(50)

    def stop(self):
        self.active = False
        self.timer.stop()
        self.values = [0] * self.bars
        self.update()

    def animate(self):
        import random
        if self.active:
            self.values = [random.randint(5, 35) for _ in range(self.bars)]
        else:
            self.values = [max(0, v - 2) for v in self.values]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_width = self.width() // self.bars - 2
        center_y = self.height() // 2

        for i, value in enumerate(self.values):
            x = i * (bar_width + 2) + 1
            gradient = QLinearGradient(x, center_y - value, x, center_y + value)
            gradient.setColorAt(0, QColor(COLORS['arc_glow']))
            gradient.setColorAt(0.5, QColor(COLORS['arc_blue']))
            gradient.setColorAt(1, QColor(COLORS['arc_glow']))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, center_y - value//2, bar_width, value, 2, 2)


class ArcReactorWidget(QWidget):
    """Animated Arc Reactor style widget"""

    def __init__(self, size=100, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.pulse = 0
        self.pulse_dir = 1
        self.power_level = 100

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def setPowerLevel(self, level):
        self.power_level = max(0, min(100, level))

    def animate(self):
        self.angle = (self.angle + 2) % 360
        self.pulse += self.pulse_dir * 2
        if self.pulse >= 30:
            self.pulse_dir = -1
        elif self.pulse <= 0:
            self.pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.width() // 2
        intensity = self.power_level / 100

        # Outer glow
        gradient = QRadialGradient(center, center, center)
        gradient.setColorAt(0, QColor(0, 212, 255, int((50 + self.pulse) * intensity)))
        gradient.setColorAt(0.7, QColor(0, 212, 255, int(20 * intensity)))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

        # Outer ring
        pen = QPen(QColor(0, 212, 255, int(200 * intensity)))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(10, 10, self.width()-20, self.height()-20)

        # Power level arc
        if self.power_level < 100:
            pen.setColor(QColor(COLORS['gold']))
            pen.setWidth(4)
            painter.setPen(pen)
            span = int((self.power_level / 100) * 360 * 16)
            painter.drawArc(10, 10, self.width()-20, self.height()-20, 90 * 16, -span)

        # Inner rings
        pen.setWidth(2)
        pen.setColor(QColor(0, 180, 220, int(150 * intensity)))
        painter.setPen(pen)
        painter.drawEllipse(20, 20, self.width()-40, self.height()-40)

        # Rotating segments
        painter.translate(center, center)
        painter.rotate(self.angle)

        pen.setColor(QColor(0, 255, 255, int(200 * intensity)))
        pen.setWidth(4)
        painter.setPen(pen)

        for i in range(6):
            painter.rotate(60)
            painter.drawLine(15, 0, 25, 0)

        # Center core
        painter.rotate(-self.angle)
        gradient = QRadialGradient(0, 0, 15)
        gradient.setColorAt(0, QColor(255, 255, 255, int(255 * intensity)))
        gradient.setColorAt(0.3, QColor(0, 245, 255, int(255 * intensity)))
        gradient.setColorAt(1, QColor(0, 150, 200, int(100 * intensity)))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(-12, -12, 24, 24)


class SystemMonitorWidget(QWidget):
    """System monitoring panel"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)  # Update every 2 seconds

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("◈ SYSTEM STATUS")
        title.setStyleSheet(f"color: {COLORS['arc_blue']}; font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        # CPU
        self.cpu_bar = self._create_stat_bar("CPU")
        layout.addWidget(self.cpu_bar['widget'])

        # Memory
        self.mem_bar = self._create_stat_bar("MEM")
        layout.addWidget(self.mem_bar['widget'])

        # Disk
        self.disk_bar = self._create_stat_bar("DISK")
        layout.addWidget(self.disk_bar['widget'])

        # Battery
        self.battery_label = QLabel("⚡ 100%")
        self.battery_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")
        layout.addWidget(self.battery_label)

        self.update_stats()

    def _create_stat_bar(self, name) -> dict:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(name)
        label.setFixedWidth(35)
        label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['arc_blue']}, stop:1 {COLORS['arc_glow']});
                border-radius: 3px;
            }}
        """)

        value_label = QLabel("0%")
        value_label.setFixedWidth(35)
        value_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")

        layout.addWidget(label)
        layout.addWidget(bar)
        layout.addWidget(value_label)

        return {'widget': widget, 'bar': bar, 'value': value_label}

    def update_stats(self):
        stats = system_monitor.get_all_stats()

        # CPU
        cpu = int(stats['cpu'])
        self.cpu_bar['bar'].setValue(cpu)
        self.cpu_bar['value'].setText(f"{cpu}%")
        self._update_bar_color(self.cpu_bar['bar'], cpu)

        # Memory
        mem = int(stats['memory'])
        self.mem_bar['bar'].setValue(mem)
        self.mem_bar['value'].setText(f"{mem}%")
        self._update_bar_color(self.mem_bar['bar'], mem)

        # Disk
        disk = int(stats['disk'])
        self.disk_bar['bar'].setValue(disk)
        self.disk_bar['value'].setText(f"{disk}%")
        self._update_bar_color(self.disk_bar['bar'], disk)

        # Battery
        battery = stats['battery']
        bat_pct = battery['percent']
        bat_icon = "🔌" if battery['plugged'] else "🔋"
        bat_color = COLORS['success'] if bat_pct > 20 else COLORS['red']
        self.battery_label.setText(f"{bat_icon} {bat_pct}%")
        self.battery_label.setStyleSheet(f"color: {bat_color}; font-size: 11px;")

    def _update_bar_color(self, bar, value):
        if value > 80:
            color = COLORS['red']
        elif value > 60:
            color = COLORS['warning']
        else:
            color = COLORS['arc_blue']

        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 3px;
            }}
        """)


class PomodoroWidget(QWidget):
    """Pomodoro timer widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = PomodoroTimer(
            on_tick=self.on_tick,
            on_complete=self.on_complete
        )
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("◈ FOCUS TIMER")
        title.setStyleSheet(f"color: {COLORS['arc_blue']}; font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        # Time display
        self.time_label = QLabel("25:00")
        self.time_label.setStyleSheet(f"""
            color: {COLORS['arc_glow']};
            font-size: 28px;
            font-weight: bold;
            font-family: 'Orbitron', monospace;
        """)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        # Status
        self.status_label = QLabel("READY")
        self.status_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶")
        self.start_btn.setFixedSize(35, 35)
        self.start_btn.clicked.connect(self.toggle_timer)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']};
                color: black;
                border-radius: 17px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: #00cc6a; }}
        """)
        btn_layout.addWidget(self.start_btn)

        self.reset_btn = QPushButton("↺")
        self.reset_btn.setFixedSize(35, 35)
        self.reset_btn.clicked.connect(self.reset_timer)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['arc_blue_dim']};
                color: white;
                border-radius: 17px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {COLORS['arc_blue']}; }}
        """)
        btn_layout.addWidget(self.reset_btn)

        layout.addLayout(btn_layout)

        # Session count
        self.session_label = QLabel("Sessions: 0")
        self.session_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.session_label)

    def toggle_timer(self):
        if self.timer.is_running:
            if self.timer.is_paused:
                self.timer.resume()
                self.start_btn.setText("⏸")
            else:
                self.timer.pause()
                self.start_btn.setText("▶")
        else:
            self.timer.start()
            self.start_btn.setText("⏸")
            self.start_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['warning']};
                    color: black;
                    border-radius: 17px;
                    font-size: 14px;
                }}
            """)

    def reset_timer(self):
        self.timer.reset()
        self.time_label.setText("25:00")
        self.status_label.setText("READY")
        self.start_btn.setText("▶")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']};
                color: black;
                border-radius: 17px;
                font-size: 14px;
            }}
        """)

    def on_tick(self, remaining, is_break):
        self.time_label.setText(self.timer.get_time_string())
        status = "BREAK" if is_break else "FOCUS"
        self.status_label.setText(status)

        # Update color
        if is_break:
            self.time_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 28px; font-weight: bold;")
        else:
            self.time_label.setStyleSheet(f"color: {COLORS['arc_glow']}; font-size: 28px; font-weight: bold;")

    def on_complete(self, is_break, session):
        self.session_label.setText(f"Sessions: {session}")
        self.start_btn.setText("▶")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']};
                color: black;
                border-radius: 17px;
                font-size: 14px;
            }}
        """)

        # Notification
        msg = "Break time! Take a rest." if is_break else "Focus session complete!"
        voice_engine.speak(msg)


class QuoteWidget(QWidget):
    """Daily motivational quote widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_quote()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        header = QHBoxLayout()
        title = QLabel("◈ DAILY INSPIRATION")
        title.setStyleSheet(f"color: {COLORS['gold']}; font-weight: bold; font-size: 11px;")
        header.addWidget(title)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(25, 25)
        refresh_btn.clicked.connect(self.refresh_quote)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['gold']};
                border: 1px solid {COLORS['gold_dim']};
                border-radius: 12px;
            }}
            QPushButton:hover {{ background: {COLORS['gold_dim']}; color: white; }}
        """)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        self.quote_label = QLabel()
        self.quote_label.setWordWrap(True)
        self.quote_label.setStyleSheet(f"""
            color: {COLORS['text']};
            font-style: italic;
            font-size: 12px;
            padding: 5px;
        """)
        layout.addWidget(self.quote_label)

        self.author_label = QLabel()
        self.author_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.author_label)

    def refresh_quote(self):
        quote, author = daily_motivation.get_quote()
        self.quote_label.setText(f'"{quote}"')
        self.author_label.setText(f"— {author}")


class HUDButton(QPushButton):
    """Futuristic HUD button"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_panel']}, stop:1 #151520);
                color: {COLORS['arc_blue']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 5px;
                padding: 10px 20px;
                font-family: 'Orbitron', monospace;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a2530, stop:1 #0d1820);
                border: 1px solid {COLORS['arc_glow']};
                color: {COLORS['arc_glow']};
            }}
            QPushButton:pressed {{
                background: {COLORS['arc_blue_dim']};
                color: white;
            }}
        """)

        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(15)
        glow.setColor(QColor(0, 212, 255, 80))
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)


class AIWorker(QThread):
    """Worker thread for AI responses"""
    response_chunk = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, message: str):
        super().__init__()
        self.message = message
        self.ai = get_ai()

    def run(self):
        try:
            for chunk in self.ai.stream_chat(self.message):
                self.response_chunk.emit(chunk)
        except Exception as e:
            self.response_chunk.emit(f"\n[Error: {e}]")
        self.finished.emit()


class VoiceListenerThread(QThread):
    """Thread for voice listening"""
    text_recognized = pyqtSignal(str)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.voice_assistant = None
        if VOICE_ASSISTANT_AVAILABLE:
            self.voice_assistant = VoiceAssistant()

    def run(self):
        if not self.voice_assistant:
            self.error.emit("Voice assistant not available")
            return

        self.listening_started.emit()
        try:
            text = self.voice_assistant.listen_once(timeout=10.0, phrase_time_limit=15.0)
            if text:
                self.text_recognized.emit(text)
            else:
                self.error.emit("Didn't catch that")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.listening_stopped.emit()


class CommandPalette(QDialog):
    """Quick command palette (Ctrl+K)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Commands")
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def setup_ui(self):
        container = QWidget()
        container.setStyleSheet(f"""
            background-color: {COLORS['bg_dark']};
            border: 2px solid {COLORS['arc_blue']};
            border-radius: 15px;
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 15, 15, 15)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command...")
        self.search_input.textChanged.connect(self.filter_commands)
        self.search_input.returnPressed.connect(self.execute_selected)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
            }}
        """)
        layout.addWidget(self.search_input)

        # Commands list
        self.commands_list = QTableWidget()
        self.commands_list.setColumnCount(2)
        self.commands_list.setHorizontalHeaderLabels(["Command", "Description"])
        self.commands_list.horizontalHeader().setStretchLastSection(True)
        self.commands_list.setColumnWidth(0, 120)
        self.commands_list.verticalHeader().setVisible(False)
        self.commands_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.commands_list.itemDoubleClicked.connect(self.execute_selected)
        self.commands_list.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_panel']};
                color: {COLORS['text']};
                border: none;
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background: {COLORS['arc_blue_dim']};
            }}
            QHeaderView::section {{
                background: {COLORS['bg_dark']};
                color: {COLORS['arc_blue']};
                padding: 8px;
                border: none;
            }}
        """)
        layout.addWidget(self.commands_list)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)

        self.load_commands()

    def load_commands(self):
        commands = QuickCommands.get_all()
        self.commands_list.setRowCount(len(commands))

        for i, (name, desc) in enumerate(commands):
            self.commands_list.setItem(i, 0, QTableWidgetItem(name.upper()))
            self.commands_list.setItem(i, 1, QTableWidgetItem(desc))

    def filter_commands(self, text):
        results = QuickCommands.search(text) if text else QuickCommands.get_all()
        self.commands_list.setRowCount(len(results))

        for i, (name, desc) in enumerate(results):
            self.commands_list.setItem(i, 0, QTableWidgetItem(name.upper()))
            self.commands_list.setItem(i, 1, QTableWidgetItem(desc))

    def execute_selected(self):
        row = self.commands_list.currentRow()
        if row >= 0:
            cmd = self.commands_list.item(row, 0).text().lower()
            QuickCommands.execute(cmd)
            self.accept()


class AddTaskDialog(QDialog):
    """Futuristic dialog for adding tasks"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("// NEW TASK")
        self.setMinimumWidth(450)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def setup_ui(self):
        container = QWidget()
        container.setStyleSheet(f"""
            background-color: {COLORS['bg_dark']};
            border: 2px solid {COLORS['arc_blue_dim']};
            border-radius: 15px;
        """)

        layout = QFormLayout(container)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("◈ NEW TASK")
        title.setStyleSheet(f"color: {COLORS['arc_blue']}; font-size: 16px; font-weight: bold;")
        layout.addRow(title)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("ENTER TASK DESIGNATION...")
        self.title_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 5px;
                padding: 10px;
            }}
        """)
        layout.addRow(QLabel("TITLE:"), self.title_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["HIGH", "MEDIUM", "LOW"])
        self.priority_combo.setCurrentText("MEDIUM")
        self.priority_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 5px;
                padding: 8px;
            }}
        """)
        layout.addRow(QLabel("PRIORITY:"), self.priority_combo)

        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("CATEGORY...")
        self.category_edit.setStyleSheet(self.title_edit.styleSheet())
        layout.addRow(QLabel("CATEGORY:"), self.category_edit)

        btn_layout = QHBoxLayout()
        self.add_btn = HUDButton("CONFIRM")
        self.add_btn.clicked.connect(self.accept)
        self.cancel_btn = HUDButton("ABORT")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)

        # Style labels
        for i in range(layout.rowCount()):
            item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setStyleSheet(f"color: {COLORS['arc_blue']}; font-weight: bold;")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)

    def get_task_data(self) -> dict:
        return {
            'title': self.title_edit.text(),
            'priority': self.priority_combo.currentText().lower(),
            'category': self.category_edit.text() or None,
        }


class JarvisMainWindow(QMainWindow):
    """Iron Man style JARVIS main window - Enhanced"""

    def __init__(self):
        super().__init__()
        self.db = get_db()
        self.ai = get_ai()
        self.worker = None
        self.voice_enabled = True

        self.setWindowTitle(f"J.A.R.V.I.S. - {USER_NAME.upper()}")
        self.setMinimumSize(1400, 900)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setup_ui()
        self.setup_shortcuts()
        self.setup_tray()
        self.setup_timers()
        self.show_welcome()

        # Health reminders
        self.health_reminder = HealthReminder(callback=self.show_health_reminder)
        self.health_reminder.start()

        self.drag_pos = None

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Command palette
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self.show_command_palette)

        # Voice toggle
        voice_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        voice_shortcut.activated.connect(self.toggle_voice)

    def setup_ui(self):
        """Setup the enhanced UI"""
        container = QWidget()
        container.setObjectName("mainContainer")
        container.setStyleSheet(f"""
            #mainContainer {{
                background-color: {COLORS['bg_dark']};
                border: 2px solid {COLORS['arc_blue_dim']};
                border-radius: 15px;
            }}
        """)
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)

        # Content area
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(15)

        # Left panel
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel)

        # Center panel (main content)
        center_panel = self.create_center_panel()
        content_layout.addWidget(center_panel, stretch=1)

        # Right panel (tools)
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel)

        main_layout.addWidget(content)

    def create_title_bar(self) -> QWidget:
        """Create custom title bar"""
        title_bar = QWidget()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['bg_dark']}, stop:0.5 #0a1520, stop:1 {COLORS['bg_dark']});
            border-bottom: 1px solid {COLORS['arc_blue_dim']};
            border-top-left-radius: 15px;
            border-top-right-radius: 15px;
        """)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(20, 0, 20, 0)

        # Logo
        title = QLabel("◈ J.A.R.V.I.S.")
        title.setStyleSheet(f"""
            color: {COLORS['arc_blue']};
            font-family: 'Orbitron', monospace;
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 3px;
        """)
        layout.addWidget(title)

        # Waveform (for voice visualization)
        self.waveform = WaveformWidget()
        self.waveform.setFixedWidth(150)
        layout.addWidget(self.waveform)

        # Status
        self.status_label = QLabel(f"● ONLINE | {datetime.now().strftime('%H:%M:%S')}")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-family: monospace; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Screen time
        self.screen_time_label = QLabel("⏱ 0h 0m")
        self.screen_time_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        layout.addWidget(self.screen_time_label)

        layout.addStretch()

        # Voice toggle
        self.voice_btn = QPushButton("🔊")
        self.voice_btn.setFixedSize(30, 30)
        self.voice_btn.clicked.connect(self.toggle_voice)
        self.voice_btn.setToolTip("Toggle Voice (Ctrl+M)")
        self.voice_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['arc_blue']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 15px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {COLORS['arc_blue_dim']}; }}
        """)
        layout.addWidget(self.voice_btn)

        # Command palette button
        cmd_btn = QPushButton("⌘")
        cmd_btn.setFixedSize(30, 30)
        cmd_btn.clicked.connect(self.show_command_palette)
        cmd_btn.setToolTip("Quick Commands (Ctrl+K)")
        cmd_btn.setStyleSheet(self.voice_btn.styleSheet())
        layout.addWidget(cmd_btn)

        # Window controls
        minimize_btn = QPushButton("─")
        minimize_btn.setFixedSize(30, 30)
        minimize_btn.clicked.connect(self.showMinimized)
        minimize_btn.setStyleSheet(self.voice_btn.styleSheet())
        layout.addWidget(minimize_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['red']};
                border: 1px solid {COLORS['red']};
                border-radius: 15px;
            }}
            QPushButton:hover {{ background: {COLORS['red']}; color: white; }}
        """)
        layout.addWidget(close_btn)

        return title_bar

    def create_left_panel(self) -> QWidget:
        """Create left panel with Arc Reactor and system status"""
        panel = QWidget()
        panel.setFixedWidth(220)

        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(15)

        # Arc Reactor
        self.reactor = ArcReactorWidget(160)
        layout.addWidget(self.reactor, alignment=Qt.AlignmentFlag.AlignCenter)

        # System Monitor
        self.sys_monitor = SystemMonitorWidget()
        self.sys_monitor.setStyleSheet(f"""
            background: {COLORS['bg_panel']};
            border: 1px solid {COLORS['arc_blue_dim']};
            border-radius: 10px;
        """)
        layout.addWidget(self.sys_monitor)

        # Pomodoro Timer
        self.pomodoro = PomodoroWidget()
        self.pomodoro.setStyleSheet(f"""
            background: {COLORS['bg_panel']};
            border: 1px solid {COLORS['arc_blue_dim']};
            border-radius: 10px;
        """)
        layout.addWidget(self.pomodoro)

        layout.addStretch()

        return panel

    def create_center_panel(self) -> QWidget:
        """Create center panel with tabs"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
            }}
            QTabBar::tab {{
                background: {COLORS['bg_dark']};
                color: {COLORS['text_dim']};
                padding: 10px 20px;
                margin-right: 3px;
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-family: monospace;
                font-weight: bold;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['bg_panel']};
                color: {COLORS['arc_blue']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-bottom: none;
            }}
        """)

        self.tabs.addTab(self.create_chat_tab(), "◈ NEURAL LINK")
        self.tabs.addTab(self.create_tasks_tab(), "◈ MISSIONS")
        self.tabs.addTab(self.create_activity_tab(), "◈ LOG")
        self.tabs.addTab(self.create_analysis_tab(), "◈ ANALYSIS")

        layout.addWidget(self.tabs)

        return panel

    def create_right_panel(self) -> QWidget:
        """Create right panel with tools"""
        panel = QWidget()
        panel.setFixedWidth(250)

        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Quick Actions
        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
            }}
        """)
        actions_layout = QVBoxLayout(actions_frame)

        title = QLabel("◈ QUICK ACTIONS")
        title.setStyleSheet(f"color: {COLORS['arc_blue']}; font-weight: bold; font-size: 11px;")
        actions_layout.addWidget(title)

        for text, callback in [
            ("+ NEW TASK", self.show_add_task_dialog),
            ("+ LOG ACTIVITY", self.show_log_activity_dialog),
            ("📊 SUMMARY", self.generate_summary),
            ("🔊 SPEAK", self.speak_last_message),
        ]:
            btn = HUDButton(text)
            btn.clicked.connect(callback)
            actions_layout.addWidget(btn)

        layout.addWidget(actions_frame)

        # Daily Quote
        self.quote_widget = QuoteWidget()
        self.quote_widget.setStyleSheet(f"""
            background: {COLORS['bg_panel']};
            border: 1px solid {COLORS['gold_dim']};
            border-radius: 10px;
        """)
        layout.addWidget(self.quote_widget)

        # Task Overview
        task_frame = QFrame()
        task_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        task_layout = QVBoxLayout(task_frame)

        task_title = QLabel("◈ MISSION STATUS")
        task_title.setStyleSheet(f"color: {COLORS['arc_blue']}; font-weight: bold; font-size: 11px;")
        task_layout.addWidget(task_title)

        self.task_overview = QLabel("Loading...")
        self.task_overview.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        self.task_overview.setWordWrap(True)
        task_layout.addWidget(self.task_overview)

        layout.addWidget(task_frame)

        layout.addStretch()

        return panel

    def create_chat_tab(self) -> QWidget:
        """Create the chat interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
                padding: 15px;
                font-family: 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
            }}
        """)
        layout.addWidget(self.chat_display)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)

        # Voice input button (clickable microphone)
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(40, 40)
        self.mic_btn.setToolTip("Click to speak (or hold Spacebar)")
        self.mic_btn.clicked.connect(self.start_voice_listening)
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_panel']};
                color: {COLORS['arc_blue']};
                border: 2px solid {COLORS['arc_blue_dim']};
                border-radius: 20px;
                font-size: 20px;
            }}
            QPushButton:hover {{
                background: {COLORS['arc_blue_dim']};
                color: white;
            }}
            QPushButton:pressed {{
                background: {COLORS['arc_blue']};
            }}
        """)
        input_layout.addWidget(self.mic_btn)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("ENTER COMMAND OR QUERY... (or click 🎤 to speak)")
        self.chat_input.returnPressed.connect(self.send_message)
        self.chat_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {COLORS['text']};
                border: none;
                padding: 10px;
                font-family: monospace;
                font-size: 14px;
            }}
        """)
        input_layout.addWidget(self.chat_input)

        send_btn = HUDButton("TRANSMIT")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)

        # Voice listener thread
        self.voice_listener = None
        self.is_listening = False

        layout.addWidget(input_frame)

        return widget

    def create_tasks_tab(self) -> QWidget:
        """Create tasks interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(5)
        self.tasks_table.setHorizontalHeaderLabels(["ID", "PRIORITY", "MISSION", "STATUS", "ACTIONS"])
        self.tasks_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
                gridline-color: {COLORS['border']};
            }}
            QTableWidget::item {{ padding: 10px; }}
            QTableWidget::item:selected {{ background-color: {COLORS['arc_blue_dim']}; }}
            QHeaderView::section {{
                background-color: {COLORS['bg_panel']};
                color: {COLORS['arc_blue']};
                padding: 10px;
                border: none;
                font-weight: bold;
            }}
        """)
        self.tasks_table.setColumnWidth(0, 50)
        self.tasks_table.setColumnWidth(1, 100)
        self.tasks_table.setColumnWidth(2, 400)
        self.tasks_table.setColumnWidth(3, 100)
        self.tasks_table.setColumnWidth(4, 150)
        self.tasks_table.verticalHeader().setVisible(False)

        layout.addWidget(self.tasks_table)
        self.refresh_tasks()

        return widget

    def create_activity_tab(self) -> QWidget:
        """Create activity log interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QHBoxLayout()
        header.addWidget(QLabel("◈ ACTIVITY LOG"))
        self.total_time_label = QLabel("TOTAL: 0H 0M")
        self.total_time_label.setStyleSheet(f"color: {COLORS['arc_blue']};")
        header.addStretch()
        header.addWidget(self.total_time_label)
        layout.addLayout(header)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels(["TIME", "ACTIVITY", "DURATION", "CATEGORY"])
        self.activity_table.setStyleSheet(self.tasks_table.styleSheet() if hasattr(self, 'tasks_table') else "")
        self.activity_table.verticalHeader().setVisible(False)

        layout.addWidget(self.activity_table)
        self.refresh_activities()

        return widget

    def create_analysis_tab(self) -> QWidget:
        """Create analysis/summary view"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        self.summary_display = QTextEdit()
        self.summary_display.setReadOnly(True)
        self.summary_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
                padding: 15px;
                font-family: monospace;
            }}
        """)
        layout.addWidget(self.summary_display)

        # Stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['arc_blue_dim']};
                border-radius: 10px;
            }}
        """)
        stats_layout = QHBoxLayout(stats_frame)

        self.stats_widgets = {}
        for name in ["COMPLETED", "PENDING", "PRODUCTIVITY"]:
            w = QWidget()
            l = QVBoxLayout(w)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            value = QLabel("0")
            value.setStyleSheet(f"color: {COLORS['arc_glow']}; font-size: 32px; font-weight: bold;")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)

            label = QLabel(name)
            label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            l.addWidget(value)
            l.addWidget(label)
            stats_layout.addWidget(w)
            self.stats_widgets[name] = value

        layout.addWidget(stats_frame)
        self.refresh_stats()

        return widget

    def setup_tray(self):
        """Setup system tray"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("J.A.R.V.I.S.")

        tray_menu = QMenu()
        tray_menu.addAction("Show", self.show)
        tray_menu.addAction("Summary", self.generate_summary)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", QApplication.quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda r: self.show() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray_icon.show()

    def setup_timers(self):
        """Setup update timers"""
        # Clock update
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_status)
        self.clock_timer.start(1000)

        # Task count update
        self.task_timer = QTimer()
        self.task_timer.timeout.connect(self.update_task_overview)
        self.task_timer.start(30000)

    def update_status(self):
        """Update status bar"""
        self.status_label.setText(f"● ONLINE | {datetime.now().strftime('%H:%M:%S')}")
        self.screen_time_label.setText(f"⏱ {screen_time.get_session_time_string()}")

        # Update reactor based on system load
        cpu = system_monitor.get_cpu_percent()
        self.reactor.setPowerLevel(100 - int(cpu * 0.5))

    def update_task_overview(self):
        """Update task overview"""
        tasks = self.db.get_pending_tasks()
        high = len([t for t in tasks if t['priority'] == 'high'])
        medium = len([t for t in tasks if t['priority'] == 'medium'])
        low = len([t for t in tasks if t['priority'] == 'low'])

        self.task_overview.setText(
            f"🔴 High: {high}\n"
            f"🟡 Medium: {medium}\n"
            f"🟢 Low: {low}\n"
            f"━━━━━━━━━━\n"
            f"Total: {len(tasks)}"
        )

    def show_welcome(self):
        """Show welcome message"""
        welcome = self.ai.generate_welcome_message()
        self.append_message("J.A.R.V.I.S.", welcome, is_assistant=True)
        self.update_task_overview()

        # Speak welcome
        if self.voice_enabled:
            voice_engine.speak(f"Good day, {USER_NAME}. All systems are online.")

    def append_message(self, sender: str, message: str, is_assistant: bool = False):
        """Add message to chat"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        color = COLORS['arc_blue'] if is_assistant else COLORS['gold']
        prefix = "◈" if is_assistant else "►"

        html = f'''
        <p style="margin: 10px 0;">
            <span style="color: {color}; font-weight: bold;">{prefix} {sender}:</span><br/>
            <span style="color: {COLORS['text']};">{message}</span>
        </p>
        '''
        cursor.insertHtml(html)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

        self.last_message = message

    def send_message(self):
        """Send message to AI"""
        message = self.chat_input.text().strip()
        if not message:
            return

        self.chat_input.clear()
        self.append_message(USER_NAME.upper(), message, is_assistant=False)

        self.worker = AIWorker(message)
        self.worker.response_chunk.connect(self.handle_response_chunk)
        self.worker.finished.connect(self.handle_response_finished)

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<p style="margin: 10px 0;"><span style="color: {COLORS["arc_blue"]}; font-weight: bold;">◈ J.A.R.V.I.S.:</span><br/><span style="color: {COLORS["text"]};">')

        self.chat_input.setEnabled(False)
        self.waveform.start()
        self.worker.start()

    def handle_response_chunk(self, chunk: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def handle_response_finished(self):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml('</span></p>')
        self.chat_input.setEnabled(True)
        self.chat_input.setFocus()
        self.waveform.stop()

    def toggle_voice(self):
        """Toggle voice output"""
        self.voice_enabled = voice_engine.toggle()
        icon = "🔊" if self.voice_enabled else "🔇"
        self.voice_btn.setText(icon)

    def start_voice_listening(self):
        """Start listening for voice input"""
        if self.is_listening:
            return

        if not VOICE_ASSISTANT_AVAILABLE:
            self.append_message("SYSTEM", "Voice input not available. Install: pip install SpeechRecognition")
            return

        self.is_listening = True
        self.mic_btn.setText("🔴")
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['red']};
                color: white;
                border: 2px solid {COLORS['red']};
                border-radius: 20px;
                font-size: 20px;
            }}
        """)
        self.chat_input.setPlaceholderText("🎤 LISTENING... Speak now!")

        # Start voice listener thread
        self.voice_listener = VoiceListenerThread()
        self.voice_listener.text_recognized.connect(self.on_voice_recognized)
        self.voice_listener.listening_stopped.connect(self.on_voice_stopped)
        self.voice_listener.error.connect(self.on_voice_error)
        self.voice_listener.start()

        # Start waveform animation
        self.waveform.start()

    def on_voice_recognized(self, text: str):
        """Handle recognized speech"""
        self.chat_input.setText(text)
        self.append_message("VOICE", text)
        # Auto-send the message
        QTimer.singleShot(500, self.send_message)

    def on_voice_stopped(self):
        """Reset voice UI after listening stops"""
        self.is_listening = False
        self.mic_btn.setText("🎤")
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_panel']};
                color: {COLORS['arc_blue']};
                border: 2px solid {COLORS['arc_blue_dim']};
                border-radius: 20px;
                font-size: 20px;
            }}
            QPushButton:hover {{
                background: {COLORS['arc_blue_dim']};
                color: white;
            }}
        """)
        self.chat_input.setPlaceholderText("ENTER COMMAND OR QUERY... (or click 🎤 to speak)")
        self.waveform.stop()

    def on_voice_error(self, error: str):
        """Handle voice recognition error"""
        # Don't spam chat with "Didn't catch that" - just show briefly in placeholder
        if "catch" in error.lower():
            self.chat_input.setPlaceholderText("Didn't catch that. Click 🎤 to try again.")
            QTimer.singleShot(3000, lambda: self.chat_input.setPlaceholderText(
                "ENTER COMMAND OR QUERY... (or click 🎤 to speak)"))
        else:
            # Show actual errors in chat
            self.append_message("SYSTEM", f"Voice: {error}")

    def speak_last_message(self):
        """Speak the last AI message"""
        if hasattr(self, 'last_message'):
            self.waveform.start()
            voice_engine.speak(self.last_message)
            QTimer.singleShot(3000, self.waveform.stop)

    def show_command_palette(self):
        """Show quick command palette"""
        dialog = CommandPalette(self)
        dialog.exec()

    def show_add_task_dialog(self):
        """Show add task dialog"""
        dialog = AddTaskDialog(self)
        if dialog.exec():
            data = dialog.get_task_data()
            if data['title']:
                self.db.add_task(**data)
                self.refresh_tasks()
                self.update_task_overview()

    def show_log_activity_dialog(self):
        """Quick log activity"""
        text, ok = QInputDialog.getText(self, 'LOG ACTIVITY', 'Activity:')
        if ok and text:
            self.db.log_activity(text)
            self.refresh_activities()

    def show_health_reminder(self, reminder_type: str, message: str):
        """Show health reminder notification"""
        self.tray_icon.showMessage(
            f"Health Reminder: {reminder_type.title()}",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
        if self.voice_enabled:
            voice_engine.speak(message)

    def refresh_tasks(self):
        """Refresh tasks table"""
        tasks = self.db.get_pending_tasks()
        self.tasks_table.setRowCount(len(tasks))

        colors = {'high': COLORS['red'], 'medium': COLORS['gold'], 'low': COLORS['success']}

        for row, task in enumerate(tasks):
            self.tasks_table.setItem(row, 0, QTableWidgetItem(str(task['id'])))

            p_item = QTableWidgetItem(task['priority'].upper())
            p_item.setForeground(QColor(colors.get(task['priority'], COLORS['text'])))
            self.tasks_table.setItem(row, 1, p_item)

            self.tasks_table.setItem(row, 2, QTableWidgetItem(task['title']))
            self.tasks_table.setItem(row, 3, QTableWidgetItem("PENDING"))

            # Actions
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(5, 2, 5, 2)

            done_btn = QPushButton("✓")
            done_btn.setFixedSize(30, 30)
            done_btn.setStyleSheet(f"background: {COLORS['success']}; border-radius: 15px;")
            done_btn.clicked.connect(lambda c, tid=task['id']: self.complete_task(tid))
            actions_layout.addWidget(done_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(30, 30)
            del_btn.setStyleSheet(f"background: {COLORS['red']}; border-radius: 15px; color: white;")
            del_btn.clicked.connect(lambda c, tid=task['id']: self.delete_task(tid))
            actions_layout.addWidget(del_btn)

            self.tasks_table.setCellWidget(row, 4, actions)

    def refresh_activities(self):
        """Refresh activities table"""
        logs = self.db.get_today_logs()
        self.activity_table.setRowCount(len(logs))

        total = 0
        for row, log in enumerate(logs):
            self.activity_table.setItem(row, 0, QTableWidgetItem(log['time'][:5]))
            self.activity_table.setItem(row, 1, QTableWidgetItem(log['activity']))
            dur = log['duration_minutes'] or 0
            self.activity_table.setItem(row, 2, QTableWidgetItem(f"{dur}M" if dur else "-"))
            total += dur
            self.activity_table.setItem(row, 3, QTableWidgetItem(log['category'] or "-"))

        self.total_time_label.setText(f"TOTAL: {total//60}H {total%60}M")

    def refresh_stats(self):
        """Refresh statistics"""
        stats = self.db.get_productivity_stats(7)
        tasks = self.db.get_pending_tasks()

        self.stats_widgets["COMPLETED"].setText(str(stats['tasks_completed']))
        self.stats_widgets["PENDING"].setText(str(len(tasks)))
        self.stats_widgets["PRODUCTIVITY"].setText(f"{screen_time.get_productivity_score()}%")

    def generate_summary(self):
        """Generate daily summary"""
        summary = self.ai.generate_daily_summary()
        self.summary_display.setPlainText(summary)
        self.refresh_stats()
        self.tabs.setCurrentIndex(3)

    def complete_task(self, task_id: int):
        self.db.complete_task(task_id)
        self.refresh_tasks()
        self.refresh_stats()
        self.update_task_overview()

    def delete_task(self, task_id: int):
        self.db.delete_task(task_id)
        self.refresh_tasks()
        self.update_task_overview()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("J.A.R.V.I.S.", "Running in background", QSystemTrayIcon.MessageIcon.Information, 2000)


class CrashHandler:
    """Handle GUI crashes gracefully"""

    def __init__(self):
        self._original_hook = sys.excepthook
        self._error_count = 0
        self._max_errors = 5

    def install(self):
        """Install the crash handler"""
        sys.excepthook = self._handle_exception

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        self._error_count += 1

        # Log the error
        try:
            from core.logger import get_logger
            logger = get_logger("gui_crash")
            logger.critical(
                f"Uncaught GUI exception ({self._error_count}): {exc_value}",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
        except Exception:
            pass

        # Show error dialog for non-KeyboardInterrupt
        if not issubclass(exc_type, KeyboardInterrupt):
            try:
                error_msg = f"An error occurred: {exc_value}\n\nJARVIS will attempt to continue."
                QMessageBox.critical(None, "JARVIS Error", error_msg)
            except Exception:
                pass

        # If too many errors, exit gracefully
        if self._error_count >= self._max_errors:
            try:
                QMessageBox.critical(
                    None,
                    "JARVIS Critical Error",
                    f"Too many errors ({self._error_count}). JARVIS will exit.\n"
                    "Check the logs for details."
                )
            except Exception:
                pass

            # Call original hook and exit
            self._original_hook(exc_type, exc_value, exc_traceback)
            sys.exit(1)


class SafeApplication(QApplication):
    """QApplication wrapper with improved error handling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._crash_handler = CrashHandler()
        self._crash_handler.install()

        # Connect to aboutToQuit for cleanup
        self.aboutToQuit.connect(self._cleanup)

    def _cleanup(self):
        """Cleanup on application exit"""
        try:
            from core.logger import get_logger
            logger = get_logger("gui")
            logger.info("GUI application shutting down")
        except Exception:
            pass

    def notify(self, receiver, event):
        """Override notify to catch exceptions in event handlers"""
        try:
            return super().notify(receiver, event)
        except Exception as e:
            # Log the error
            try:
                from core.logger import get_logger
                logger = get_logger("gui_event")
                logger.error(f"Event handler error: {e}", exc_info=True)
            except Exception:
                pass

            # Show error but continue
            try:
                QMessageBox.warning(
                    None,
                    "JARVIS Warning",
                    f"An error occurred: {e}\n\nThe application will continue."
                )
            except Exception:
                pass

            return False


def run_gui():
    """Run the GUI application with crash protection"""
    # Setup logging
    try:
        from core.logger import setup_crash_handler, get_logger
        setup_crash_handler()
        logger = get_logger("gui")
        logger.info("Starting JARVIS GUI")
    except Exception:
        pass

    try:
        # Use SafeApplication instead of QApplication
        app = SafeApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        # Set application metadata
        app.setApplicationName("JARVIS")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("JARVIS AI")

        # Create and show main window
        window = JarvisMainWindow()
        window.show()

        # Run event loop
        exit_code = app.exec()

        # Clean exit
        try:
            logger.info(f"GUI exited with code {exit_code}")
        except Exception:
            pass

        sys.exit(exit_code)

    except Exception as e:
        # Critical startup error
        try:
            from core.logger import get_logger
            logger = get_logger("gui")
            logger.critical(f"GUI startup failed: {e}", exc_info=True)
        except Exception:
            pass

        print(f"JARVIS GUI failed to start: {e}")
        sys.exit(1)


if __name__ == '__main__':
    run_gui()
