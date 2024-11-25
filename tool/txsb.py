from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QLabel, QFileDialog, QScrollArea,
                             QHBoxLayout, QSpinBox, QMessageBox, QProgressBar, QLineEdit, QTextEdit, QListWidget,
                             QDialog, QListWidgetItem, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage
import cv2
import numpy as np
import pyautogui
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple
import logging
import random
import json
from datetime import datetime
import os
import sqlite3
from contextlib import contextmanager


@dataclass
class ImageItem:
    path: str
    threshold: float = 0.8
    min_delay: float = 0.5  # 最小延时
    max_delay: float = 2.0  # 最大延时
    timeout: float = 60.0  # 默认改为60秒


@dataclass
class Task:
    name: str
    description: str
    loop_count: int
    images: List[ImageItem]
    created_time: str = ''

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'loop_count': self.loop_count,
            'created_time': self.created_time,
            'images': [
                {
                    'path': img.path,
                    'threshold': img.threshold,
                    'min_delay': img.min_delay,
                    'max_delay': img.max_delay,
                    'timeout': img.timeout
                } for img in self.images
            ]
        }

    @classmethod
    def from_dict(cls, data):
        images = [
            ImageItem(
                path=img['path'],
                threshold=img['threshold'],
                min_delay=img['min_delay'],
                max_delay=img['max_delay'],
                timeout=img['timeout']
            ) for img in data['images']
        ]
        return cls(
            name=data['name'],
            description=data['description'],
            loop_count=data['loop_count'],
            images=images,
            created_time=data['created_time']
        )


class ImageProcessThread(QThread):
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    image_signal = pyqtSignal(QPixmap)

    def __init__(self, images: List[ImageItem], loop_count: int):
        super().__init__()
        self.images = images
        self.loop_count = loop_count
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            current_loop = 1

            while current_loop <= self.loop_count and self.is_running:
                self.result_signal.emit(f"\n开始执行第 {current_loop}/{self.loop_count} 轮任务")

                for i, img_item in enumerate(self.images):
                    if not self.is_running:
                        break

                    # 计算总体进度
                    total_progress = int(((current_loop - 1) * len(self.images) + i) /
                                         (self.loop_count * len(self.images)) * 100)
                    self.progress_signal.emit(total_progress)

                    # 读取并显示当前处理的图片
                    template = cv2.imread(img_item.path)
                    if template is None:
                        self.result_signal.emit(f"无法读取图像: {img_item.path}")
                        continue

                    # 发送图片信号用于显示
                    pixmap = QPixmap(img_item.path)
                    self.image_signal.emit(pixmap)

                    # 开计时
                    start_time = time.time()
                    found = False

                    # 循检测直到超时
                    while time.time() - start_time < img_item.timeout and not found and self.is_running:
                        # 获取屏幕截图
                        screen = np.array(pyautogui.screenshot())
                        screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

                        # 模板匹配
                        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                        if max_val > img_item.threshold:
                            found = True
                            h, w = template.shape[:2]

                            # 修改随机点击位置的计算方式
                            # 确保点击位置在匹配到的图像区域内
                            click_x = max_loc[0] + random.randint(5, w - 5)  # 留出5像素边距
                            click_y = max_loc[1] + random.randint(5, h - 5)  # 留出5像素边距

                            # 随机延时
                            random_delay = random.uniform(img_item.min_delay, img_item.max_delay)

                            try:
                                # 添加更详细的日志
                                self.result_signal.emit(
                                    f"第 {current_loop}/{self.loop_count} 轮 - "
                                    f"处理第 {i + 1}/{len(self.images)} 张图片:\n"
                                    f"匹配位置: ({max_loc[0]}, {max_loc[1]})\n"
                                    f"图像大小: {w}x{h}\n"
                                    f"随机点击: ({click_x}, {click_y})\n"
                                    f"匹配度: {max_val:.2f}\n"
                                    f"等待时间: {random_delay:.1f}秒\n"
                                    f"识别用时: {time.time() - start_time:.1f}秒"
                                )

                                # 平滑移动到随机位置
                                pyautogui.moveTo(click_x, click_y, duration=0.2)
                                time.sleep(0.1)  # 短暂停顿
                                pyautogui.click()

                            except Exception as e:
                                self.result_signal.emit(f"击失败: {str(e)}")

                            time.sleep(random_delay)
                        else:
                            # 短暂等待后继续检测
                            time.sleep(0.1)

                    if not found:
                        self.result_signal.emit(
                            f"第 {current_loop}/{self.loop_count} 轮 - "
                            f"处理第 {i + 1}/{len(self.images)} 张图片:\n"
                            f"超时未找到匹配图像 (超时时间: {img_item.timeout}秒)\n"
                            f"最佳匹配度: {max_val:.2f}"
                        )

                if self.is_running:
                    current_loop += 1
                    if current_loop <= self.loop_count:
                        self.result_signal.emit(f"\n当前轮次完成，等待3秒后开始下一轮...")
                        time.sleep(3)  # 每轮之间等待3秒

            self.progress_signal.emit(100)
            self.result_signal.emit(f"\n所有循环执行完成，共执行 {current_loop - 1} 轮")
            self.finished_signal.emit()

        except Exception as e:
            self.result_signal.emit(f"处理过程出错: {str(e)}")
            self.finished_signal.emit()


