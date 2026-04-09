#!/usr/bin/env python3
"""
输入/输出时间追踪器
用于个人行为分析，追踪 Input（阅读/观看）和 Output（行动/创作）的时间分配
"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QMouseEvent


class StateType(Enum):
    """状态类型"""
    IDLE = auto()   # 空闲/未开始
    INPUT = auto()  # 输入状态（阅读/观看）
    OUTPUT = auto() # 输出状态（行动/创作）


@dataclass
class StateSession:
    """单次状态会话记录"""
    state_type: StateType
    start_time: datetime
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> timedelta:
        """计算本次会话持续时间"""
        end = self.end_time or datetime.now()
        return end - self.start_time
    
    def end(self) -> None:
        """结束本次会话"""
        if self.end_time is None:
            self.end_time = datetime.now()


@dataclass
class TimeStats:
    """时间统计结果"""
    input_seconds: int = 0
    output_seconds: int = 0
    total_seconds: int = 0
    input_percent: float = 0.0
    output_percent: float = 0.0


class TrackerState:
    """
    追踪器状态管理类
    
    职责：
    1. 管理当前状态（IDLE/INPUT/OUTPUT）
    2. 记录所有状态会话
    3. 计算累计时间（Input/Output）
    4. 提供状态切换接口
    5. 通知UI更新时间
    
    设计原则：
    - 所有时间计算基于实际时间点，避免累计误差
    - 当前进行中的会话实时计算持续时间
    """
    
    def __init__(self) -> None:
        self._current_state: StateType = StateType.IDLE
        self._sessions: list[StateSession] = []
        self._current_session: Optional[StateSession] = None
        self._tick_callbacks: list[Callable] = []
    
    # ------------------- 状态查询 -------------------
    
    @property
    def current_state(self) -> StateType:
        return self._current_state
    
    def is_idle(self) -> bool:
        return self._current_state == StateType.IDLE
    
    def is_input(self) -> bool:
        return self._current_state == StateType.INPUT
    
    def is_output(self) -> bool:
        return self._current_state == StateType.OUTPUT
    
    # ------------------- 状态切换 -------------------
    
    def start_input(self) -> None:
        """切换到 Input 状态"""
        if self._current_state != StateType.INPUT:
            self._end_current_session()
            self._current_state = StateType.INPUT
            self._start_new_session(StateType.INPUT)
    
    def start_output(self) -> None:
        """切换到 Output 状态"""
        if self._current_state != StateType.OUTPUT:
            self._end_current_session()
            self._current_state = StateType.OUTPUT
            self._start_new_session(StateType.OUTPUT)
    
    def stop(self) -> None:
        """停止追踪，回到空闲状态"""
        self._end_current_session()
        self._current_state = StateType.IDLE
    
    def reset(self) -> None:
        """重置所有数据"""
        self._end_current_session()
        self._sessions.clear()
        self._current_state = StateType.IDLE
    
    def _start_new_session(self, state_type: StateType) -> None:
        """开始新的会话"""
        self._current_session = StateSession(
            state_type=state_type,
            start_time=datetime.now()
        )
    
    def _end_current_session(self) -> None:
        """结束当前会话"""
        if self._current_session:
            self._current_session.end()
            self._sessions.append(self._current_session)
            self._current_session = None
    
    # ------------------- 时间计算 -------------------
    
    def get_stats(self) -> TimeStats:
        """
        获取当前时间统计
        
        计算方法：
        1. 遍历所有已结束的会话，累加时间
        2. 加上当前进行中的会话的实时持续时间
        3. 计算百分比
        """
        input_seconds = 0
        output_seconds = 0
        
        # 累加已结束会话的时间
        for session in self._sessions:
            duration = int(session.duration.total_seconds())
            if session.state_type == StateType.INPUT:
                input_seconds += duration
            elif session.state_type == StateType.OUTPUT:
                output_seconds += duration
        
        # 加上当前会话的实时时间
        if self._current_session:
            current_duration = int(self._current_session.duration.total_seconds())
            if self._current_session.state_type == StateType.INPUT:
                input_seconds += current_duration
            elif self._current_session.state_type == StateType.OUTPUT:
                output_seconds += current_duration
        
        total_seconds = input_seconds + output_seconds
        
        # 计算百分比
        input_percent = 0.0
        output_percent = 0.0
        if total_seconds > 0:
            input_percent = round(input_seconds / total_seconds * 100, 1)
            output_percent = round(output_seconds / total_seconds * 100, 1)
        
        return TimeStats(
            input_seconds=input_seconds,
            output_seconds=output_seconds,
            total_seconds=total_seconds,
            input_percent=input_percent,
            output_percent=output_percent
        )
    
    # ------------------- UI通知 -------------------
    
    def on_tick(self, callback: Callable) -> None:
        """注册每秒更新的回调函数"""
        self._tick_callbacks.append(callback)
    
    def tick(self) -> None:
        """触发所有注册的回调（由 QTimer 调用）"""
        for callback in self._tick_callbacks:
            callback()


class MainWindow(QMainWindow):
    """
    主窗口类
    
    职责：
    1. 构建和显示UI界面
    2. 处理用户交互（按钮点击、拖拽等）
    3. 接收状态更新通知并刷新显示
    4. 管理 QTimer 定时器
    
    设计原则：
    - 不包含任何时间计算逻辑，所有数据来自 TrackerState
    - 仅负责展示和交互
    """
    
    def __init__(self, state: TrackerState) -> None:
        super().__init__()
        self._state = state
        self._drag_position: Optional[Qt.MouseButton] = None
        
        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._connect_signals()
        
        # 注册状态更新回调
        self._state.on_tick(self._update_display)
    
    # ------------------- 窗口设置 -------------------
    
    def _setup_window(self) -> None:
        """配置窗口属性"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # 无边框
            Qt.WindowType.WindowStaysOnTopHint    # 始终置顶
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(220, 160)
        self.move(100, 100)  # 初始位置
    
    # ------------------- UI构建 -------------------
    
    def _setup_ui(self) -> None:
        """构建用户界面"""
        # 中央容器（带圆角和背景）
        self._container = QFrame(self)
        self._container.setGeometry(0, 0, 220, 160)
        self._container.setObjectName("container")
        self._container.setStyleSheet("""
            #container {
                background-color: #2d2d2d;
                border-radius: 12px;
                border: 1px solid #404040;
            }
        """)
        
        # 主布局
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)
        
        # 标题栏（含关闭按钮）
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        
        self._title_label = QLabel("⏱ I/O Tracker")
        self._title_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(self._title_label)
        
        header_layout.addStretch()
        
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff6b6b;
            }
        """)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self._close_btn)
        
        layout.addLayout(header_layout)
        
        # 状态按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self._input_btn = QPushButton("📥 Input")
        self._input_btn.setFixedHeight(36)
        self._input_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._input_btn.setCheckable(True)
        
        self._output_btn = QPushButton("📤 Output")
        self._output_btn.setFixedHeight(36)
        self._output_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._output_btn.setCheckable(True)
        
        self._style_buttons()
        
        btn_layout.addWidget(self._input_btn)
        btn_layout.addWidget(self._output_btn)
        layout.addLayout(btn_layout)
        
        # 数据显示区域
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        
        # Input 时间
        input_layout = QVBoxLayout()
        input_layout.setSpacing(2)
        
        input_title = QLabel("📥 Input")
        input_title.setStyleSheet("color: #4ecdc4; font-size: 11px;")
        input_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(input_title)
        
        self._input_time_label = QLabel("00:00:00")
        self._input_time_label.setStyleSheet("color: #fff; font-size: 16px; font-weight: bold;")
        self._input_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(self._input_time_label)
        
        stats_layout.addLayout(input_layout)
        
        # Output 时间
        output_layout = QVBoxLayout()
        output_layout.setSpacing(2)
        
        output_title = QLabel("📤 Output")
        output_title.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        output_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        output_layout.addWidget(output_title)
        
        self._output_time_label = QLabel("00:00:00")
        self._output_time_label.setStyleSheet("color: #fff; font-size: 16px; font-weight: bold;")
        self._output_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        output_layout.addWidget(self._output_time_label)
        
        stats_layout.addLayout(output_layout)
        
        layout.addLayout(stats_layout)
        
        # 比例显示
        self._ratio_label = QLabel("Input: 0% | Output: 0%")
        self._ratio_label.setStyleSheet("color: #888; font-size: 11px;")
        self._ratio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._ratio_label)
    
    def _style_buttons(self) -> None:
        """设置按钮样式"""
        base_style = """
            QPushButton {
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                border: 2px solid %s;
                color: %s;
                background: %s;
            }
            QPushButton:hover {
                background: %s;
            }
            QPushButton:checked {
                background: %s;
                color: #2d2d2d;
            }
        """
        
        # Input 按钮样式（青色主题）
        self._input_btn.setStyleSheet(base_style % (
            "#4ecdc4",      # border
            "#4ecdc4",      # color
            "transparent",  # background
            "rgba(78, 205, 196, 0.15)",  # hover
            "#4ecdc4",      # checked
        ))
        
        # Output 按钮样式（红色主题）
        self._output_btn.setStyleSheet(base_style % (
            "#ff6b6b",      # border
            "#ff6b6b",      # color
            "transparent",  # background
            "rgba(255, 107, 107, 0.15)",  # hover
            "#ff6b6b",      # checked
        ))
    
    # ------------------- 定时器 -------------------
    
    def _setup_timer(self) -> None:
        """配置 QTimer 定时器"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start(1000)  # 每秒触发一次
    
    def _on_timer_tick(self) -> None:
        """定时器触发回调"""
        self._state.tick()
    
    # ------------------- 信号连接 -------------------
    
    def _connect_signals(self) -> None:
        """连接信号与槽"""
        self._input_btn.clicked.connect(self._on_input_clicked)
        self._output_btn.clicked.connect(self._on_output_clicked)
        self._close_btn.clicked.connect(self.close)
    
    def _on_input_clicked(self) -> None:
        """Input 按钮点击处理"""
        if self._input_btn.isChecked():
            self._state.start_input()
            self._output_btn.setChecked(False)
        else:
            self._state.stop()
        self._update_display()
    
    def _on_output_clicked(self) -> None:
        """Output 按钮点击处理"""
        if self._output_btn.isChecked():
            self._state.start_output()
            self._input_btn.setChecked(False)
        else:
            self._state.stop()
        self._update_display()
    
    # ------------------- 显示更新 -------------------
    
    def _update_display(self) -> None:
        """刷新UI显示"""
        stats = self._state.get_stats()
        
        # 更新时间显示
        self._input_time_label.setText(self._format_time(stats.input_seconds))
        self._output_time_label.setText(self._format_time(stats.output_seconds))
        
        # 更新比例显示
        self._ratio_label.setText(
            f"Input: {stats.input_percent}% | Output: {stats.output_percent}%"
        )
        
        # 同步按钮状态
        self._input_btn.setChecked(self._state.is_input())
        self._output_btn.setChecked(self._state.is_output())
    
    @staticmethod
    def _format_time(total_seconds: int) -> str:
        """将秒数格式化为 HH:MM:SS"""
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # ------------------- 鼠标事件（支持拖拽移动） -------------------
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        event.accept()


def main() -> None:
    """程序入口"""
    app = QApplication(sys.argv)
    
    # 创建状态管理器
    state = TrackerState()
    
    # 创建主窗口
    window = MainWindow(state)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
