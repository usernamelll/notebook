import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import re
import random
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QDoubleSpinBox,
    QGroupBox,
    QDateEdit,
    QTimeEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFormLayout,
    QInputDialog,
    QDialog,
    QTextEdit,
)
from PySide6.QtCore import Qt, QDateTime, Signal, Slot, QThread
from PySide6.QtGui import QFont, QColor
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = [
    "SimHei",
    "Microsoft YaHei",
    "SimSun",
]  # 黑体、微软雅黑、宋体
plt.rcParams["axes.unicode_minus"] = False

# 基础配置
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DEFAULT_FONT = QFont("Microsoft YaHei", 10)
TITLE_FONT = QFont("Microsoft YaHei", 14, QFont.Bold)
LARGE_FONT = QFont("Microsoft YaHei", 24, QFont.Bold)


class TimerThread(QThread):
    """计时器线程"""

    update_signal = Signal(int)
    pomodoro_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.elapsed = 0
        self.parent = parent

    def run(self):
        self.running = True
        start_time = time.time() - self.elapsed

        while self.running:
            self.elapsed = int(time.time() - start_time)
            self.update_signal.emit(self.elapsed)

            # 番茄钟周期检查
            if self.parent.pomodoro_mode:
                self.check_pomodoro_cycle()

            time.sleep(1)

    def check_pomodoro_cycle(self):
        """检查番茄钟周期是否完成"""
        if self.parent.current_pomodoro % 2 == 0:  # 工作周期
            if self.elapsed % self.parent.pomodoro_length == 0 and self.elapsed > 0:
                self.parent.pomodoro_count += 1
                self.parent.current_pomodoro += 1
                self.pomodoro_signal.emit()
        else:  # 休息周期
            if (
                self.parent.pomodoro_count % (self.parent.long_break_interval * 2)
                == self.parent.long_break_interval * 2 - 1
            ):
                # 长休息
                if self.elapsed % self.parent.long_break == 0 and self.elapsed > 0:
                    self.parent.pomodoro_count += 1
                    self.parent.current_pomodoro += 1
                    self.pomodoro_signal.emit()
            else:
                # 短休息
                if self.elapsed % self.parent.short_break == 0 and self.elapsed > 0:
                    self.parent.pomodoro_count += 1
                    self.parent.current_pomodoro += 1
                    self.pomodoro_signal.emit()

    def stop(self):
        self.running = False
        self.wait()


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class FocusTimeManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("专注时间管理工具")
        self.resize(1000, 700)

        # 数据文件路径
        self.data_file = os.path.join(DATA_DIR, "focus_time_data.csv")
        self.categories_file = os.path.join(DATA_DIR, "categories.txt")
        self.settings_file = os.path.join(DATA_DIR, "pomodoro_settings.csv")

        # 初始化数据
        self.categories = self.load_categories() or [
            "英语",
            "数学",
            "政治",
            "408",
            "做题",
        ]
        self.pomodoro_settings = self.load_pomodoro_settings()
        self.pomodoro_length = self.pomodoro_settings.get("work", 25) * 60
        self.short_break = self.pomodoro_settings.get("short_break", 5) * 60
        self.long_break = self.pomodoro_settings.get("long_break", 15) * 60
        self.long_break_interval = self.pomodoro_settings.get("interval", 4)

        # 计时相关变量
        self.timer_running = False
        self.elapsed_time = 0
        self.timer_thread = TimerThread(self)
        self.timer_thread.update_signal.connect(self.update_timer_display)
        self.timer_thread.pomodoro_signal.connect(self.pomodoro_notify)
        self.pomodoro_mode = False
        self.pomodoro_count = 0
        self.current_pomodoro = 0

        # 加载数据
        self.data = self.load_data()

        # 设置全局字体
        self.setFont(DEFAULT_FONT)

        # 主布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 标签页控件
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # 初始化各个标签页
        self.init_main_tab()
        self.init_records_tab()
        # 状态栏
        self.statusBar().showMessage("就绪")

    # 主计时器标签页
    def init_main_tab(self):
        main_tab = QWidget()
        self.tab_widget.addTab(main_tab, "时间管理")

        main_splitter = QSplitter(Qt.Vertical)
        main_layout = QVBoxLayout(main_tab)
        main_layout.addWidget(main_splitter)

        # 计时器区域
        timer_widget = QWidget()
        timer_layout = QVBoxLayout(timer_widget)

        title_label = QLabel("专注时间计时器")
        title_label.setFont(TITLE_FONT)
        title_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(title_label)

        # 控制区
        control_layout = QHBoxLayout()
        timer_layout.addLayout(control_layout)

        control_layout.addWidget(QLabel("学习标签:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(self.categories)
        control_layout.addWidget(self.category_combo)

        control_layout.addStretch()

        self.pomodoro_check = QPushButton("启用番茄钟模式")
        self.pomodoro_check.setCheckable(True)
        self.pomodoro_check.clicked.connect(self.toggle_pomodoro)
        control_layout.addWidget(self.pomodoro_check)

        self.pomodoro_settings_btn = QPushButton("番茄钟设置")
        self.pomodoro_settings_btn.clicked.connect(self.open_pomodoro_settings)
        control_layout.addWidget(self.pomodoro_settings_btn)

        # 计时器显示
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setFont(LARGE_FONT)
        self.timer_display.setAlignment(Qt.AlignCenter)
        self.timer_display.setStyleSheet(
            "background-color: #f0f7ff; padding: 15px; margin: 10px 0; border-radius: 8px;"
        )
        timer_layout.addWidget(self.timer_display)

        self.pomodoro_status = QLabel("")
        self.pomodoro_status.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.pomodoro_status)

        # 控制按钮
        btn_layout = QHBoxLayout()
        timer_layout.addLayout(btn_layout)

        self.start_btn = QPushButton("开始计时")
        self.start_btn.clicked.connect(self.start_timer)
        btn_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause_timer)
        self.pause_btn.setEnabled(False)
        btn_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("结束并保存")
        self.stop_btn.clicked.connect(self.stop_timer)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        main_splitter.addWidget(timer_widget)

        # 手动记录区域
        manual_widget = QWidget()
        manual_layout = QVBoxLayout(manual_widget)

        manual_group = QGroupBox("手动记录")
        manual_layout.addWidget(manual_group)

        manual_form = QFormLayout(manual_group)

        self.manual_date = QDateEdit(QDateTime.currentDateTime().date())
        self.manual_date.setDisplayFormat("yyyy-MM-dd")
        manual_form.addRow("日期:", self.manual_date)

        self.manual_time = QTimeEdit(QDateTime.currentDateTime().time())
        self.manual_time.setDisplayFormat("HH:mm:ss")
        manual_form.addRow("时间:", self.manual_time)

        self.manual_category = QComboBox()
        self.manual_category.addItems(self.categories)
        manual_form.addRow("标签:", self.manual_category)

        self.manual_duration = QDoubleSpinBox()
        self.manual_duration.setRange(0, 1440.0)
        self.manual_duration.setSingleStep(0.5)
        manual_form.addRow("时长(分钟):", self.manual_duration)

        self.manual_save_btn = QPushButton("保存记录")
        self.manual_save_btn.clicked.connect(self.save_manual_data)
        manual_form.addRow(self.manual_save_btn)

        main_splitter.addWidget(manual_widget)
        main_splitter.setSizes([400, 300])

    # 记录标签页
    def init_records_tab(self):
        records_tab = QWidget()
        self.tab_widget.addTab(records_tab, "学习记录")

        layout = QVBoxLayout(records_tab)

        title_label = QLabel("学习记录管理")
        title_label.setFont(TITLE_FONT)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 标签管理
        category_widget = QWidget()
        category_layout = QVBoxLayout(category_widget)

        category_group = QGroupBox("标签管理")
        category_layout.addWidget(category_group)

        category_form = QVBoxLayout(category_group)

        self.category_list = QListWidget()
        self.category_list.addItems(self.categories)
        category_form.addWidget(self.category_list)

        btn_layout = QHBoxLayout()
        self.add_category_btn = QPushButton("添加标签")
        self.add_category_btn.clicked.connect(self.add_category)
        btn_layout.addWidget(self.add_category_btn)

        self.edit_category_btn = QPushButton("修改标签")
        self.edit_category_btn.clicked.connect(self.edit_category)
        btn_layout.addWidget(self.edit_category_btn)

        self.delete_category_btn = QPushButton("删除标签")
        self.delete_category_btn.clicked.connect(self.delete_category)
        btn_layout.addWidget(self.delete_category_btn)

        category_form.addLayout(btn_layout)
        splitter.addWidget(category_widget)

        # 记录列表
        records_widget = QWidget()
        records_layout = QVBoxLayout(records_widget)

        records_group = QGroupBox("学习记录")
        records_layout.addWidget(records_group)

        records_table_layout = QVBoxLayout(records_group)

        self.records_table = QTableWidget()
        self.records_table.setColumnCount(4)
        self.records_table.setHorizontalHeaderLabels(
            ["日期", "时间", "标签", "时长(分钟)"]
        )
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        records_table_layout.addWidget(self.records_table)

        # 记录管理按钮
        records_btn_layout = QHBoxLayout()
        self.refresh_records_btn = QPushButton("刷新记录")
        self.refresh_records_btn.clicked.connect(self.update_records_table)
        records_btn_layout.addWidget(self.refresh_records_btn)

        self.delete_record_btn = QPushButton("删除选中记录")
        self.delete_record_btn.clicked.connect(self.delete_selected_record)
        records_btn_layout.addWidget(self.delete_record_btn)

        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self.export_data)
        records_btn_layout.addWidget(self.export_btn)

        records_table_layout.addLayout(records_btn_layout)
        splitter.addWidget(records_widget)

        splitter.setSizes([200, 700])
        self.update_records_table()

    # 计时器相关功能
    def toggle_pomodoro(self):
        self.pomodoro_mode = self.pomodoro_check.isChecked()
        if self.pomodoro_mode and not self.timer_running:
            self.elapsed_time = 0
            self.current_pomodoro = 0
            self.pomodoro_count = 0
            self.update_timer_display(0)
            self.update_pomodoro_status()
        else:
            self.update_pomodoro_status()

    def open_pomodoro_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("番茄钟设置")
        dialog.resize(300, 200)
        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 60)
        self.work_spin.setValue(int(self.pomodoro_length / 60))
        form_layout.addRow("工作时长(分钟):", self.work_spin)

        self.short_break_spin = QSpinBox()
        self.short_break_spin.setRange(1, 30)
        self.short_break_spin.setValue(int(self.short_break / 60))
        form_layout.addRow("短休息时长(分钟):", self.short_break_spin)

        self.long_break_spin = QSpinBox()
        self.long_break_spin.setRange(5, 60)
        self.long_break_spin.setValue(int(self.long_break / 60))
        form_layout.addRow("长休息时长(分钟):", self.long_break_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10)
        self.interval_spin.setValue(self.long_break_interval)
        form_layout.addRow("长休息间隔(个):", self.interval_spin)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            self.pomodoro_length = self.work_spin.value() * 60
            self.short_break = self.short_break_spin.value() * 60
            self.long_break = self.long_break_spin.value() * 60
            self.long_break_interval = self.interval_spin.value()

            settings = {
                "work": self.work_spin.value(),
                "short_break": self.short_break_spin.value(),
                "long_break": self.long_break_spin.value(),
                "interval": self.interval_spin.value(),
            }
            self.save_pomodoro_settings(settings)
            self.update_pomodoro_status()

    def start_timer(self):
        if not self.timer_running:
            self.timer_running = True
            self.timer_thread.elapsed = self.elapsed_time
            self.timer_thread.start()
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.category_combo.setEnabled(False)

    def pause_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.timer_thread.stop()
            self.elapsed_time = self.timer_thread.elapsed
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)

    def stop_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.timer_thread.stop()
            self.elapsed_time = self.timer_thread.elapsed

        # 时长小于1分钟（60秒）不保存
        if self.elapsed_time < 60:
            QMessageBox.information(self, "提示", "时长小于1分钟，不保存记录")
            self.reset_timer()
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.category_combo.setEnabled(True)
            # 直接返回，避免执行后续重复代码
            return

        # 时长 >=1 分钟时执行保存逻辑
        minutes = self.elapsed_time / 60
        category = self.category_combo.currentText()

        reply = QMessageBox.question(
            self,
            "保存记录",
            f"是否保存 {category} 的学习记录: {minutes:.1f} 分钟?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.save_timer_data(category, self.elapsed_time)
            QMessageBox.information(self, "成功", f"已保存 {minutes:.1f} 分钟")

        self.reset_timer()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.category_combo.setEnabled(True)
        self.update_records_table()

    def reset_timer(self):
        self.elapsed_time = 0
        self.timer_thread.elapsed = 0
        self.current_pomodoro = 0
        self.update_timer_display(0)
        self.update_pomodoro_status()

    @Slot(int)
    def update_timer_display(self, elapsed):
        self.elapsed_time = elapsed
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.timer_display.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        if self.pomodoro_mode:
            self.update_pomodoro_status()

    def update_pomodoro_status(self):
        if not self.pomodoro_mode:
            self.pomodoro_status.setText("")
            return

        if self.timer_running:
            if self.current_pomodoro % 2 == 0:  # 工作时段
                remaining = self.pomodoro_length - (
                    self.elapsed_time % self.pomodoro_length
                )
                status = f"工作时段 - 剩余: {self.format_time(remaining)} | 已完成 {self.pomodoro_count//2} 个番茄钟"
            else:  # 休息时段
                if (
                    self.pomodoro_count % (self.long_break_interval * 2)
                    == self.long_break_interval * 2 - 1
                ):
                    remaining = self.long_break - (self.elapsed_time % self.long_break)
                    status = f"长休息时段 - 剩余: {self.format_time(remaining)}"
                else:
                    remaining = self.short_break - (
                        self.elapsed_time % self.short_break
                    )
                    status = f"短休息时段 - 剩余: {self.format_time(remaining)}"
        else:
            status = f"已完成 {self.pomodoro_count//2} 个番茄钟"

        self.pomodoro_status.setText(status)

    def format_time(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def pomodoro_notify(self):
        if self.current_pomodoro % 2 == 1:
            QMessageBox.information(self, "提示", "工作时段结束！该休息一下了。")
        else:
            QMessageBox.information(self, "提示", "休息结束！准备开始新的工作时段吧。")

    # 数据管理功能
    def save_timer_data(self, category, seconds):
        minutes = round(seconds / 60, 1)
        date = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")

        file_exists = os.path.exists(self.data_file)

        with open(self.data_file, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write("日期,时间,标签,时长(分钟)\n")
            f.write(f"{date},{time_str},{category},{minutes}\n")

        self.data = self.load_data()

    def save_manual_data(self):
        date = self.manual_date.date().toString("yyyy-MM-dd")
        time_str = self.manual_time.time().toString("HH:mm:ss")
        category = self.manual_category.currentText()
        duration = self.manual_duration.value()

        if duration <= 0:
            QMessageBox.warning(self, "错误", "时长必须大于0")
            return

        file_exists = os.path.exists(self.data_file)

        with open(self.data_file, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write("日期,时间,标签,时长(分钟)\n")
            f.write(f"{date},{time_str},{category},{duration}\n")

        QMessageBox.information(self, "成功", "学习时间已保存")
        self.manual_duration.setValue(0)
        self.data = self.load_data()
        self.update_records_table()

    def update_records_table(self):
        self.data = self.load_data()
        self.records_table.setRowCount(0)

        if self.data.empty:
            return

        self.data = self.data.sort_values(by=["日期", "时间"], ascending=False)

        for idx, row in self.data.iterrows():
            row_pos = self.records_table.rowCount()
            self.records_table.insertRow(row_pos)

            self.records_table.setItem(
                row_pos, 0, QTableWidgetItem(row["日期"].strftime("%Y-%m-%d"))
            )
            self.records_table.setItem(row_pos, 1, QTableWidgetItem(row["时间"]))
            self.records_table.setItem(row_pos, 2, QTableWidgetItem(row["标签"]))
            self.records_table.setItem(
                row_pos, 3, QTableWidgetItem(f"{row['时长(分钟)']:.1f}")
            )

    def delete_selected_record(self):
        selected_items = self.records_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要删除的记录")
            return

        selected_row = selected_items[0].row()
        date = self.records_table.item(selected_row, 0).text()
        time_str = self.records_table.item(selected_row, 1).text()
        category = self.records_table.item(selected_row, 2).text()

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 {date} {time_str} 的 {category} 记录吗?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.data = self.data[
                ~(
                    (self.data["日期"].dt.strftime("%Y-%m-%d") == date)
                    & (self.data["时间"] == time_str)
                    & (self.data["标签"] == category)
                )
            ]
            self.save_dataframe()
            self.update_records_table()

    def export_data(self):
        if self.data.empty:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = os.path.join(DATA_DIR, f"focus_export_{timestamp}.csv")
            self.data.to_csv(export_file, index=False, encoding="utf-8")
            QMessageBox.information(self, "成功", f"数据已导出至 {export_file}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")

    # 标签管理
    def load_categories(self):
        if not os.path.exists(self.categories_file):
            return []

        try:
            with open(self.categories_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []

    def save_categories(self):
        try:
            with open(self.categories_file, "w", encoding="utf-8") as f:
                for category in self.categories:
                    f.write(f"{category}\n")

            self.category_combo.clear()
            self.category_combo.addItems(self.categories)
            self.manual_category.clear()
            self.manual_category.addItems(self.categories)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存标签失败: {str(e)}")

    def add_category(self):
        category, ok = QInputDialog.getText(self, "添加标签", "请输入新标签名称:")
        if ok and category:
            category = category.strip()
            if category in self.categories:
                QMessageBox.warning(self, "提示", f"标签 '{category}' 已存在")
                return

            self.categories.append(category)
            self.category_list.addItem(category)
            self.save_categories()

    def edit_category(self):
        current_item = self.category_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要修改的标签")
            return

        old_category = current_item.text()
        new_category, ok = QInputDialog.getText(
            self, "修改标签", "请输入新的标签名称:", text=old_category
        )

        if ok and new_category and new_category != old_category:
            new_category = new_category.strip()
            if new_category in self.categories:
                QMessageBox.warning(self, "提示", f"标签 '{new_category}' 已存在")
                return

            index = self.categories.index(old_category)
            self.categories[index] = new_category
            current_item.setText(new_category)
            self.data.loc[self.data["标签"] == old_category, "标签"] = new_category
            self.save_dataframe()
            self.save_categories()
            self.update_records_table()

    def delete_category(self):
        current_item = self.category_list.currentItem()
        if not current_item:
            return

        category = current_item.text()

        if not self.data.empty and category in self.data["标签"].values:
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"标签 '{category}' 存在学习记录，删除将同时删除相关记录，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            self.data = self.data[self.data["标签"] != category]
            self.save_dataframe()

        self.categories.remove(category)
        self.category_list.takeItem(self.category_list.row(current_item))
        self.save_categories()
        self.update_records_table()

    # 数据加载与保存
    def load_data(self):
        if not os.path.exists(self.data_file):
            return pd.DataFrame(columns=["日期", "时间", "标签", "时长(分钟)"])

        try:
            return pd.read_csv(self.data_file, parse_dates=["日期"], encoding="utf-8")
        except:
            return pd.DataFrame(columns=["日期", "时间", "标签", "时长(分钟)"])

    def save_dataframe(self):
        try:
            self.data.to_csv(self.data_file, index=False, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存数据失败: {str(e)}")

    def load_pomodoro_settings(self):
        default = {"work": 25, "short_break": 5, "long_break": 15, "interval": 4}
        if not os.path.exists(self.settings_file):
            self.save_pomodoro_settings(default)
            return default

        try:
            df = pd.read_csv(self.settings_file)
            return {
                "work": int(df.iloc[0]["work"]),
                "short_break": int(df.iloc[0]["short_break"]),
                "long_break": int(df.iloc[0]["long_break"]),
                "interval": int(df.iloc[0]["interval"]),
            }
        except:
            return default

    def save_pomodoro_settings(self, settings):
        try:
            pd.DataFrame([settings]).to_csv(self.settings_file, index=False)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存设置失败: {str(e)}")


# AI数据分析模拟函数（实际使用时可替换为真实API调用）
def ai_analyze_data(data, period):
    """模拟AI数据分析，生成个性化学习建议"""
    if data.empty:
        return "暂无学习数据可供分析，开始你的学习记录吧！"

    # 基础统计
    total_time = data["时长(分钟)"].sum()
    avg_time = data["时长(分钟)"].mean()
    top_category = data.groupby("标签")["时长(分钟)"].sum().idxmax()
    top_category_time = data.groupby("标签")["时长(分钟)"].sum().max()
    category_dist = data.groupby("标签")["时长(分钟)"].sum().to_dict()

    # 生成建议
    suggestions = []
    suggestions.append(f"根据你{period}的学习数据，我发现了一些有趣的模式：")
    suggestions.append(
        f"- 你总共投入了{total_time:.1f}分钟学习，平均每次学习{avg_time:.1f}分钟，继续保持！"
    )

    # 学习分布分析
    if len(category_dist) > 1:
        suggestions.append(
            f"- 你的学习重心在「{top_category}」，占总学习时间的{top_category_time/total_time*100:.1f}%"
        )
        min_category = min(category_dist, key=category_dist.get)
        if category_dist[min_category] / total_time < 0.1:
            suggestions.append(
                f"- 「{min_category}」的学习时间较少，建议适当增加投入以平衡知识结构"
            )

    # 时间效率分析
    if avg_time < 20:
        suggestions.append("- 单次学习时长偏短，尝试逐步延长专注时间，有助于深度思考")
    elif avg_time > 60:
        suggestions.append("- 单次学习时长较长，注意适当休息，运用番茄工作法提升效率")

    # 个性化建议
    if total_time < 60:
        suggestions.append(
            "- 本周学习时间较少，建议制定小额目标（如每天30分钟）逐步培养习惯"
        )
    else:
        suggestions.append(
            "- 不错的学习积累！可以尝试设置阶段性目标，进一步提升学习效果"
        )

    suggestions.append("\n下周建议：")
    suggestions.append(
        f"- 保持「{top_category}」的学习节奏，同时尝试增加其他领域10%的学习时间"
    )
    suggestions.append("- 尝试在精力充沛的时段（如早晨）安排难度较高的学习内容")
    suggestions.append("- 每完成3次学习后进行一次小回顾，巩固学习成果")

    return "\n\n".join(suggestions)


class ImprovedFocusTimeManager(FocusTimeManager):
    """优化后的专注时间管理工具，含美化图表和学习建议功能"""

    def __init__(self):
        super().__init__()
        # 初始化AI Key设置
        self.ai_key = self.load_ai_key()
        # 添加学习建议标签页
        self.init_suggestions_tab()
        # 重写统计标签页（移除原建议部分）
        self.init_stats_tab()

    def load_ai_key(self):
        """加载已保存的AI Key"""
        try:
            if os.path.exists("ai_key.txt"):
                with open("ai_key.txt", "r") as f:
                    return f.read().strip()
        except:
            pass
        return None

    def save_ai_key(self, key):
        """保存AI Key"""
        try:
            with open("ai_key.txt", "w") as f:
                f.write(key)
            self.ai_key = key
            return True
        except:
            return False

    def init_suggestions_tab(self):
        """初始化学习建议标签页"""
        suggestions_tab = QWidget()
        self.tab_widget.addTab(suggestions_tab, "学习建议")

        layout = QVBoxLayout(suggestions_tab)

        # 标题
        title_label = QLabel("学习建议")
        title_label.setFont(TITLE_FONT)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 建议类型选择
        type_layout = QHBoxLayout()
        layout.addLayout(type_layout)

        self.suggestion_type = QComboBox()
        self.suggestion_type.addItems(["本地建议", "AI建议"])
        self.suggestion_type.currentIndexChanged.connect(
            self.on_suggestion_type_changed
        )
        type_layout.addWidget(QLabel("建议类型:"))
        type_layout.addWidget(self.suggestion_type)

        # AI Key设置按钮
        self.set_ai_key_btn = QPushButton("设置AI Key")
        self.set_ai_key_btn.clicked.connect(self.set_ai_key_dialog)
        type_layout.addWidget(self.set_ai_key_btn)

        # 周期选择
        period_layout = QHBoxLayout()
        layout.addLayout(period_layout)

        period_layout.addWidget(QLabel("统计周期:"))
        self.suggest_period_combo = QComboBox()
        self.suggest_period_combo.addItems(["每日", "每周", "每月", "每年"])
        self.suggest_period_combo.currentIndexChanged.connect(
            self.update_suggest_period_options
        )
        period_layout.addWidget(self.suggest_period_combo)

        period_layout.addWidget(QLabel("选择时间段:"))
        self.suggest_range_combo = QComboBox()
        self.suggest_range_combo.currentIndexChanged.connect(self.update_suggestions)
        period_layout.addWidget(self.suggest_range_combo)

        # 生成建议按钮
        self.generate_suggest_btn = QPushButton("生成建议")
        self.generate_suggest_btn.clicked.connect(self.update_suggestions)
        period_layout.addWidget(self.generate_suggest_btn)

        period_layout.addStretch()

        # 建议内容区域
        suggestions_group = QGroupBox("建议内容")
        suggestions_group.setFont(DEFAULT_FONT)
        layout.addWidget(suggestions_group)

        suggestions_inner_layout = QVBoxLayout(suggestions_group)
        self.suggestions_text = QTextEdit()
        self.suggestions_text.setFont(DEFAULT_FONT)
        self.suggestions_text.setReadOnly(True)
        self.suggestions_text.setStyleSheet("background-color: #f8fafc; padding: 10px;")
        suggestions_inner_layout.addWidget(self.suggestions_text)

        # 初始化周期选项
        self.update_suggest_period_options()
        # 初始显示本地建议
        self.on_suggestion_type_changed(0)

    def set_ai_key_dialog(self):
        """设置AI Key的对话框"""
        current_key = self.ai_key or ""
        key, ok = QInputDialog.getText(
            self, "设置AI Key", "请输入你的AI API Key:", QLineEdit.Password, current_key
        )

        if ok and key:
            if self.save_ai_key(key):
                QMessageBox.information(self, "成功", "AI Key已保存")
            else:
                QMessageBox.warning(self, "失败", "保存AI Key失败")

    def on_suggestion_type_changed(self, index):
        """建议类型变更处理"""
        is_ai = index == 1
        self.set_ai_key_btn.setVisible(is_ai)
        if is_ai and not self.ai_key:
            self.suggestions_text.setText("请先设置AI Key以使用AI建议功能")
        else:
            self.update_suggestions()

    def update_suggest_period_options(self):
        """更新建议周期选项"""
        period = self.suggest_period_combo.currentText()
        self.suggest_range_combo.clear()

        if period == "每日":
            for i in range(7):
                date = datetime.now() - timedelta(days=i)
                self.suggest_range_combo.addItem(date.strftime("%Y-%m-%d"))
        elif period == "每周":
            for i in range(4):
                start = datetime.now() - timedelta(
                    days=datetime.now().weekday() + 7 * i
                )
                end = start + timedelta(days=6)
                self.suggest_range_combo.addItem(
                    f"{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}"
                )
        elif period == "每月":
            for i in range(6):
                month = datetime.now().month - i
                year = datetime.now().year
                if month <= 0:
                    month += 12
                    year -= 1
                self.suggest_range_combo.addItem(f"{year}年{month}月")
        elif period == "每年":
            for i in range(3):
                year = datetime.now().year - i
                self.suggest_range_combo.addItem(f"{year}年")

    def update_suggestions(self):
        """更新建议内容"""
        if self.data.empty:
            self.suggestions_text.setText("暂无学习数据可供分析，请先记录学习时间哦！")
            return
        
        if self.suggestion_type.currentIndex() == 1 and not self.ai_key:
            self.show_ai_key_prompt()
            return
        
        period = self.suggest_period_combo.currentText()
        range_text = self.suggest_range_combo.currentText()
        
        filtered_data = self.data.copy()
        if period == "每日":
            filtered_data = filtered_data[filtered_data["日期"].dt.strftime("%Y-%m-%d") == range_text]
        elif period == "每周":
            dates = range_text.split(" 至 ")
            start_date = datetime.strptime(dates[0], "%Y-%m-%d")
            end_date = datetime.strptime(dates[1], "%Y-%m-%d")
            filtered_data = filtered_data[(filtered_data["日期"] >= start_date) & (filtered_data["日期"] <= end_date)]
        elif period == "每月":
            year_month = re.match(r"(\d+)年(\d+)月", range_text)
            if year_month:
                year = int(year_month.group(1))
                month = int(year_month.group(2))
                filtered_data = filtered_data[(filtered_data["日期"].dt.year == year) & 
                                            (filtered_data["日期"].dt.month == month)]
        elif period == "每年":
            year = int(range_text[:-1])
            filtered_data = filtered_data[filtered_data["日期"].dt.year == year]
        
        if filtered_data.empty:
            self.suggestions_text.setText(f"所选{period}{range_text}没有学习数据")
            return
        
        if self.suggestion_type.currentIndex() == 0:
            # ========== 本地建议（丰富版） ==========
            total_time = filtered_data["时长(分钟)"].sum()
            avg_time = filtered_data["时长(分钟)"].mean()
            session_count = len(filtered_data)
            category_stats = filtered_data.groupby("标签")["时长(分钟)"].sum().sort_values(ascending=False)
            top_category = category_stats.index[0] if not category_stats.empty else "无"
            top_time = category_stats.iloc[0] if not category_stats.empty else 0
            category_count = len(category_stats)
            
            # 时长分析
            duration_suggest = []
            if total_time < 180:  # 低于3小时
                duration_suggest.append("- 总学习时间偏短，建议每天固定30分钟专注时段，逐步培养习惯")
            elif total_time < 480:  # 3-8小时
                duration_suggest.append("- 学习时长适中，可尝试增加10%的深度学习时间（如沉浸式刷题、总结）")
            else:  # 超过8小时
                duration_suggest.append("- 学习时长充足，注意劳逸结合，每90分钟休息10分钟效果更佳")
            
            # 类别分析
            category_suggest = []
            if category_count == 1:
                category_suggest.append(f"- 仅专注于「{top_category}」，建议加入1-2个互补类别（如学完数学后做10分钟英语阅读）")
            else:
                category_suggest.append(f"- 学习重心在「{top_category}」（占{top_time/total_time*100:.1f}%），可适当增加占比不足15%类别的投入")
            
            # 时间效率分析
            efficiency_suggest = []
            if avg_time < 20:
                efficiency_suggest.append("- 单次学习时长偏短，尝试用番茄钟法（25分钟专注+5分钟休息）提升专注深度")
            elif avg_time > 60:
                efficiency_suggest.append("- 单次学习时长较长，建议每45分钟做一次知识小结，避免疲劳导致效率下降")
            
            # 整合建议
            suggestions = [
                f"📊 {period}{range_text} 学习全景分析",
                f"- 总学习时间：{total_time:.1f}分钟 | 平均每次：{avg_time:.1f}分钟 | 学习次数：{session_count}次",
                f"- 学习类别：{category_count}个 | 核心类别：{top_category}（{top_time:.1f}分钟）",
                "\n✨ 针对性建议",
                *duration_suggest,
                *category_suggest,
                *efficiency_suggest,
                "\n📅 下周行动清单",
                "- 每天在固定时段（如晚8点）安排30分钟「薄弱类别」学习",
                "- 尝试用「学习日志」记录每次学习的关键收获（仅需2分钟）",
                "- 周末花15分钟做本周学习内容的思维导图梳理"
            ]
            
            self.suggestions_text.setText("\n\n".join(suggestions))
        else:
            # AI建议（保持不变）
            self.suggestions_text.setText("正在分析数据，生成个性化建议...")
            QApplication.processEvents()
            time.sleep(1)
            suggestion = ai_analyze_data(filtered_data, f"{period}{range_text}")
            self.suggestions_text.setText(suggestion)
            """更新建议内容"""
            if self.data.empty:
                self.suggestions_text.setText("暂无学习数据可供分析，请先记录学习时间哦！")
                return

            if self.suggestion_type.currentIndex() == 1 and not self.ai_key:
                self.show_ai_key_prompt()
                return

            period = self.suggest_period_combo.currentText()
            range_text = self.suggest_range_combo.currentText()

            filtered_data = self.data.copy()
            if period == "每日":
                filtered_data = filtered_data[
                    filtered_data["日期"].dt.strftime("%Y-%m-%d") == range_text
                ]
            elif period == "每周":
                dates = range_text.split(" 至 ")
                start_date = datetime.strptime(dates[0], "%Y-%m-%d")
                end_date = datetime.strptime(dates[1], "%Y-%m-%d")
                filtered_data = filtered_data[
                    (filtered_data["日期"] >= start_date)
                    & (filtered_data["日期"] <= end_date)
                ]
            elif period == "每月":
                year_month = re.match(r"(\d+)年(\d+)月", range_text)
                if year_month:
                    year = int(year_month.group(1))
                    month = int(year_month.group(2))
                    filtered_data = filtered_data[
                        (filtered_data["日期"].dt.year == year)
                        & (filtered_data["日期"].dt.month == month)
                    ]
            elif period == "每年":
                year = int(range_text[:-1])
                filtered_data = filtered_data[filtered_data["日期"].dt.year == year]

            if filtered_data.empty:
                self.suggestions_text.setText(f"所选{period}{range_text}没有学习数据")
                return

            if self.suggestion_type.currentIndex() == 0:
                total_time = filtered_data["时长(分钟)"].sum()
                avg_time = filtered_data["时长(分钟)"].mean()

                suggestions = [
                    f"{period}{range_text}学习总结：",
                    f"- 总学习时间：{total_time:.1f}分钟",
                    f"- 平均每次学习：{avg_time:.1f}分钟",
                    f"- 学习次数：{len(filtered_data)}次",
                ]

                self.suggestions_text.setText("\n\n".join(suggestions))
            else:
                self.suggestions_text.setText("正在分析数据，生成个性化建议...")
                QApplication.processEvents()
                time.sleep(1)
                suggestion = ai_analyze_data(filtered_data, f"{period}{range_text}")
                self.suggestions_text.setText(suggestion)

    def show_ai_key_prompt(self):
        reply = QMessageBox.question(
            self,
            "缺少AI Key",
            "使用AI建议需要先设置API Key，是否现在设置？\n\n"
            "设置方法：\n1. 前往AI服务提供商获取API Key\n"
            "2. 在弹出的对话框中输入并保存",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.set_ai_key_dialog()

    def init_stats_tab(self):
        """重写统计标签页，只保留图表显示"""
        stats_tab = QWidget()
        self.tab_widget.addTab(stats_tab, "数据统计")

        layout = QVBoxLayout(stats_tab)

        title_label = QLabel("学习数据分析")
        title_label.setFont(TITLE_FONT)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        period_layout = QHBoxLayout()
        layout.addLayout(period_layout)

        period_layout.addWidget(QLabel("统计周期:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["每日", "每周", "每月", "每年"])
        self.period_combo.currentIndexChanged.connect(self.update_period_options)
        period_layout.addWidget(self.period_combo)

        period_layout.addWidget(QLabel("选择时间段:"))
        self.range_combo = QComboBox()
        self.range_combo.currentIndexChanged.connect(self.update_stats)
        period_layout.addWidget(self.range_combo)

        self.refresh_chart_btn = QPushButton("刷新数据")
        self.refresh_chart_btn.clicked.connect(self.update_stats)
        period_layout.addWidget(self.refresh_chart_btn)

        period_layout.addStretch()

        stats_info_layout = QHBoxLayout()
        layout.addLayout(stats_info_layout)

        self.total_time_label = QLabel("总专注时间: -- 分钟")
        self.avg_time_label = QLabel("平均时长: -- 分钟")
        self.sessions_label = QLabel("学习次数: -- 次")
        for label in [self.total_time_label, self.avg_time_label, self.sessions_label]:
            label.setFont(DEFAULT_FONT)
            label.setStyleSheet(
                "margin: 5px 15px; padding: 5px; background-color: #f0f7ff; border-radius: 4px;"
            )
            stats_info_layout.addWidget(label)

        charts_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(charts_splitter)

        bar_widget = QWidget()
        bar_layout = QVBoxLayout(bar_widget)
        bar_group = QGroupBox("学习时长")
        bar_group.setFont(DEFAULT_FONT)
        bar_layout.addWidget(bar_group)

        bar_inner_layout = QVBoxLayout(bar_group)
        self.bar_chart = MplCanvas(width=5, height=4, dpi=100)
        bar_inner_layout.addWidget(self.bar_chart)
        charts_splitter.addWidget(bar_widget)

        ring_widget = QWidget()
        ring_layout = QVBoxLayout(ring_widget)
        ring_group = QGroupBox("学习占比")
        ring_group.setFont(DEFAULT_FONT)
        ring_layout.addWidget(ring_group)

        ring_inner_layout = QVBoxLayout(ring_group)
        self.ring_chart = MplCanvas(width=5, height=4, dpi=100)
        ring_inner_layout.addWidget(self.ring_chart)
        charts_splitter.addWidget(ring_widget)

        charts_splitter.setSizes([500, 500])

        self.update_period_options()

    def update_period_options(self):
        period = self.period_combo.currentText()
        self.range_combo.clear()

        if period == "每日":
            for i in range(14):
                date = datetime.now() - timedelta(days=i)
                self.range_combo.addItem(date.strftime("%Y-%m-%d"))
        elif period == "每周":
            today = datetime.now()
            for i in range(8):
                start = today - timedelta(days=today.weekday() + i * 7)
                end = start + timedelta(days=6)
                self.range_combo.addItem(
                    f"{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}"
                )
        elif period == "每月":
            today = datetime.now()
            for i in range(6):
                month = today.month - i
                year = today.year
                if month <= 0:
                    month += 12
                    year -= 1
                self.range_combo.addItem(f"{year}年{month}月")
        elif period == "每年":
            current_year = datetime.now().year
            for i in range(5):
                self.range_combo.addItem(f"{current_year - i}年")

        if self.range_combo.count() > 0:
            self.update_stats()

    def update_stats(self):
        if self.data.empty:
            self.total_time_label.setText("总专注时间: 0 分钟")
            self.avg_time_label.setText("平均时长: 0 分钟")
            self.sessions_label.setText("学习次数: 0 次")
            return

        period = self.period_combo.currentText()
        range_text = self.range_combo.currentText()
        filtered_data = self.data.copy()

        if period == "每日":
            filtered_data = filtered_data[
                filtered_data["日期"].dt.strftime("%Y-%m-%d") == range_text
            ]
        elif period == "每周":
            dates = range_text.split(" 至 ")
            start_date = datetime.strptime(dates[0], "%Y-%m-%d")
            end_date = datetime.strptime(dates[1], "%Y-%m-%d")
            filtered_data = filtered_data[
                (filtered_data["日期"] >= start_date)
                & (filtered_data["日期"] <= end_date)
            ]
        elif period == "每月":
            year_month = re.match(r"(\d+)年(\d+)月", range_text)
            if year_month:
                year = int(year_month.group(1))
                month = int(year_month.group(2))
                filtered_data = filtered_data[
                    (filtered_data["日期"].dt.year == year)
                    & (filtered_data["日期"].dt.month == month)
                ]
        elif period == "每年":
            year = int(range_text[:-1])
            filtered_data = filtered_data[filtered_data["日期"].dt.year == year]

        if filtered_data.empty:
            self.total_time_label.setText("总专注时间: 0 分钟")
            self.avg_time_label.setText("平均时长: 0 分钟")
            self.sessions_label.setText("学习次数: 0 次")
            return

        total_time = filtered_data["时长(分钟)"].sum()
        avg_time = filtered_data["时长(分钟)"].mean()
        sessions = len(filtered_data)

        self.total_time_label.setText(f"总专注时间: {total_time:.1f} 分钟")
        self.avg_time_label.setText(f"平均时长: {avg_time:.1f} 分钟")
        self.sessions_label.setText(f"学习次数: {sessions} 次")

        self.update_charts(filtered_data, range_text)

    def update_charts(self, data, range_text):
        self.bar_chart.axes.clear()
        category_data = (
            data.groupby("标签")["时长(分钟)"].sum().sort_values(ascending=False)
        )

        if not category_data.empty:
            colors = plt.cm.viridis(np.linspace(0, 1, len(category_data)))
            bars = category_data.plot(
                kind="bar",
                ax=self.bar_chart.axes,
                color=colors,
                edgecolor="white",
                linewidth=1,
            )

            self.bar_chart.axes.set_title(
                f"{range_text} 学习时长分布", pad=20, fontsize=12, fontweight="bold"
            )
            self.bar_chart.axes.set_xlabel("学习标签", labelpad=10, fontsize=10)
            self.bar_chart.axes.set_ylabel("总时长(分钟)", labelpad=10, fontsize=10)

            self.bar_chart.axes.yaxis.grid(True, linestyle="--", alpha=0.7)
            self.bar_chart.axes.set_axisbelow(True)

            plt.xticks(rotation=0, ha="center", fontsize=9)
            plt.yticks(fontsize=9)

            for bar in bars.patches:
                height = bar.get_height()
                self.bar_chart.axes.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 1,
                    f"{height:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                )

        self.bar_chart.fig.tight_layout()
        self.bar_chart.draw()

        # 圆环图绘制部分
        self.ring_chart.axes.clear()
        if not category_data.empty:
            total = category_data.sum()
            threshold = total * 0.03  # 小于3%的类别合并为“其他”
            small_categories = category_data[category_data < threshold]
            large_categories = category_data[category_data >= threshold]

            # 合并小类别为“其他”
            if not small_categories.empty:
                large_categories["其他"] = small_categories.sum()

            # 配色方案
            colors = plt.cm.Set3(np.linspace(0, 1, len(large_categories)))

            # 绘制圆环图（wedgeprops控制圆环宽度）
            wedges, texts, autotexts = self.ring_chart.axes.pie(
                large_categories,
                autopct=lambda p: f"{p:.1f}%\n({p*total/100:.0f}min)",  # 显示百分比和分钟数
                startangle=90,  # 从顶部开始绘制
                pctdistance=0.85,  # 百分比标签位置
                wedgeprops=dict(width=0.3, edgecolor="white"),  # 圆环宽度和边框
                colors=colors,
                labels=large_categories.index.tolist(),  # 显式添加标签名称
            )

            # 美化标签样式
            plt.setp(
                autotexts, size=9, weight="bold", color="darkslategray"
            )  # 百分比标签
            plt.setp(texts, size=10, weight="medium", color="black")  # 类别名称标签

            # 圆环中心白色圆（形成“环形”效果）
            centre_circle = plt.Circle((0, 0), 0.70, fc="white")
            self.ring_chart.fig.gca().add_artist(centre_circle)

            # 中心显示总时长
            self.ring_chart.axes.text(
                0,
                0,
                f"总时长\n{total:.1f}分钟",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

            # 标题
            self.ring_chart.axes.set_title(
                f"{range_text} 学习占比分布", pad=20, fontsize=12, fontweight="bold"
            )
            self.ring_chart.axes.axis("equal")  # 保证圆形比例

        self.ring_chart.fig.tight_layout()
        self.ring_chart.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImprovedFocusTimeManager()
    window.show()
    sys.exit(app.exec())