class DatabaseManager:
    def __init__(self):
        self.db_path = 'tasks.db'
        self.init_database()

    def init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 创建任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    loop_count INTEGER,
                    created_time TEXT
                )
            ''')
            # 创建图像表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    path TEXT NOT NULL,
                    threshold REAL,
                    min_delay REAL,
                    max_delay REAL,
                    timeout REAL,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            ''')
            conn.commit()

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def save_task(self, task: Task):
        """保存任务到数据库"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 保存任务信息
            cursor.execute('''
                INSERT INTO tasks (name, description, loop_count, created_time)
                VALUES (?, ?, ?, ?)
            ''', (task.name, task.description, task.loop_count, task.created_time))

            task_id = cursor.lastrowid

            # 保存图像信息
            for img in task.images:
                cursor.execute('''
                    INSERT INTO images (task_id, path, threshold, min_delay, max_delay, timeout)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, img.path, img.threshold, img.min_delay, img.max_delay, img.timeout))

            conn.commit()
            return task_id

    def load_task(self, task_id):
        """从数据库加载任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 获取任务信息
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            task_data = cursor.fetchone()

            if not task_data:
                raise ValueError(f"找不到ID为{task_id}的任务")

            # 获取图像信息
            cursor.execute('SELECT * FROM images WHERE task_id = ?', (task_id,))
            images_data = cursor.fetchall()

            # 构建图像列表
            images = [
                ImageItem(
                    path=img[2],
                    threshold=img[3],
                    min_delay=img[4],
                    max_delay=img[5],
                    timeout=img[6]
                ) for img in images_data
            ]

            # 构建任务对象
            return Task(
                name=task_data[1],
                description=task_data[2],
                loop_count=task_data[3],
                images=images,
                created_time=task_data[4]
            )

    def get_all_tasks(self):
        """获取所有任务的基本信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, created_time FROM tasks ORDER BY created_time DESC')
            return cursor.fetchall()

    def delete_task(self, task_id):
        """删除任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()


# 添加新的日志窗口类
class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('处理日志')
        self.setGeometry(200, 200, 600, 800)

        layout = QVBoxLayout(self)

        # 分割窗口：上方显示当前图片，下方显示日志
        splitter = QVBoxLayout()

        # 当前处理图片显示区域
        image_group = QGroupBox("当前处理图片")
        image_layout = QVBoxLayout()
        self.current_image = QLabel()
        self.current_image.setFixedSize(200, 200)
        self.current_image.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.current_image)
        image_group.setLayout(image_layout)
        splitter.addWidget(image_group)

        # 日志显示区域
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: white; padding: 10px;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)

        layout.addLayout(splitter)

    def updateLog(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def updateImage(self, pixmap):
        self.current_image.setPixmap(
            pixmap.scaled(
                200, 200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )


class ImageProcessor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_items: List[ImageItem] = []
        self.process_thread = None
        self.db = DatabaseManager()
        self.log_window = LogWindow(self)  # 创建日志窗口

        # 配置日志系统
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='image_processor.log',
            filemode='a'
        )
        logging.info("程序启动")

        self.initUI()

    def initUI(self):
        self.setWindowTitle('智能图像识别点击工具')
        self.setGeometry(100, 100, 1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 按钮区域
        button_layout = QHBoxLayout()

        add_button = QPushButton('添加图像', self)
        add_button.clicked.connect(self.addImage)
        button_layout.addWidget(add_button)

        start_button = QPushButton('开始处理', self)
        start_button.clicked.connect(self.startProcessing)
        button_layout.addWidget(start_button)

        stop_button = QPushButton('停止', self)
        stop_button.clicked.connect(self.stopProcessing)
        button_layout.addWidget(stop_button)

        clear_button = QPushButton('清空列表', self)
        clear_button.clicked.connect(self.clearImages)
        button_layout.addWidget(clear_button)

        layout.addLayout(button_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # 图像显示区域
        scroll = QScrollArea()
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        scroll.setWidget(self.image_container)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        # 添加任务控制区域
        task_control_layout = QHBoxLayout()

        # 任务名称
        self.task_name_input = QLineEdit()
        self.task_name_input.setPlaceholderText("任务名称")
        task_control_layout.addWidget(self.task_name_input)

        # 循环次数
        task_control_layout.addWidget(QLabel("循环次数:"))
        self.loop_count_spin = QSpinBox()
        self.loop_count_spin.setRange(1, 999999)
        self.loop_count_spin.setValue(1)
        task_control_layout.addWidget(self.loop_count_spin)

        # 任务说明
        self.task_description = QTextEdit()
        self.task_description.setPlaceholderText("任务说明")
        self.task_description.setMaximumHeight(60)

        # 保存和加载任务按钮
        save_task_button = QPushButton("保存任务")
        save_task_button.clicked.connect(self.saveTask)
        task_control_layout.addWidget(save_task_button)

        load_task_button = QPushButton("加载任务")
        load_task_button.clicked.connect(self.loadTask)
        task_control_layout.addWidget(load_task_button)

        # 在任务控制区域添加任务列表按钮
        task_list_button = QPushButton("任务列表")
        task_list_button.clicked.connect(self.showTaskList)
        task_control_layout.addWidget(task_list_button)

        layout.insertLayout(1, task_control_layout)
        layout.insertWidget(2, self.task_description)

    def addImage(self):
        try:
            file_names, _ = QFileDialog.getOpenFileNames(
                self,
                "选择图像",
                "",
                "图像文件 (*.png *.jpg *.jpeg *.bmp)"
            )

            for file_name in file_names:
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)

                # 图像预览
                label = QLabel()
                pixmap = QPixmap(file_name)
                label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
                item_layout.addWidget(label)

                # 图像信息和控制
                info_layout = QVBoxLayout()

                path_label = QLabel(f"路径: {file_name}")
                info_layout.addWidget(path_label)

                # 匹配阈值控制
                threshold_layout = QHBoxLayout()
                threshold_layout.addWidget(QLabel("匹配阈值:"))
                threshold_spin = QSpinBox()
                threshold_spin.setRange(1, 100)
                threshold_spin.setValue(80)
                threshold_layout.addWidget(threshold_spin)
                info_layout.addLayout(threshold_layout)

                # 修改延时控制为最小最大延时
                delay_layout = QHBoxLayout()
                delay_layout.addWidget(QLabel("延时范围(秒):"))
                min_delay_spin = QSpinBox()
                min_delay_spin.setRange(0, 10)
                min_delay_spin.setValue(1)
                max_delay_spin = QSpinBox()
                max_delay_spin.setRange(0, 10)
                max_delay_spin.setValue(2)
                delay_layout.addWidget(min_delay_spin)
                delay_layout.addWidget(QLabel("-"))
                delay_layout.addWidget(max_delay_spin)
                info_layout.addLayout(delay_layout)

                # 添加超时设置
                timeout_layout = QHBoxLayout()
                timeout_layout.addWidget(QLabel("超时时间(秒):"))
                timeout_spin = QSpinBox()
                timeout_spin.setRange(1, 3600)  # 范围改为1秒到1小时
                timeout_spin.setValue(60)  # 默认改为60秒
                timeout_spin.setSingleStep(10)  # 步进值设为10秒
                timeout_layout.addWidget(timeout_spin)
                info_layout.addLayout(timeout_layout)

                item_layout.addLayout(info_layout)

                # 删除按钮
                delete_button = QPushButton("删除")
                delete_button.clicked.connect(
                    lambda checked, w=item_widget: self.deleteImage(w)
                )
                item_layout.addWidget(delete_button)

                self.image_layout.addWidget(item_widget)

                # 创建ImageItem对象
                image_item = ImageItem(
                    path=file_name,
                    threshold=threshold_spin.value() / 100,
                    min_delay=min_delay_spin.value(),
                    max_delay=max_delay_spin.value(),
                    timeout=float(timeout_spin.value())
                )
                self.image_items.append(image_item)

                # 修改信号连接部分
                index = len(self.image_items) - 1
                timeout_spin.valueChanged.connect(self.create_timeout_handler(index))
                threshold_spin.valueChanged.connect(self.create_threshold_handler(index))
                min_delay_spin.valueChanged.connect(self.create_min_delay_handler(index))
                max_delay_spin.valueChanged.connect(self.create_max_delay_handler(index))

        except Exception as e:
            QMessageBox.warning(self, "错误", f"添加图像失败: {str(e)}")
            logging.error(f"添加图像失败: {str(e)}")

    def deleteImage(self, widget):
        index = self.findWidgetIndex(widget)
        if index >= 0:
            self.image_items.pop(index)
            widget.deleteLater()

    def findWidgetIndex(self, widget):
        for i in range(self.image_layout.count()):
            if self.image_layout.itemAt(i).widget() == widget:
                return i
        return -1

    def clearImages(self):
        self.image_items.clear()
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def startProcessing(self):
        if not self.image_items:
            QMessageBox.warning(self, "警告", "请先添加图像")
            return

        if self.process_thread and self.process_thread.isRunning():
            QMessageBox.warning(self, "警告", "处理已在进行中")
            return

        self.log_window.log_text.clear()
        self.log_window.show()  # 显示日志窗口

        self.process_thread = ImageProcessThread(
            self.image_items,
            self.loop_count_spin.value()
        )
        self.process_thread.progress_signal.connect(self.updateProgress)
        self.process_thread.result_signal.connect(self.updateLog)
        self.process_thread.finished_signal.connect(self.processingFinished)
        self.process_thread.image_signal.connect(self.updateCurrentImage)
        self.process_thread.start()

    def stopProcessing(self):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait()
            self.updateLog("处理已停止")

    def updateProgress(self, value):
        self.progress_bar.setValue(value)

    def updateLog(self, message):
        self.log_window.updateLog(message)
        logging.info(message)

    def processingFinished(self):
        self.updateLog("处理完成")

    def closeEvent(self, event):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait()
        event.accept()

    def updateCurrentImage(self, pixmap):
        self.log_window.updateImage(pixmap)

    # 加新的更新方法
    def updateTimeout(self, index, value):
        if 0 <= index < len(self.image_items):
            self.image_items[index].timeout = value
            logging.info(f"更新图像 {index + 1} 的超时时间为: {value}秒")

    def updateThreshold(self, index, value):
        if 0 <= index < len(self.image_items):
            self.image_items[index].threshold = value
            logging.info(f"更新图像 {index + 1} 的匹配阈值为: {value}")

    def updateMinDelay(self, index, value):
        if 0 <= index < len(self.image_items):
            self.image_items[index].min_delay = value
            logging.info(f"更新图像 {index + 1} 的最小延时为: {value}秒")

    def updateMaxDelay(self, index, value):
        if 0 <= index < len(self.image_items):
            self.image_items[index].max_delay = value
            logging.info(f"更新图像 {index + 1} 的最大延时为: {value}秒")

    def saveTask(self):
        """保存任务到数据库"""
        if not self.image_items:
            QMessageBox.warning(self, "警告", "请先添加图像")
            return

        name = self.task_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入任务名称")
            return

        try:
            task = Task(
                name=name,
                description=self.task_description.toPlainText().strip(),
                loop_count=self.loop_count_spin.value(),
                images=self.image_items,
                created_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            task_id = self.db.save_task(task)
            QMessageBox.information(self, "成功", f"任务已保存，ID: {task_id}")
            logging.info(f"任务已保存到数据库，ID: {task_id}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存任务失败: {str(e)}")
            logging.error(f"保存任务失败: {str(e)}")

    def loadTask(self):
        """从数据库加载任务"""
        try:
            # 获取所有任务
            tasks = self.db.get_all_tasks()
            if not tasks:
                QMessageBox.information(self, "提示", "暂无保存的任务")
                return

            # 创建任务选择对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("选择任务")
            layout = QVBoxLayout(dialog)

            task_list = QListWidget()
            for task_id, name, created_time in tasks:
                task_list.addItem(f"{name} (创建时间: {created_time})")
                task_list.item(task_list.count() - 1).setData(Qt.UserRole, task_id)

            layout.addWidget(task_list)

            buttons = QHBoxLayout()
            load_button = QPushButton("加载")
            cancel_button = QPushButton("取消")
            buttons.addWidget(load_button)
            buttons.addWidget(cancel_button)
            layout.addLayout(buttons)

            load_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            if dialog.exec_() == QDialog.Accepted and task_list.currentItem():
                task_id = task_list.currentItem().data(Qt.UserRole)
                task = self.db.load_task(task_id)

                # 清空当前任务
                self.clearImages()

                # 加载任务信息
                self.task_name_input.setText(task.name)
                self.task_description.setText(task.description)
                self.loop_count_spin.setValue(task.loop_count)

                # 加载图像列表
                for img_item in task.images:
                    self.addImageFromTask(img_item)

                QMessageBox.information(self, "成功", "任务加载完成")
                logging.info(f"任务已从数据库加载，ID: {task_id}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载任务失败: {str(e)}")
            logging.error(f"加载任务失败: {str(e)}")

    def addImageFromTask(self, img_item: ImageItem):
        """从任务中添加图像项"""
        try:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)

            # 图像预览
            label = QLabel()
            pixmap = QPixmap(img_item.path)
            label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
            item_layout.addWidget(label)

            # 图像信息和控制
            info_layout = QVBoxLayout()

            path_label = QLabel(f"路径: {img_item.path}")
            info_layout.addWidget(path_label)

            # 匹配阈值控制
            threshold_layout = QHBoxLayout()
            threshold_layout.addWidget(QLabel("匹配阈值:"))
            threshold_spin = QSpinBox()
            threshold_spin.setRange(1, 100)
            threshold_spin.setValue(int(img_item.threshold * 100))
            threshold_layout.addWidget(threshold_spin)
            info_layout.addLayout(threshold_layout)

            # 延时范围控制
            delay_layout = QHBoxLayout()
            delay_layout.addWidget(QLabel("延时范围(秒):"))
            min_delay_spin = QSpinBox()
            min_delay_spin.setRange(0, 10)
            min_delay_spin.setValue(int(img_item.min_delay))
            max_delay_spin = QSpinBox()
            max_delay_spin.setRange(0, 10)
            max_delay_spin.setValue(int(img_item.max_delay))
            delay_layout.addWidget(min_delay_spin)
            delay_layout.addWidget(QLabel("-"))
            delay_layout.addWidget(max_delay_spin)
            info_layout.addLayout(delay_layout)

            # 超时设置
            timeout_layout = QHBoxLayout()
            timeout_layout.addWidget(QLabel("超时时间(秒):"))
            timeout_spin = QSpinBox()
            timeout_spin.setRange(1, 3600)
            timeout_spin.setValue(int(img_item.timeout))
            timeout_spin.setSingleStep(10)
            timeout_layout.addWidget(timeout_spin)
            info_layout.addLayout(timeout_layout)

            item_layout.addLayout(info_layout)

            # 删除按钮
            delete_button = QPushButton("删除")
            delete_button.clicked.connect(
                lambda checked, w=item_widget: self.deleteImage(w)
            )
            item_layout.addWidget(delete_button)

            self.image_layout.addWidget(item_widget)
            self.image_items.append(img_item)

            # 修改信号连接部分
            index = len(self.image_items) - 1
            timeout_spin.valueChanged.connect(self.create_timeout_handler(index))
            threshold_spin.valueChanged.connect(self.create_threshold_handler(index))
            min_delay_spin.valueChanged.connect(self.create_min_delay_handler(index))
            max_delay_spin.valueChanged.connect(self.create_max_delay_handler(index))

        except Exception as e:
            logging.error(f"从任务添加图像失败: {str(e)}")
            raise

    def showTaskList(self):
        """显示任务列表对话框"""
        try:
            # 获取所有任务
            tasks = self.db.get_all_tasks()
            if not tasks:
                QMessageBox.information(self, "提示", "暂无保存的任务")
                return

            # 创建任务列表对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("任务列表")
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 创建任务列表
            task_list = QListWidget()
            for task_id, name, created_time in tasks:
                item = QListWidgetItem(name)  # 只显示任务名称
                item.setData(Qt.UserRole, task_id)
                task_list.addItem(item)
            layout.addWidget(task_list)

            # 创建按钮布局
            button_layout = QHBoxLayout()

            # 加载按钮
            load_button = QPushButton("加载")
            load_button.clicked.connect(lambda: self.loadTaskFromList(task_list, dialog))
            button_layout.addWidget(load_button)

            # 修改按钮
            edit_button = QPushButton("修改")
            edit_button.clicked.connect(lambda: self.editTask(task_list))
            button_layout.addWidget(edit_button)

            # 删除按钮
            delete_button = QPushButton("删除")
            delete_button.clicked.connect(lambda: self.deleteTaskFromList(task_list))
            button_layout.addWidget(delete_button)

            # 关闭按钮
            close_button = QPushButton("关闭")
            close_button.clicked.connect(dialog.close)
            button_layout.addWidget(close_button)

            layout.addLayout(button_layout)
            dialog.exec_()

        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示任务列表失败: {str(e)}")
            logging.error(f"显示任务列表失败: {str(e)}")

    def loadTaskFromList(self, task_list: QListWidget, dialog: QDialog):
        """从列表加载选中的任务"""
        if not task_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择任务")
            return

        try:
            task_id = task_list.currentItem().data(Qt.UserRole)
            task = self.db.load_task(task_id)

            # 清空当前任务
            self.clearImages()

            # 加载任务信息
            self.task_name_input.setText(task.name)
            self.task_description.setText(task.description)
            self.loop_count_spin.setValue(task.loop_count)

            # 加载图像列表
            for img_item in task.images:
                self.addImageFromTask(img_item)

            dialog.close()
            QMessageBox.information(self, "成功", "任务加载完成")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载任务失败: {str(e)}")
            logging.error(f"加载任务失败: {str(e)}")

    def editTask(self, task_list: QListWidget):
        """修改选中的任务"""
        if not task_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择任务")
            return

        try:
            task_id = task_list.currentItem().data(Qt.UserRole)
            task = self.db.load_task(task_id)

            # 加载任务到主界面
            self.clearImages()
            self.task_name_input.setText(task.name)
            self.task_description.setText(task.description)
            self.loop_count_spin.setValue(task.loop_count)

            for img_item in task.images:
                self.addImageFromTask(img_item)

            QMessageBox.information(self, "提示", "请修改任务后点击保存按钮保存更改")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"修改任务失败: {str(e)}")
            logging.error(f"修改任务失败: {str(e)}")

    def deleteTaskFromList(self, task_list: QListWidget):
        """删除选中的任务"""
        if not task_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择任务")
            return

        try:
            task_id = task_list.currentItem().data(Qt.UserRole)

            reply = QMessageBox.question(
                self,
                "确认删除",
                "确定要删除选中的任务吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.db.delete_task(task_id)
                task_list.takeItem(task_list.currentRow())
                QMessageBox.information(self, "成功", "任务已删除")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"删除任务失败: {str(e)}")
            logging.error(f"删除任务失败: {str(e)}")

    def create_timeout_handler(self, index):
        return lambda value: self.updateTimeout(index, float(value))

    def create_threshold_handler(self, index):
        return lambda value: self.updateThreshold(index, value / 100)

    def create_min_delay_handler(self, index):
        return lambda value: self.updateMinDelay(index, float(value))

    def create_max_delay_handler(self, index):
        return lambda value: self.updateMaxDelay(index, float(value))


if __name__ == '__main__':
    # 设置pyautogui的安全性
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1

    app = QApplication(sys.argv)
    window = ImageProcessor()
    window.show()
    sys.exit(app.exec_())