import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QMenu, QDialog, QLabel, QTextEdit,
                             QScrollArea, QColorDialog, QMessageBox, QSplitter, QFileDialog, QProgressBar, QInputDialog,
                             QStackedWidget, QFrame)
from PyQt6.QtCore import Qt, QPoint, QTimer, QEvent, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QAction, QFont
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
import re
from datetime import datetime
import sqlite3
from pathlib import Path


class MarkableLabel(QLabel):
    """可以手写标记的标签"""

    def __init__(self):
        super().__init__()
        self.drawing = False
        self.last_point = None
        self.marks = []
        self.current_color = QColor(Qt.GlobalColor.red)
        self.current_width = 2
        self.setMouseTracking(False)
        self.page_marks = {}  # 存储所有页面的标记
        self.current_page_key = None
        self.page_labels = {}  # 存储���页面的标签

        # 添加以下代码，使标签可以接收键盘焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 添加以下代码，设置滚动步长
        self.scroll_step = 50  # 每次滚动的像素值

        # 添加触摸和鼠标滑动相关的属性
        self.last_x = None
        self.is_dragging = False
        self.drag_threshold = 180  # 滑动触发阈值
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)  # 启用触摸事件
        self.page_turned = False  # 添加标志，防止连续翻页

        # 添加标签相关属性
        self.text_labels = []  # 存储标签列表
        self.adding_label = False  # 是否正在添加标签
        self.label_text = ""  # 当前标签文本
        self.label_color = QColor(Qt.GlobalColor.blue)  # 标签颜色
        self.label_font_size = 12  # 标签字体大小

        # 在 MarkableLabel 类的 __init__ 中添加历史记录列表
        self.marks_history = []  # 标记历史
        self.labels_history = []  # 标签历史

    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        main_window = self.get_main_window()
        if event.button() == Qt.MouseButton.LeftButton:
            if main_window and main_window.marking_enabled:
                # 保存当前标记状态��历史
                self.save_marks_history()
                self.drawing = True
                self.last_point = event.pos()
            elif main_window and main_window.labeling_enabled:  # 添加标签模式
                pos = event.pos()
                # 将标签添加到当前页面
                if self.current_page_key:
                    if self.current_page_key not in self.page_labels:
                        self.page_labels[self.current_page_key] = []

                    # 添加新标签
                    new_label = {
                        'text': self.label_text,
                        'pos': pos,
                        'color': QColor(self.label_color),
                        'font_size': self.label_font_size
                    }
                    self.page_labels[self.current_page_key].append(new_label)
                    self.update()

                    # 直接将新标签添加到数据库
                    if main_window:
                        book_id = main_window.books[main_window.current_book_path]['id']
                        main_window.cursor.execute(
                            'INSERT INTO labels (book_id, page, text, pos_x, pos_y, color, font_size) VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (book_id, main_window.current_page,
                             new_label['text'],
                             new_label['pos'].x(), new_label['pos'].y(),
                             new_label['color'].name(),
                             new_label['font_size'])
                        )
                        main_window.conn.commit()
                        main_window.update_label_tree_item(self.current_page_key)  # 只更新当前页面的标签树
            else:
                self.is_dragging = True
                self.last_x = event.pos().x()
                self.page_turned = False

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drawing:
                self.drawing = False
                self.save_current_marks()
            self.is_dragging = False
            self.last_x = None
            self.page_turned = False  # 重置翻页标志

    def mouseMoveEvent(self, event):
        """处理鼠标移事件"""
        main_window = self.get_main_window()
        if not main_window:
            return

        if self.drawing and main_window.marking_enabled:
            current_point = event.pos()
            mark = {
                'start': QPoint(self.last_point.x(), self.last_point.y()),
                'end': QPoint(current_point.x(), current_point.y()),
                'color': QColor(self.current_color.name()),
                'width': self.current_width
            }
            self.marks.append(mark)
            self.last_point = current_point
            self.update()
        elif self.is_dragging and self.last_x is not None and not self.page_turned:
            # 处理滑动翻页
            delta_x = event.pos().x() - self.last_x
            if abs(delta_x) > self.drag_threshold:
                if delta_x > 0:  # 向右滑动
                    main_window.prev_page()
                else:  # 向左滑动
                    main_window.next_page()
                self.page_turned = True  # 设置翻页标志
                self.last_x = event.pos().x()

    def event(self, event):
        """处理触摸事件"""
        if event.type() == QEvent.Type.TouchBegin:
            # 记录触摸开始点
            points = event.points()
            if points:
                self.last_x = points[0].position().x()
                self.page_turned = False  # 重翻页标志
            return True

        elif event.type() == QEvent.Type.TouchUpdate:
            points = event.points()
            if len(points) == 2 and not self.page_turned:  # 双指触控且未翻��������
                touch_point = points[0]
                if self.last_x is not None:
                    delta_x = touch_point.position().x() - self.last_x
                    if abs(delta_x) > self.drag_threshold:
                        main_window = self.get_main_window()
                        if main_window:
                            if delta_x > 0:  # 向右滑动
                                main_window.prev_page()
                            else:  # 向左滑动
                                main_window.next_page()
                            self.page_turned = True  # 设置翻页标志
                            self.last_x = touch_point.position().x()
            return True

        elif event.type() == QEvent.Type.TouchEnd:
            self.last_x = None
            self.page_turned = False  # 重置翻页标志
            return True

        return super().event(event)

    def paintEvent(self, event):
        """重写绘制事件"""
        super().paintEvent(event)
        painter = QPainter(self)

        # 绘制标记
        for mark in self.marks:
            pen = QPen(mark['color'], mark['width'])
            painter.setPen(pen)
            painter.drawLine(mark['start'], mark['end'])

        # 绘�����������������������前页面的文本标签
        if self.current_page_key and self.current_page_key in self.page_labels:
            for label in self.page_labels[self.current_page_key]:
                # 检查是否是高亮标签
                is_highlight = (hasattr(self, 'highlight_label') and
                                self.highlight_label and
                                self.highlight_label['text'] == label['text'] and
                                self.highlight_label['pos'] == label['pos'])

                # 设置字体
                font = painter.font()
                font.setPointSize(label['font_size'])
                painter.setFont(font)

                # 计算文本宽度和换行
                text = label['text']
                fm = painter.fontMetrics()
                max_width = 120  # 将最大宽度从65改为120

                # 如果文本宽度超过最大宽度，需要换行
                if fm.horizontalAdvance(text) > max_width:
                    # 计算每行大约能容纳的字符数
                    chars_per_line = max(1, int(max_width / (fm.averageCharWidth() * 1.1)))
                    # 分割文本
                    lines = []
                    for i in range(0, len(text), chars_per_line):
                        lines.append(text[i:i + chars_per_line])
                else:
                    lines = [text]

                # 绘制背景（如果是高亮状态）
                if is_highlight:
                    max_line_width = max(fm.horizontalAdvance(line) for line in lines)
                    bg_height = fm.height() * len(lines) + 4  # 添加一些内边距
                    painter.fillRect(
                        QRect(label['pos'].x() - 2,
                              label['pos'].y() - fm.ascent() - 2,
                              max_line_width + 4,
                              bg_height),
                        QColor(255, 255, 0, 100)  # 半透明黄色背景
                    )

                # 绘制文本
                painter.setPen(QPen(label['color']))
                y = label['pos'].y()
                for line in lines:
                    painter.drawText(label['pos'].x(), y, line)
                    y += fm.height()  # 移动到下一行

    def clear_marks(self):
        """清除所有标记"""
        self.marks = []
        if self.current_page_key and self.current_page_key in self.page_marks:
            del self.page_marks[self.current_page_key]
        self.update()

    def set_current_page(self, page_key):
        """设置当前页面，加载对应的标记和标签"""
        self.current_page_key = page_key
        self.marks = []

        # 加载标记
        if page_key in self.page_marks:
            self.marks = self.page_marks[page_key].copy()

        # 确保当前页面的标签列表存在
        if page_key not in self.page_labels:
            self.page_labels[page_key] = []

        self.update()

    def save_current_marks(self):
        """保存当前页面的标记"""
        if self.current_page_key and self.marks:
            saved_marks = []
            for mark in self.marks:
                saved_marks.append({
                    'start': QPoint(mark['start'].x(), mark['start'].y()),
                    'end': QPoint(mark['end'].x(), mark['end'].y()),
                    'color': QColor(mark['color'].name()),
                    'width': mark['width']
                })
            self.page_marks[self.current_page_key] = saved_marks

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent:
            if isinstance(parent, EbookManager):
                return parent
            parent = parent.parent()
        return None

    def get_scroll_area(self):
        """获取父滚动区域"""
        parent = self.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parent()
        return None

    def keyPressEvent(self, event):
        """处理键盘事件"""
        try:
            scroll_area = self.get_scroll_area()
            if scroll_area:
                if event.key() == Qt.Key.Key_Up:  # 上方向键
                    # 获取当前垂直滚动的值
                    current = scroll_area.verticalScrollBar().value()
                    # 向上��动
                    scroll_area.verticalScrollBar().setValue(current - self.scroll_step)
                    event.accept()
                elif event.key() == Qt.Key.Key_Down:  # 下方向键
                    # 获取当前垂直滚动条的值
                    current = scroll_area.verticalScrollBar().value()
                    # 向下滚动
                    scroll_area.verticalScrollBar().setValue(current + self.scroll_step)
                    event.accept()
                elif event.key() == Qt.Key.Key_Left:  # 左方向键
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.prev_page()
                    event.accept()
                elif event.key() == Qt.Key.Key_Right:  # 右方向键
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.next_page()
                    event.accept()
            else:
                event.ignore()
        except Exception as e:
            print(f"处理键盘事件时出错: {e}")
            event.ignore()

    def clear_labels(self):
        """清除当前页面的标签"""
        if self.current_page_key:
            if self.current_page_key in self.page_labels:
                del self.page_labels[self.current_page_key]
            self.update()

    def save_marks_history(self):
        """保存当前标记到历史"""
        if self.marks:
            self.marks_history.append(self.marks.copy())

    def save_labels_history(self):
        """保存当前标签到历史"""
        if self.current_page_key and self.current_page_key in self.page_labels:
            self.labels_history.append({
                'page_key': self.current_page_key,
                'labels': self.page_labels[self.current_page_key].copy()
            })


class EbookManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.epub', '.pdf', '.txt', '.mobi', '.azw', '.azw3']
        self.books = {}  # 存储书籍信息
        self.notes = {}  # 存储笔记信息
        self.current_doc = None  # 当前打开的文档
        self.current_page = 0  # 当前�����码
        self.current_book_path = None  # 开的书路
        self.page_marks = {}  # 存储每页的标记
        self.zoom_factor = 1.0  # 缩放因子
        self.min_zoom = 0.1  # 最小缩放
        self.max_zoom = 5.0  # 最大缩放
        self.booklist_visible = True  # 书籍列表示态
        self.init_ui()
        self.init_database()

        # 创建异步检测定时器
        self.init_check_timer = QTimer()
        self.init_check_timer.setSingleShot(True)  # 设置为单次触发
        self.init_check_timer.timeout.connect(self.initial_file_check)

        # 加载数据并启动检测
        self.load_library()
        self.load_notes()
        self.load_marks()
        self.load_zoom_states()
        self.marking_enabled = False  # 标记状态
        self.zoom_states = {}  # 存储书的缩放状态
        self.load_zoom_states()  # 加载缩放状态

        # 启动初始检测（延迟1秒执行，让界面先加载完成）
        self.init_check_timer.start(1000)

        # 添加自动保存定时器
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_drawings)

        # 标���������
        self.labeling_enabled = False  # 添��������������������������������

    def initial_file_check(self):
        """系统动检查文件是否存在"""
        try:
            deleted_paths = []
            total_books = len(self.books)
            checked_count = 0

            # 创建进度对话框
            progress = QDialog(self)
            progress.setWindowTitle("检查文件")
            progress.setFixedSize(300, 100)
            layout = QVBoxLayout(progress)

            # 添加进度标签
            status_label = QLabel("正在检查��件完整性...", progress)
            layout.addWidget(status_label)

            # 添加进度条
            progress_bar = QProgressBar(progress)
            progress_bar.setMaximum(total_books)
            layout.addWidget(progress_bar)

            # 显示对话框（非模态）
            progress.setModal(False)
            progress.show()

            # 检查所有书籍文件是否存在
            for path in list(self.books.keys()):
                if not os.path.exists(path):
                    print(f"文件不存在，将删除相关数据: {path}")
                    deleted_paths.append(path)

                # 更新进度
                checked_count += 1
                progress_bar.setValue(checked_count)
                status_label.setText(f"正在检查文件完整性... ({checked_count}/{total_books})")
                QApplication.processEvents()  # 让界面保持响应

            # 如果文件不存在，删除相关数据
            if deleted_paths:
                for path in deleted_paths:
                    try:
                        # 从数据库中删除书籍（级联删除会自动删除相关数据）
                        self.cursor.execute('DELETE FROM books WHERE path = ?', (path,))

                        # 从内存中删除
                        del self.books[path]
                        if path in self.notes:
                            del self.notes[path]
                        for key in list(self.page_marks.keys()):
                            if key.startswith(path):
                                del self.page_marks[key]
                        if path in self.zoom_states:
                            del self.zoom_states[path]

                    except Exception as e:
                        print(f"删除不存在文件的数据时出错: {e}")

                # 提交事务
                self.conn.commit()

                # 更新界
                self.update_book_tree()
                self.update_notes_list()

                # 显示结果
                QMessageBox.warning(self, "文件检查结果",
                                    f"检测到 {len(deleted_paths)} 个件������存在，相关数据已处理。")

            # 关闭进度对话框
            progress.close()

            print(f"初始文件检查完成，删除了 {len(deleted_paths)} 个不存在文件的数据")

        except Exception as e:
            print(f"初始文件检查时出错: {e}")

    def init_ui(self):
        # 修改窗口初始状态
        self.setWindowTitle('晓阅')
        self.setGeometry(100, 100, 1500, 800)

        # 定义按钮样式
        button_style = """
            QPushButton {
                padding: 4px 8px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background: white;
                min-width: 50px;
                max-width: 80px;
                margin: 0px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        """

        # 修改布局为三段式
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 创建单个分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        # 左侧书籍列表面板
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)

        # 搜索框
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索书籍...')
        self.search_input.textChanged.connect(self.search_books)
        search_layout.addWidget(self.search_input)

        # 导入按钮
        import_btn = QPushButton('导入书籍')
        import_btn.setStyleSheet("font-size: 14px;")  # 置字体大小为 20px
        import_btn.clicked.connect(self.import_books)
        search_layout.addWidget(import_btn)

        left_layout.addLayout(search_layout)

        # 书籍列表
        self.book_tree = QTreeWidget()
        self.book_tree.setStyleSheet("QTreeWidget { font-size: 10px; }")  # 设置字体大小
        self.book_tree.setHeaderLabels(['书籍'])
        self.book_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.book_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.book_tree.customContextMenuRequested.connect(self.show_book_menu)
        left_layout.addWidget(self.book_tree)

        # 中间阅读区域
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        # 首先创建所有按钮
        # 导航按钮
        self.toggle_booklist_btn = QPushButton('隐���书列')
        self.prev_btn = QPushButton('上一页')
        self.next_btn = QPushButton('下一页')
        self.current_page_label = QLabel('0/0')
        self.current_page_label.setStyleSheet("font-size: 14px; font-weight: normal;")
        self.current_page_label.setFixedWidth(50)
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(50)
        self.page_input.setPlaceholderText('页码')
        self.goto_btn = QPushButton('跳转')
        self.zoom_label = QLabel('100%')
        self.zoom_label.setStyleSheet("font-size: 14px; font-weight: normal;")
        self.zoom_label.setFixedWidth(50)
        self.zoom_in_btn = QPushButton('放大')
        self.zoom_out_btn = QPushButton('缩小')

        # 标记按钮
        self.add_note_btn = QPushButton('添加笔记')
        self.color_btn = QPushButton('标记颜色')
        self.undo_marks_btn = QPushButton('撤销标记')
        self.save_button = QPushButton('保存标记')

        # 标签按钮
        self.add_label_btn = QPushButton('添加标签')
        self.label_color_btn = QPushButton('标签颜色')
        self.undo_labels_btn = QPushButton('撤销标签')
        self.toggle_labels_btn = QPushButton('显示标签')

        # 连接按钮信号
        self.toggle_booklist_btn.clicked.connect(self.toggle_booklist)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.goto_btn.clicked.connect(self.goto_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.add_note_btn.clicked.connect(self.add_note)
        self.color_btn.clicked.connect(self.choose_color)
        self.undo_marks_btn.clicked.connect(self.undo_mark)
        self.save_button.clicked.connect(self.save_drawings)
        self.add_label_btn.clicked.connect(self.toggle_label_mode)
        self.label_color_btn.clicked.connect(self.choose_label_color)
        self.undo_labels_btn.clicked.connect(self.undo_label)
        self.toggle_labels_btn.clicked.connect(self.toggle_labels_panel)

        # 创建单行工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(1)
        toolbar.setContentsMargins(0, 0, 0, 0)

        # 导航按钮组
        nav_buttons = [
            self.toggle_booklist_btn,
            self.prev_btn,
            self.next_btn,
            self.current_page_label,
            self.page_input,
            self.goto_btn,
            self.zoom_out_btn,
            self.zoom_label,
            self.zoom_in_btn
        ]

        # 添加���航按钮
        for button in nav_buttons:
            if isinstance(button, QPushButton):
                button.setStyleSheet(button_style)
            toolbar.addWidget(button)

        # 添加分隔符
        toolbar.addSpacing(20)  # 添加一些间距

        # 创建功能按钮组
        # 标签功能下拉菜单
        label_menu = QMenu(self)
        label_menu.addAction("添加标签", self.toggle_label_mode)
        label_menu.addAction("标签颜色", self.choose_label_color)
        label_menu.addAction("撤销标签", self.undo_label)
        label_menu.addAction("清除标签", self.clear_current_labels)  # 添加清除标签选项
        label_menu.addAction("显示/隐藏标签列表", self.toggle_labels_panel)

        label_btn = QPushButton("标签功能")
        label_btn.setStyleSheet(button_style)
        label_btn.setMenu(label_menu)
        toolbar.addWidget(label_btn)

        # 笔记功能下拉菜单
        note_menu = QMenu(self)
        note_menu.addAction("添加笔记", self.add_note)
        note_menu.addAction("显示/隐藏笔记列表", self.toggle_notes_panel)

        note_btn = QPushButton("笔记功能")
        note_btn.setStyleSheet(button_style)
        note_btn.setMenu(note_menu)
        toolbar.addWidget(note_btn)

        # 手写标记功能下拉菜单
        mark_menu = QMenu(self)
        mark_menu.addAction("开始标记", lambda: self.choose_color())
        mark_menu.addAction("撤销标记", self.undo_mark)
        mark_menu.addAction("清除标记", self.clear_current_marks)  # 添加清除标记选项
        mark_menu.addAction("保存标记", self.save_drawings)

        mark_btn = QPushButton("手写标记")
        mark_btn.setStyleSheet(button_style)
        mark_btn.setMenu(mark_menu)
        toolbar.addWidget(mark_btn)

        # 将工具栏添加到中心布局
        center_layout.addLayout(toolbar)

        # 可标记的阅读区域
        scroll_area = QScrollArea()
        self.content_display = MarkableLabel()
        self.content_display.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_display.setFocus()  # 设置初始焦点
        scroll_area.setWidget(self.content_display)
        scroll_area.setWidgetResizable(True)
        center_layout.addWidget(scroll_area)

        # 右侧标签列表面板
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)

        # 创建标签页和笔记页的堆叠窗口
        self.stacked_widget = QStackedWidget()
        right_layout.addWidget(self.stacked_widget)

        # 标签页
        labels_page = QWidget()
        labels_layout = QVBoxLayout(labels_page)

        # 标签搜索框
        self.label_search_input = QLineEdit()
        self.label_search_input.setPlaceholderText('搜索标签...')
        self.label_search_input.setStyleSheet("font-size: 14px;")
        self.label_search_input.textChanged.connect(self.search_labels)
        labels_layout.addWidget(self.label_search_input)

        # 标签树形列表
        self.label_tree = QTreeWidget()
        self.label_tree.setHeaderLabels(['标签'])
        self.label_tree.itemDoubleClicked.connect(self.goto_label)
        self.label_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.label_tree.customContextMenuRequested.connect(self.show_label_menu)
        labels_layout.addWidget(self.label_tree)

        # 笔记页
        notes_page = QWidget()
        notes_layout = QVBoxLayout(notes_page)

        # 笔记列表
        self.notes_list = QTreeWidget()
        self.notes_list.setHeaderLabels(['笔记'])
        self.notes_list.itemDoubleClicked.connect(self.view_note)
        notes_layout.addWidget(self.notes_list)

        # 将页面添加到堆叠窗口
        self.stacked_widget.addWidget(labels_page)
        self.stacked_widget.addWidget(notes_page)

        # 修改 toggle_notes_panel 方法
        self.toggle_notes_btn = QPushButton('显示笔记')
        self.toggle_notes_btn.clicked.connect(self.toggle_notes_panel)
        self.toggle_notes_btn.setStyleSheet(button_style)

        # 添加到分割器
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(center_panel)
        self.main_splitter.addWidget(self.right_panel)

        # 设置分割器比例
        self.main_splitter.setStretchFactor(0, 2)  # 书籍列表
        self.main_splitter.setStretchFactor(1, 4)  # 阅读区域
        self.main_splitter.setStretchFactor(2, 2)  # 标签列表

        # 设置最小宽度
        self.left_panel.setMinimumWidth(300)  # 增加书籍列表最小宽度
        self.right_panel.setMinimumWidth(300)  # 增加标签列表最小度

        # 默认隐标签列表
        self.right_panel.hide()
        self.toggle_labels_btn.setText('显示标签')

        # 设置树形列表标题样式
        try:
            self.book_tree.headerItem().setFont(0, QFont('', 16, QFont.Weight.Bold))  # 减小标题字体大小
            self.label_tree.headerItem().setFont(0, QFont('', 16, QFont.Weight.Bold))
            self.notes_list.headerItem().setFont(0, QFont('', 16, QFont.Weight.Bold))

            # 设置形列表项的字体
            self.book_tree.setStyleSheet("""
                QTreeWidget::item {
                    height: 30px;
                    font-size: 14px;
                }
                QTreeWidget::item:has-children {  /* 父节点（格式分类）样式 */
                    font-size: 16px;
                    font-weight: bold;
                    color: #333;
                    background: #f8f8f8;
                    padding: 4px;
                }
            """)
        except Exception as e:
            print(f"设置标题字体时出错: {e}")

        # 在 init_ui 方法中，创建按钮的部分添加：

        # 笔记功能下拉菜单
        note_menu = QMenu(self)
        note_menu.addAction("添加笔记", self.add_note)
        note_menu.addAction("显示/隐藏笔记列表", self.toggle_notes_panel)

        note_btn = QPushButton("笔记功能")
        note_btn.setStyleSheet(button_style)
        note_btn.setMenu(note_menu)

        # 将 toggle_notes_btn 作为类属性
        self.toggle_notes_btn = QPushButton('显示笔记')
        self.toggle_notes_btn.clicked.connect(self.toggle_notes_panel)
        self.toggle_notes_btn.setStyleSheet(button_style)

    def init_database(self):
        """初始化数据库"""
        try:
            db_path = Path('library.db')
            self.conn = sqlite3.connect(str(db_path))
            self.cursor = self.conn.cursor()  # 添加这行，创建游标对象

            # 创建书籍表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    title TEXT,
                    format TEXT,
                    size INTEGER
                )
            ''')

            # 创建笔记表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    content TEXT,
                    page INTEGER,
                    timestamp TEXT,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            ''')

            # 创建标记表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS marks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    page INTEGER,
                    start_x INTEGER,
                    start_y INTEGER,
                    end_x INTEGER,
                    end_y INTEGER,
                    color TEXT,
                    width INTEGER,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            ''')

            # 创建缩放状态表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS zoom_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER UNIQUE,
                    zoom_factor REAL,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            ''')

            # 创建标签表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    page INTEGER,
                    text TEXT,
                    pos_x INTEGER,
                    pos_y INTEGER,
                    color TEXT,
                    font_size INTEGER,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            ''')

            # 启用外键约束
            self.cursor.execute('PRAGMA foreign_keys = ON')

            # 添加保存当前页码的表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS current_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER UNIQUE,
                    page INTEGER,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            ''')

            self.conn.commit()
        except Exception as e:
            print(f"初始化数据库失败: {e}")

    def load_library(self):
        """数据库载书籍"""
        try:
            self.books = {}
            self.cursor.execute('SELECT id, path, title, format, size FROM books')
            for row in self.cursor.fetchall():
                id_, path, title, format_, size = row
                self.books[path] = {
                    'id': id_,
                    'path': path,
                    'title': title,
                    'format': format_,
                    'size': size
                }
            self.update_book_tree()
        except Exception as e:
            print(f"加载书库失败: {e}")

    def save_library(self):
        """保存书库数据库"""
        try:
            # 不删除所有记录，而更新现有记录或插入新记录
            for path, info in self.books.items():
                if 'id' in info:  # 如果已有ID更新记录
                    self.cursor.execute(
                        'UPDATE books SET title = ?, format = ?, size = ? WHERE id = ?',
                        (info['title'], info['format'], info['size'], info['id']))
                else:  # 如果��新记录，插入
                    self.cursor.execute(
                        'INSERT INTO books (path, title, format, size) VALUES (?, ?, ?, ?)',
                        (path, info['title'], info['format'], info['size']))
                    # 获取新插入记录的ID
                    info['id'] = self.cursor.lastrowid
            self.conn.commit()
        except Exception as e:
            print(f"保存���库失败: {e}")

    def load_notes(self):
        """从数据库加载笔记"""
        try:
            self.notes = {}
            self.cursor.execute('''
                SELECT n.*, b.path 
                FROM notes n 
                JOIN books b ON n.book_id = b.id 
                ORDER BY n.timestamp
            ''')
            for row in self.cursor.fetchall():
                _, book_id, content, page, timestamp, book_path = row
                if book_path not in self.notes:
                    self.notes[book_path] = []
                self.notes[book_path].append({
                    'book_id': book_id,
                    'content': content,
                    'page': page,
                    'timestamp': timestamp
                })
        except Exception as e:
            print(f"加载笔记失败: {e}")

    def save_notes(self):
        """保存笔记到数据库"""
        try:
            # 先删除所有笔记
            self.cursor.execute('DELETE FROM notes')

            # 遍历所有书籍的笔记
            for book_path in list(self.notes.keys()):  # 使用 list() 创���副本
                # 确保 book_path 存在于 self.books 中
                if book_path in self.books and isinstance(self.notes[book_path], list):
                    book_id = self.books[book_path]['id']

                    # 遍历该书籍的所有笔记
                    for note in self.notes[book_path]:
                        if isinstance(note, dict):  # 确保 note 是字典类型
                            self.cursor.execute(
                                'INSERT INTO notes (book_id, content, page, timestamp) VALUES (?, ?, ?, ?)',
                                (book_id,
                                 note.get('content', ''),
                                 note.get('page', 0),
                                 note.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                            )

            # 提交事务
            self.conn.commit()
            print("笔记已保存到数据库")

        except Exception as e:
            print(f"保存笔记失败: {e}")
            QMessageBox.warning(self, "错误", f"保存笔记失败: {str(e)}")

    def load_marks(self):
        """从数据库加载标记"""
        try:
            self.page_marks = {}
            self.cursor.execute('''
                SELECT m.*, b.path 
                FROM marks m 
                JOIN books b ON m.book_id = b.id
            ''')
            for row in self.cursor.fetchall():
                _, book_id, page, start_x, start_y, end_x, end_y, color, width, book_path = row
                key = f"{book_path}_{page}"
                if key not in self.page_marks:
                    self.page_marks[key] = []

                mark_data = {
                    'start': QPoint(start_x, start_y),
                    'end': QPoint(end_x, end_y),
                    'color': QColor(color),
                    'width': width
                }
                self.page_marks[key].append(mark_data)

            if hasattr(self, 'content_display'):
                self.content_display.page_marks = self.page_marks.copy()

            print("数据加载标记完成")
        except Exception as e:
            print(f"从数据库加载标失败: {e}")
            self.page_marks = {}
            if hasattr(self, 'content_display'):
                self.content_display.page_marks = {}

    def save_marks(self):
        """保存标记到数据库"""
        try:
            # 先删除所有标记
            sql = 'DELETE FROM marks'
            self.cursor.execute(sql)

            # 遍历所有标记
            for key, marks in self.page_marks.items():
                # 解析书籍路径和页码
                book_path, page = key.rsplit('_', 1)
                book_id = self.books[book_path]['id']

                # 保存每个标记
                for mark in marks:
                    # 准备SQL语句和参数
                    sql = ('INSERT INTO marks '
                           '(book_id, page, start_x, start_y, end_x, end_y, color, width) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?, ?)')  # 修复：添加了缺少的一个问号
                    params = [
                        book_id,
                        int(page),
                        mark['start'].x(),
                        mark['start'].y(),
                        mark['end'].x(),
                        mark['end'].y(),
                        mark['color'].name(),
                        mark['width']
                    ]

                    # 执行SQL
                    self.cursor.execute(sql, params)

            # 提交事务
            self.conn.commit()
            print("标记已保存到数据库")

        except Exception as e:
            print(f"保存标记到数据库失败: {e}")

    def load_zoom_states(self):
        """从数据库加载缩放状态"""
        try:
            self.zoom_states = {}
            self.cursor.execute('''
                SELECT z.*, b.path 
                FROM zoom_states z 
                JOIN books b ON z.book_id = b.id
            ''')
            for row in self.cursor.fetchall():
                _, book_id, zoom_factor, book_path = row
                self.zoom_states[book_path] = zoom_factor
        except Exception as e:
            print(f"加载放状态失败: {e}")

    def save_zoom_states(self):
        """保放状态到数据库"""
        try:
            self.cursor.execute('DELETE FROM zoom_states')
            for book_path, zoom_factor in self.zoom_states.items():
                book_id = self.books[book_path]['id']
                self.cursor.execute(
                    'INSERT INTO zoom_states (book_id, zoom_factor) VALUES (?, ?)',
                    (book_id, zoom_factor)
                )
            self.conn.commit()
        except Exception as e:
            print(f"保存放状态失败: {e}")

    def closeEvent(self, event):
        """程序关闭时的处理"""
        try:
            # 保存当前页面标记到数据库
            if self.current_book_path and self.marking_enabled:
                try:
                    book_id = self.books[self.current_book_path]['id']
                    # 先删除当前页面的旧标记
                    self.cursor.execute('DELETE FROM marks WHERE book_id = ? AND page = ?',
                                        (book_id, self.current_page))

                    # 插入新标记
                    for mark in self.content_display.marks:
                        self.cursor.execute(
                            'INSERT INTO marks (book_id, page, start_x, start_y, end_x, end_y, color, width) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                            (book_id, self.current_page,
                             mark['start'].x(), mark['start'].y(),
                             mark['end'].x(), mark['end'].y(),
                             mark['color'].name(), mark['width'])
                        )

                    # 提交事务
                    self.conn.commit()
                    print("关闭程序前保存标记到数据库完成")
                except Exception as e:
                    print(f"关闭程序时保存标记失败: {e}")

            # 保存其他数据
            self.save_library()
            self.save_notes()
            self.save_zoom_states()
            self.save_labels()  # 保存标签

            # 关闭数据库连接
            self.conn.close()

            event.accept()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            event.accept()

    def toggle_booklist(self):
        """切换书籍列表显示状态"""
        if self.booklist_visible:
            self.left_panel.hide()
            self.toggle_booklist_btn.setText('显示书列')
        else:
            self.left_panel.show()
            self.toggle_booklist_btn.setText('隐藏书列')
        self.booklist_visible = not self.booklist_visible

    def import_books(self):
        """导入书籍"""
        folder = QFileDialog.getExistingDirectory(self, '选择书籍文件')
        if folder:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.supported_formats:
                        file_path = os.path.join(root, file)
                        self.add_book(file_path)
            self.update_book_tree()

    def add_book(self, file_path):
        """添加书籍到"""
        try:
            book_info = self.get_book_info(file_path)
            if book_info:
                self.books[file_path] = book_info
                self.save_library()
        except Exception as e:
            QMessageBox.warning(self, '错误', f'添加书失败: {str(e)}')

    def get_book_info(self, file_path):
        """获��书籍信息"""
        ext = os.path.splitext(file_path)[1].lower()
        info = {
            'path': file_path,
            'title': os.path.basename(file_path),
            'format': ext[1:],
            'size': os.path.getsize(file_path)
        }

        try:
            if ext == '.pdf':
                doc = fitz.open(file_path)
                info['pages'] = len(doc)
                doc.close()
            elif ext == '.epub':
                book = epub.read_epub(file_path)
                info['title'] = book.get_metadata('DC', 'title')[0][0]


        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return info

    def update_book_tree(self):
        """更新书籍形显示"""
        self.book_tree.clear()

        # 按格式分组
        formats = {}
        for book in self.books.values():
            fmt = book['format']
            if fmt not in formats:
                formats[fmt] = []
            formats[fmt].append(book)

        # 添加到树形结构
        for fmt, books in formats.items():
            format_item = QTreeWidgetItem(self.book_tree)
            format_item.setText(0, fmt.upper())

            for book in books:
                book_item = QTreeWidgetItem(format_item)
                book_item.setText(0, book['title'])
                book_item.setData(0, Qt.ItemDataRole.UserRole, book['path'])

    def on_item_double_clicked(self, item, column):
        """处理双击事件"""
        if item.parent():  # 确保是书籍项而不是分类项
            self.open_book(item)

    def open_book(self, item):
        """打开书籍"""
        if not item.parent():
            return

        try:
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if not os.path.exists(file_path):
                QMessageBox.warning(self, '错误', '文件不存在！')
                return

            # 保存之前书籍的标记和绘图
            if self.current_book_path:
                if self.marking_enabled:
                    self.save_drawings()
                self.save_current_marks()
                # 保存当前书籍的页码
                self.save_current_page()

            # 设置新书籍
            self.current_book_path = file_path
            self.zoom_factor = self.zoom_states.get(file_path, 1.0)
            self.update_zoom_label()

            # 清除当前显示的标记
            self.content_display.marks = []

            # 加载标记数据
            self.load_marks()

            # 加载笔记数据
            self.load_notes()

            # 打开文件并加载上次阅读的页码
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                self.open_pdf(file_path)
                # 加载上次阅读的页码
                if not self.load_current_page():  # 如果没有保存的页码，设为第一页
                    self.current_page = 0
                    self.save_current_page()
                self.show_current_page()
            elif ext in ['.epub', '.mobi', '.azw', '.azw3']:
                self.convert_and_open_ebook(file_path)
                # 加载上次阅读的页码
                if not self.load_current_page():  # 如果没有保存的页码，设为第一页
                    self.current_page = 0
                    self.save_current_page()
                self.show_current_page()
            elif ext == '.txt':
                self.open_txt(file_path)

            # 更新窗口标题
            if file_path in self.books:
                book_title = self.books[file_path]['title']
                self.setWindowTitle(f"晓阅 - 阅我所悦，享受时光 - {book_title}")

            # 加载当前页面的标记和标签
            key = f"{file_path}_{self.current_page}"
            self.content_display.set_current_page(key)
            if key in self.page_marks:
                self.content_display.marks = self.page_marks[key].copy()

            # 更新标签列表和笔记列表
            self.update_labels_list()
            self.update_notes_list()

        except Exception as e:
            print(f"打开文件详细错误: {e}")
            QMessageBox.warning(self, "错误", f"打开文件失败: {str(e)}")

    def open_pdf(self, file_path):
        """打开PDF文件"""
        try:
            self.current_doc = fitz.open(file_path)
            # 不在这里设置 current_page = 0，让 load_current_page 来设置页码
            self.show_current_page()
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开PDF失败: {str(e)}')

    def open_epub(self, file_path):
        """打开EPUB文件"""
        try:
            # 显示加载提示
            self.statusBar().showMessage("正在转电子书格式...", 2000)
            QApplication.processEvents()

            # 创建时PDF文件路径
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_pdf')
            os.makedirs(temp_dir, exist_ok=True)
            pdf_path = os.path.join(temp_dir, os.path.basename(file_path) + '.pdf')

            # 如果已经有换好的PDF，直接打开
            if os.path.exists(pdf_path):
                self.current_doc = fitz.open(pdf_path)
                self.current_page = 0
                self.show_current_page()
                return

            # 使用 calibre 的命令行工具转换
            try:
                import subprocess
                result = subprocess.run(['ebook-convert', file_path, pdf_path],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    self.current_doc = fitz.open(pdf_path)
                    self.current_page = 0
                    self.show_current_page()
                else:
                    raise Exception(f"转换失败: {result.stderr}")
            except FileNotFoundError:
                QMessageBox.warning(self, '错误',
                                    'ebook-convert 工具未找到。请安装 Calibre 软件。\n'
                                    '下载地址: https://calibre-ebook.com/download')
                return

        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开EPUB失败: {str(e)}')
            print(f"打开EPUB细错误: {e}")

    def load_epub_pages(self, start_page, count):
        """加载指定范围的页面"""
        try:
            if isinstance(self.current_doc, epub.EpubBook):
                end_page = min(start_page + count, len(self.epub_items))
                for page_num in range(start_page, end_page):
                    if page_num not in self.page_cache and page_num < len(self.epub_items):
                        try:
                            item = self.epub_items[page_num]
                            content = item.get_content().decode('utf-8')
                            self.page_cache[page_num] = {
                                'content': content,
                                'processed': False
                            }
                        except Exception as e:
                            print(f"加载第 {page_num} 页时出错: {e}")
                        QApplication.processEvents()

                # 继续加载后面页面
                if end_page < len(self.epub_items):
                    QTimer.singleShot(200, lambda: self.load_epub_pages(end_page, 2))

        except Exception as e:
            print(f"加载页面时出错: {e}")

    def check_and_preload(self):
        """检查是否需要预加载更多页面"""
        try:
            if isinstance(self.current_doc, epub.EpubBook):
                # 当前页面是已加载页面的一半时，加载后面10页
                loaded_pages = len(self.page_cache)
                if self.current_page >= loaded_pages // 2:
                    next_start = loaded_pages
                    if next_start < len(self.epub_items):
                        self.load_epub_pages(next_start, 10)
        except Exception as e:
            print(f"检查预加载时出错: {e}")

    def open_txt(self, file_path):
        """打开TXT文件"""
        try:
            # 清理之前的文档状态
            self.current_doc = None
            self.current_page = 0

            # 尝试不同的编��方式打开文件
            encodings = ['utf-8', 'gbk', 'gb2312', 'ansi']
            content = None

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break  # 如果成功读取，跳出循环
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise Exception("无法识别文件编码")

            # 清除之前的图片显示
            self.content_display.clear()
            self.content_display.setPixmap(QPixmap())  # 清除之前的图片

            # 设���基样式，添���动态换行和宽度限制
            styled_content = f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            font-size: 20px;
                            line-height: 1.6;
                            margin: 20px;
                            background-color: white;
                            white-space: pre-wrap;
                            word-wrap: break-word;
                            max-width: 95%;
                        }}
                        p {{
                            margin: 0;
                            text-align: justify;
                        }}
                    </style>
                </head>
                <body>
                    <p>{content}</p>
                </body>
                </html>
            """

            # 设置为富文本格式显示
            self.content_display.setTextFormat(Qt.TextFormat.RichText)
            self.content_display.setText(styled_content)
            self.content_display.setWordWrap(True)  # 启用自动换行

            # 更新页码显示（txt文件只有一页）
            self.current_page_label.setText("1/1")

            print(f"成功打开TXT文件: {file_path}")

        except Exception as e:
            error_msg = f"打开TXT文件败: {str(e)}"
            QMessageBox.warning(self, '误', error_msg)
            print(error_msg)

    def show_current_page(self):
        """显示当前页面"""
        try:
            if isinstance(self.current_doc, fitz.Document):  # PDF
                if 0 <= self.current_page < len(self.current_doc):
                    # 更新页码显示
                    self.current_page_label.setText(f"{self.current_page + 1}/{len(self.current_doc)}")

                    # 渲染页面
                    page = self.current_doc[self.current_page]
                    zoom_matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor)
                    pix = page.get_pixmap(matrix=zoom_matrix)

                    # 转换为QImage并显示
                    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(img)
                    self.content_display.setPixmap(pixmap)

                    # 设置当前面键值并加载标记和标签
                    key = f"{self.current_book_path}_{self.current_page}"
                    self.content_display.set_current_page(key)
                    self.load_labels()

                    self.content_display.update()

            # 更新标签列表
            self.update_labels_list()

        except Exception as e:
            print(f"显示当前页面时出错: {e}")

    def process_epub_images(self, content, item):
        """处理EPUB中的图片路径"""
        try:
            # 检查是否已经处理过
            if hasattr(self, 'processed_images') and item.file_name in self.processed_images:
                return self.processed_images[item.file_name]

            # 获取当前文件目录
            base_dir = os.path.dirname(item.file_name) if hasattr(item, 'file_name') else ''

            # 创建临时文件夹（如果不存在）
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_images')
            os.makedirs(temp_dir, exist_ok=True)

            # 只处理当前内容中的图片
            image_paths = re.findall(r'src=["\']([^"\']+)["\']', content)
            if image_paths:
                # 限制每页最多处理5张图片
                for image_path in image_paths[:5]:
                    image_name = os.path.basename(image_path)
                    temp_path = os.path.join(temp_dir, image_name)

                    if not os.path.exists(temp_path):
                        # 查找对应的图片项
                        for image in self.current_doc.get_items_of_type(ebooklib.ITEM_IMAGE):
                            if image.file_name.endswith(image_name):
                                try:
                                    with open(temp_path, 'wb') as f:
                                        f.write(image.content)
                                    break
                                except Exception as e:
                                    print(f"保存图片失败: {e}")
                                    continue

                    # 替换图片路径
                    content = content.replace(f'src="{image_path}"', f'src="{temp_path}"')
                    content = content.replace(f"src='{image_path}'", f"src='{temp_path}'")

            # 缓存处理结果
            if not hasattr(self, 'processed_images'):
                self.processed_images = {}
            self.processed_images[item.file_name] = content

            return content
        except Exception as e:
            print(f"处理EPUB图片时出错: {e}")
            return content

    def prev_page(self):
        """上一页"""
        try:
            if self.current_doc and self.current_page > 0:
                # 先保存当前页面的标记
                if self.marking_enabled:
                    self.content_display.save_current_marks()
                    QApplication.processEvents()  # 让界面响应
                    self.save_marks()

                self.current_page -= 1
                # 保存新的页码到数据库
                self.save_current_page()
                self.show_current_page()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"切换上一页时出错: {str(e)}")

    def next_page(self):
        """下一页"""
        try:
            if self.current_doc:
                if isinstance(self.current_doc, fitz.Document):
                    if self.current_page < len(self.current_doc) - 1:
                        # 先保存当前页面的标记
                        if self.marking_enabled:
                            self.content_display.save_current_marks()
                            QApplication.processEvents()  # 让界面响应
                            self.save_marks()

                        self.current_page += 1
                        # 保存新的页码到数据库
                        self.save_current_page()
                        self.show_current_page()
                elif isinstance(self.current_doc, epub.EpubBook):
                    items = list(self.current_doc.get_items_of_type(ebooklib.ITEM_DOCUMENT))
                    if self.current_page < len(items) - 1:
                        # 先保存当前页面的标记
                        if self.marking_enabled:
                            self.content_display.save_current_marks()
                            QApplication.processEvents()  # 让界面响应
                            self.save_marks()

                        self.current_page += 1
                        # 保存新的页码到数据库
                        self.save_current_page()
                        self.show_current_page()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"切换下一页时出错: {str(e)}")

    def zoom_in(self):
        """放大"""
        if self.zoom_factor < self.max_zoom:
            self.zoom_factor *= 1.2
            self.zoom_factor = min(self.zoom_factor, self.max_zoom)
            self.update_zoom_label()
            # 保存缩放状态
            if self.current_book_path:
                self.zoom_states[self.current_book_path] = self.zoom_factor
            self.show_current_page()

    def zoom_out(self):
        """缩小"""
        if self.zoom_factor > self.min_zoom:
            self.zoom_factor /= 1.2
            self.zoom_factor = max(self.zoom_factor, self.min_zoom)
            self.update_zoom_label()
            # 保存缩放状态
            if self.current_book_path:
                self.zoom_states[self.current_book_path] = self.zoom_factor
            self.show_current_page()

    def update_zoom_label(self):
        """更新缩放比例显示"""
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")

    def goto_page(self):
        """跳转到指定页面"""
        try:
            page_num = int(self.page_input.text()) - 1
            if isinstance(self.current_doc, fitz.Document):
                if 0 <= page_num < len(self.current_doc):
                    self.content_display.save_current_marks()  # 保存当前页面标记
                    self.current_page = page_num
                    # 保存新的页码到数据库
                    self.save_current_page()
                    self.show_current_page()
                else:
                    QMessageBox.warning(self, '警告', '页码超出范围！')
        except ValueError:
            QMessageBox.warning(self, '警告', '请输入有效的页码！')

    def save_current_page(self):
        """保存当前页码到数据库"""
        try:
            if self.current_book_path and self.current_book_path in self.books:
                book_id = self.books[self.current_book_path]['id']

                # 检查是否已存在页码记录
                self.cursor.execute('''
                    SELECT id FROM current_pages 
                    WHERE book_id = ?
                ''', (book_id,))

                result = self.cursor.fetchone()

                if result:
                    # 更新现有记录
                    self.cursor.execute('''
                        UPDATE current_pages 
                        SET page = ? 
                        WHERE book_id = ?
                    ''', (self.current_page, book_id))
                else:
                    # 插入新记录
                    self.cursor.execute('''
                        INSERT INTO current_pages (book_id, page) 
                        VALUES (?, ?)
                    ''', (book_id, self.current_page))

                self.conn.commit()
                print(f"已保存 {self.books[self.current_book_path]['title']} 的页码: {self.current_page + 1}")
        except Exception as e:
            print(f"保存当前页码失败: {e}")

    def load_current_page(self):
        """从数据库加载上次阅读的页码"""
        try:
            if self.current_book_path and self.current_book_path in self.books:
                book_id = self.books[self.current_book_path]['id']

                self.cursor.execute('''
                    SELECT page FROM current_pages 
                    WHERE book_id = ?
                ''', (book_id,))

                result = self.cursor.fetchone()

                if result:
                    saved_page = result[0]
                    # 确保页码在有效范围内
                    if isinstance(self.current_doc, fitz.Document):
                        if 0 <= saved_page < len(self.current_doc):
                            self.current_page = saved_page
                            return True

                # 如果没有保存的页码或页码无���，返回False
                return False
        except Exception as e:
            print(f"加载上次阅读页码失败: {e}")
            return False

    def choose_color(self):
        """切换标记状态"""
        try:
            if not self.marking_enabled:
                # 启用标记
                color = QColorDialog.getColor(self.content_display.current_color, self)
                if color.isValid():
                    self.content_display.current_color = color
                    self.marking_enabled = True
                    self.color_btn.setText('取消标记')
                    self.content_display.setMouseTracking(True)
                    # 显示保存按钮并启动自动保存（改为3分钟）
                    self.save_button.show()
                    self.auto_save_timer.start(180000)  # 3分钟
            else:
                # 使用标记前先保存
                if self.current_book_path:
                    self.save_drawings()

                # 禁用标记
                self.marking_enabled = False
                self.color_btn.setText('标记颜色')
                self.content_display.setMouseTracking(False)
                # 隐藏保存按钮并止自动保存
                self.save_button.hide()
                self.auto_save_timer.stop()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"切换标记模式时出错: {str(e)}")

    def clear_current_marks(self):
        """清除当前页的标记"""
        self.content_display.clear_marks()
        if self.current_book_path and self.current_page is not None:
            key = f"{self.current_book_path}_{self.current_page}"
            if key in self.page_marks:
                del self.page_marks[key]
                self.save_marks()

    def save_current_marks(self):
        """��存当前页面的记"""
        if self.current_book_path and self.current_page is not None:
            key = f"{self.current_book_path}_{self.current_page}"
            self.page_marks[key] = self.content_display.marks.copy()
            self.save_marks()

    def add_note(self):
        """添加笔记"""
        if not self.current_book_path:
            QMessageBox.warning(self, '警告', '请打开一本书！')
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('添加笔记')
        dialog.setFixedWidth(400)

        layout = QVBoxLayout(dialog)

        # 笔容输入
        note_label = QLabel('笔记内容:')
        note_edit = QTextEdit()
        layout.addWidget(note_label)
        layout.addWidget(note_edit)

        # 按钮
        button_layout = QHBoxLayout()
        save_btn = QPushButton('保存')
        cancel_btn = QPushButton('取消')
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        def save_note():
            content = note_edit.toPlainText()
            if content:
                if self.current_book_path not in self.notes:
                    self.notes[self.current_book_path] = []

                note = {
                    'content': content,
                    'page': self.current_page,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                self.notes[self.current_book_path].append(note)
                self.save_notes()
                self.update_notes_list()
                dialog.accept()

        save_btn.clicked.connect(save_note)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def update_notes_list(self):
        """更新笔记列表"""
        try:
            self.notes_list.clear()
            if self.current_book_path and self.current_book_path in self.notes:
                # 按页码分组笔记
                page_groups = {}
                for note in self.notes[self.current_book_path]:
                    page = note['page']
                    if page not in page_groups:
                        page_groups[page] = []
                    page_groups[page].append(note)

                # 按页码顺序添加到树形列表
                for page in sorted(page_groups.keys()):
                    # 创建页码项
                    page_item = QTreeWidgetItem(self.notes_list)
                    page_item.setText(0, f"第 {page + 1} 页")

                    # 按时间倒序排序该页的笔记
                    page_notes = sorted(page_groups[page],
                                        key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S'),
                                        reverse=True)

                    # 添加该页的所有笔记
                    for note in page_notes:
                        note_item = QTreeWidgetItem(page_item)
                        # 显示笔记预览（限制长度）
                        preview = note['content'][:50] + '...' if len(note['content']) > 50 else note['content']
                        note_item.setText(0, preview)
                        note_item.setData(0, Qt.ItemDataRole.UserRole, note)

                        # 设置提示信息，显示完整内容
                        note_item.setToolTip(0, f"时间：{note['timestamp']}\n"
                                                f"内容：{note['content']}")

                # 展开所有项
                self.notes_list.expandAll()

        except Exception as e:
            print(f"更新笔记列表时出错: {e}")

    def view_note(self, item):
        """查看和编辑笔记"""
        try:
            note = item.data(0, Qt.ItemDataRole.UserRole)
            if note:
                dialog = QDialog(self)
                dialog.setWindowTitle('查看/编辑笔记')
                dialog.setFixedWidth(400)

                layout = QVBoxLayout(dialog)

                # 笔记信息
                info_label = QLabel(f"页码：第{note['page'] + 1}页\n时间：{note['timestamp']}")
                layout.addWidget(info_label)

                # 笔记内容（可编辑）
                content_edit = QTextEdit()
                content_edit.setPlainText(note['content'])
                content_edit.setReadOnly(False)  # 设置为可编辑
                layout.addWidget(content_edit)

                # 按钮布局
                button_layout = QHBoxLayout()

                # 保存按钮
                save_btn = QPushButton('保存修改')

                def save_changes():
                    try:
                        # 更新笔记内容
                        note['content'] = content_edit.toPlainText()
                        # 更新时间戳
                        note['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        # 保存到数据库
                        self.save_notes()
                        # 更新列表显示
                        self.update_notes_list()
                        # 显示保存成功提示
                        self.statusBar().showMessage("笔记已保存", 2000)
                        # 更新预览窗口标题栏时间
                        info_label.setText(f"页码：第{note['page'] + 1}页\n时间：{note['timestamp']}")
                    except Exception as e:
                        print(f"保存笔记修改时出错: {e}")
                        QMessageBox.warning(self, "错误", "保存笔记失败")

                save_btn.clicked.connect(save_changes)
                button_layout.addWidget(save_btn)

                # 删除按钮
                delete_btn = QPushButton('删除')

                def delete_note():
                    reply = QMessageBox.question(dialog, '确认删除',
                                                 '确定要删除这条笔记吗？',
                                                 QMessageBox.StandardButton.Yes |
                                                 QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        try:
                            # 从笔记列表中删除
                            if self.current_book_path in self.notes:
                                self.notes[self.current_book_path].remove(note)
                                if not self.notes[self.current_book_path]:
                                    del self.notes[self.current_book_path]
                                # 保存更改
                                self.save_notes()
                                # 更新列表显示
                                self.update_notes_list()
                                # 关闭对话框
                                dialog.accept()
                                # 显示删除成功提示
                                self.statusBar().showMessage("笔记已删除", 2000)
                        except Exception as e:
                            print(f"删除笔记时出错: {e}")
                            QMessageBox.warning(self, "错误", "删除笔记失败")

                delete_btn.clicked.connect(delete_note)
                button_layout.addWidget(delete_btn)

                # 跳转按钮
                goto_btn = QPushButton('跳转到页面')

                def goto_page():
                    try:
                        self.current_page = note['page']
                        self.show_current_page()
                        dialog.accept()
                        self.statusBar().showMessage(f"已跳转到第 {note['page'] + 1} 页", 2000)
                    except Exception as e:
                        print(f"跳转到笔记页面时出错: {e}")
                        QMessageBox.warning(self, "错误", "跳转失败")

                goto_btn.clicked.connect(goto_page)
                button_layout.addWidget(goto_btn)

                # 关闭按钮
                close_btn = QPushButton('关闭')
                close_btn.clicked.connect(dialog.accept)
                button_layout.addWidget(close_btn)

                layout.addLayout(button_layout)
                dialog.exec()

        except Exception as e:
            print(f"查看/编辑笔记时出错: {e}")
            QMessageBox.warning(self, "错误", f"操作失败: {str(e)}")

    def handle_content_change(self, editor, save_btn):
        """处理笔记内容变化"""
        # 启用保存按钮
        save_btn.setEnabled(True)

    def toggle_notes_panel(self):
        """切换笔记面板显示状态"""
        try:
            if self.stacked_widget.currentWidget() != self.stacked_widget.widget(1):  # 如果当前不是记页
                # 记住标签页的显状态
                was_labels_visible = not self.right_panel.isHidden() and self.stacked_widget.currentWidget() == self.stacked_widget.widget(
                    0)

                # 显示记面板前更新笔记列表
                self.update_notes_list()
                self.stacked_widget.setCurrentIndex(1)  # 切换到笔记页
                self.right_panel.show()  # 显示右侧面板
                self.toggle_notes_btn.setText('隐藏笔记')

                # 保存标签页之前的显示状态
                self.labels_was_visible = was_labels_visible
            else:
                self.stacked_widget.setCurrentIndex(0)  # 切换回标签页
                self.toggle_notes_btn.setText('显示笔记')

                # 根据之前的状态决定是否显示标签页
                if not hasattr(self, 'labels_was_visible') or not self.labels_was_visible:
                    self.right_panel.hide()
                else:
                    self.right_panel.show()

        except Exception as e:
            print(f"切换笔记面板时出错: {e}")

    def search_books(self):
        """搜索书籍"""
        query = self.search_input.text().lower()
        for i in range(self.book_tree.topLevelItemCount()):
            format_item = self.book_tree.topLevelItem(i)
            format_item.setHidden(False)

            has_visible_children = False
            for j in range(format_item.childCount()):
                book_item = format_item.child(j)
                title = book_item.text(0).lower()
                book_item.setHidden(query not in title)
                if not book_item.isHidden():
                    has_visible_children = True

            format_item.setHidden(not has_visible_children)

    def show_book_menu(self, position):
        """显示书右键菜单"""
        item = self.book_tree.itemAt(position)
        if not item:
            return

        menu = QMenu()

        if item.parent():  # 书籍项
            open_action = QAction('打开', self)
            open_action.triggered.connect(lambda: self.open_book(item))
            menu.addAction(open_action)

            delete_action = QAction('删除', self)
            delete_action.triggered.connect(lambda: self.delete_book(item))
            menu.addAction(delete_action)

        menu.exec(self.book_tree.viewport().mapToGlobal(position))

    def delete_book(self, item):
        """删除书籍"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, '确认删除',
                                     '确定要从库中删除这本书吗？',
                                     QMessageBox.StandardButton.Yes |
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 删除书籍（级联删除会自动删除相关的��记、标记和缩放状态）
                self.cursor.execute('DELETE FROM books WHERE path = ?', (file_path,))
                self.conn.commit()

                # 从内存中删除
                del self.books[file_path]
                if file_path in self.notes:
                    del self.notes[file_path]
                for key in list(self.page_marks.keys()):
                    if key.startswith(file_path):
                        del self.page_marks[key]
                if file_path in self.zoom_states:
                    del self.zoom_states[file_path]

                # 更新界面
                self.update_book_tree()
                self.update_notes_list()
            except Exception as e:
                print(f"删除书籍失: {e}")
                QMessageBox.warning(self, "错误", "删除书籍失败")

    def auto_save_drawings(self):
        """自动保存手写绘图"""
        try:
            if self.current_book_path and self.marking_enabled:
                current_time = datetime.now()
                if hasattr(self, 'last_save_time'):
                    time_diff = (current_time - self.last_save_time).total_seconds()
                    if time_diff < 180:  # 如果距离上次保存不到3分钟，跳过
                        return

                # 调用保存方法
                self.save_drawings()
                self.last_save_time = current_time

        except Exception as e:
            print(f"自动保存绘图失败: {e}")

    def save_drawings(self):
        """手动保存手写绘图"""
        try:
            if self.current_book_path and self.marking_enabled:
                book_id = self.books[self.current_book_path]['id']

                # 先删除当前页面的标记
                self.cursor.execute('DELETE FROM marks WHERE book_id = ? AND page = ?',
                                    (book_id, self.current_page))

                # 插入新标记
            if self.current_book_path and self.marking_enabled:
                book_id = self.books[self.current_book_path]['id']

                # 先删除当前页面的标记
                self.cursor.execute('DELETE FROM marks WHERE book_id =? AND page =?',
                                    (book_id, self.current_page))

                # 插入新标记
                if self.content_display.marks:  # 如果有标记
                    for mark in self.content_display.marks:
                        self.cursor.execute(
                            '''INSERT INTO marks 
                               (book_id, page, start_x, start_y, end_x, end_y, color, width)
                               VALUES (?,?,?,?,?,?,?,?)''',
                            (book_id, self.current_page,
                             mark['start'].x(), mark['start'].y(),
                             mark['end'].x(), mark['end'].y(),
                             mark['color'].name(), mark['width']))

                        # 提交事务
                        self.conn.commit()

                        # 更新内存中的标记
                        key = f"{self.current_book_path}_{self.current_page}"
                        self.page_marks[key] = self.content_display.marks.copy()

                        # 显示临时提示
                        self.statusBar().showMessage("绘图已保存", 2000)
                        print(f"保存了 {len(self.content_display.marks)} 个标记到数据库")

        except Exception as e:
            print(f"保存图到数据库时出错: {str(e)}")
            QMessageBox.warning(self, "错误", "保存绘图失败")

    def load_remaining_items(self):
        """后台加载剩余的项目"""
        try:
            if len(self.total_items) > 5:
                # 每次加载5个项目
                start = len(self.epub_items)
                end = min(start + 5, len(self.total_items))

                self.epub_items.extend(self.total_items[start:end])
                QApplication.processEvents()

                # 如果还有剩余项目，继续加载
                if end < len(self.total_items):
                    QTimer.singleShot(100, self.load_remaining_items)

                # 更新页码显示
                self.current_page_label.setText(f"{self.current_page + 1}/{len(self.total_items)}")
        except Exception as e:
            print(f"加载剩项目时出错: {e}")

    def keyPressEvent(self, event):
        """处理键盘事件"""
        try:
            if event.key() == Qt.Key.Key_Left:  # 左方向键
                self.prev_page()
            elif event.key() == Qt.Key.Key_Right:  # 右向键
                self.next_page()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            print(f"处理键盘事件时出错: {e}")

    def toggle_label_mode(self):
        """切换标签模式"""
        try:
            if not self.labeling_enabled:
                # 创建自定义对话框
                dialog = QDialog(self)
                dialog.setWindowTitle('添加标签')
                dialog.setFixedSize(300, 200)

                layout = QVBoxLayout(dialog)

                # 使用文本框替代输入框
                text_edit = QTextEdit()
                text_edit.setPlaceholderText('请输入标签文本...')
                text_edit.setAcceptRichText(False)  # 只接受纯文本

                # 设置动态换行
                text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

                # 设置文本框样式
                text_edit.setStyleSheet("""
                    QTextEdit {
                        font-size: 14px;
                        padding: 5px;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                    }
                """)

                layout.addWidget(text_edit)

                # 按钮布局
                button_layout = QHBoxLayout()
                ok_button = QPushButton('确定')
                cancel_button = QPushButton('取消')

                button_layout.addWidget(ok_button)
                button_layout.addWidget(cancel_button)
                layout.addLayout(button_layout)

                # 处理按钮点击
                def on_ok():
                    text = text_edit.toPlainText().strip()
                    if text:
                        self.content_display.label_text = text
                        self.labeling_enabled = True
                        self.add_label_btn.setText('取消标签')
                        self.marking_enabled = False  # 关闭标记模式
                        self.color_btn.setText('标记颜色')
                        dialog.accept()

                def on_cancel():
                    dialog.reject()

                ok_button.clicked.connect(on_ok)
                cancel_button.clicked.connect(on_cancel)

                # 显示对话框
                dialog.exec()

            else:
                self.labeling_enabled = False
                self.add_label_btn.setText('添加标签')

        except Exception as e:
            QMessageBox.warning(self, "错误", f"切换标签式时出错: {str(e)}")

    def choose_label_color(self):
        """选择标签颜色"""
        try:
            color = QColorDialog.getColor(self.content_display.label_color, self)
            if color.isValid():
                self.content_display.label_color = color
        except Exception as e:
            QMessageBox.warning(self, "错误", f"选择标签颜色时出错: {str(e)}")

    def clear_current_labels(self):
        """除当前页面的标签"""
        try:
            if self.current_book_path and self.current_page is not None:
                # 从数据库中删除当前页面的标签
                book_id = self.books[self.current_book_path]['id']
                self.cursor.execute(
                    'DELETE FROM labels WHERE book_id = ? AND page = ?',
                    (book_id, self.current_page))  # 修复括号闭合
                self.conn.commit()

                # 从内存中删除当前页面的标签
                key = f"{self.current_book_path}_{self.current_page}"
                if key in self.content_display.page_labels:
                    del self.content_display.page_labels[key]

                # 更新显示
                self.content_display.update()
                self.update_labels_list()

                print(f"已清除第 {self.current_page + 1} 页的所有标签")
        except Exception as e:
            print(f"清除标签失败: {e}")
            QMessageBox.warning(self, "错误", f"清除标签失败: {str(e)}")

    def load_labels(self):
        """从数据库加载标签"""
        try:
            if self.current_book_path:
                book_id = self.books[self.current_book_path]['id']
                self.cursor.execute(
                    '''SELECT page, text, pos_x, pos_y, color, font_size 
                       FROM labels 
                       WHERE book_id = ?''',  # 移除 page 条件，加载所有页面的标签
                    (book_id,)
                )
                labels = self.cursor.fetchall()

                # 清除现有标签
                self.content_display.page_labels = {}

                # 按页面组织标签
                for label in labels:
                    page, text, pos_x, pos_y, color, font_size = label
                    key = f"{self.current_book_path}_{page}"

                    if key not in self.content_display.page_labels:
                        self.content_display.page_labels[key] = []

                    self.content_display.page_labels[key].append({
                        'text': text,
                        'pos': QPoint(pos_x, pos_y),
                        'color': QColor(color),
                        'font_size': font_size
                    })

                # 更新当前页面的显示
                self.content_display.update()
                # 更新标签列表
                self.update_labels_list()

        except Exception as e:
            print(f"加载标签失败: {e}")

    def toggle_labels_panel(self):
        """切换标签面板显示状态"""
        if self.right_panel.isHidden() or self.stacked_widget.currentWidget() != self.stacked_widget.widget(0):
            self.right_panel.show()
            self.stacked_widget.setCurrentIndex(0)  # 切换到标签页
            self.toggle_labels_btn.setText('隐藏标签')
        else:
            self.right_panel.hide()
            self.toggle_labels_btn.setText('显示标签')

    def update_labels_list(self):
        """更新标签树形列表"""
        try:
            self.label_tree.clear()

            if not self.current_book_path:
                return

            # 按页码分组
            page_groups = {}
            if hasattr(self.content_display, 'page_labels'):
                for key, labels in self.content_display.page_labels.items():
                    if key.startswith(self.current_book_path):
                        try:
                            page = int(key.split('_')[-1])
                            if page not in page_groups:
                                page_groups[page] = []
                            page_groups[page].extend(labels)
                        except (ValueError, IndexError):
                            continue

            # 添加到树形结构
            for page, labels in sorted(page_groups.items()):
                page_item = QTreeWidgetItem(self.label_tree)
                page_item.setText(0, f"第 {page + 1} 页")

                for label in labels:
                    label_item = QTreeWidgetItem(page_item)
                    label_item.setText(0, label['text'])
                    label_item.setData(0, Qt.ItemDataRole.UserRole, {
                        'page': page,
                        'text': label['text'],
                        'pos': label['pos'],
                        'color': label['color'],
                        'font_size': label['font_size']
                    })

        except Exception as e:
            print(f"更新标签列表时出错: {e}")

    def search_labels(self):
        """搜索标签"""
        query = self.label_search_input.text().lower()

        for i in range(self.label_tree.topLevelItemCount()):
            page_item = self.label_tree.topLevelItem(i)
            page_item.setHidden(False)

            has_visible_children = False
            for j in range(page_item.childCount()):
                label_item = page_item.child(j)
                label_text = label_item.text(0).lower()
                label_item.setHidden(query not in label_text)
                if not label_item.isHidden():
                    has_visible_children = True

            page_item.setHidden(not has_visible_children)

    def show_label_menu(self, position):
        """显示标签右键菜单"""
        item = self.label_tree.itemAt(position)
        if not item or not item.parent():  # 确保是标签而不是页码
            return

        menu = QMenu()

        edit_action = QAction('编辑', self)
        edit_action.triggered.connect(lambda: self.edit_label(item))
        menu.addAction(edit_action)

        delete_action = QAction('删除', self)
        delete_action.triggered.connect(lambda: self.delete_label(item))
        menu.addAction(delete_action)

        menu.exec(self.label_tree.viewport().mapToGlobal(position))

    def edit_label(self, item):
        """编辑标签"""
        try:
            label_data = item.data(0, Qt.ItemDataRole.UserRole)
            if label_data:
                text, ok = QInputDialog.getText(self, '编辑标签',
                                                '修改标签文本:',
                                                text=label_data['text'])
                if ok and text:
                    # 更新数据库中的标签
                    book_id = self.books[self.current_book_path]['id']
                    self.cursor.execute('''
                        UPDATE labels 
                        SET text = ?
                        WHERE book_id = ? 
                        AND page = ? 
                        AND pos_x = ?
                        AND pos_y = ?
                    ''', (
                        text,
                        book_id,
                        label_data['page'],
                        label_data['pos'].x(),
                        label_data['pos'].y()
                    ))
                    self.conn.commit()

                    # 更新内存中的标签
                    key = f"{self.current_book_path}_{label_data['page']}"
                    if key in self.content_display.page_labels:
                        for label in self.content_display.page_labels[key]:
                            if (label['pos'] == label_data['pos'] and
                                    label['text'] == label_data['text']):
                                label['text'] = text
                                break

                    # 更新显示
                    self.update_labels_list()
                    self.content_display.update()

                    # 显示成功提示
                    self.statusBar().showMessage("标签已更新", 2000)

        except Exception as e:
            print(f"编辑标签时出错: {e}")
            QMessageBox.warning(self, "错误", f"编辑标签失败: {str(e)}")

    def delete_label(self, item):
        """删除标签"""
        try:
            label_data = item.data(0, Qt.ItemDataRole.UserRole)
            if label_data:
                reply = QMessageBox.question(self, '确认删除',
                                             '确定要删除这个标签吗？',
                                             QMessageBox.StandardButton.Yes |
                                             QMessageBox.StandardButton.No)

                if reply == QMessageBox.StandardButton.Yes:
                    # 从数据库中删除签
                    book_id = self.books[self.current_book_path]['id']
                    self.cursor.execute('''
                        DELETE FROM labels 
                        WHERE book_id = ? 
                        AND page = ? 
                        AND text = ?
                        AND pos_x = ?
                        AND pos_y = ?
                    ''', (
                        book_id,
                        label_data['page'],
                        label_data['text'],
                        label_data['pos'].x(),
                        label_data['pos'].y()
                    ))
                    self.conn.commit()

                    # 从内存���删除标签
                    key = f"{self.current_book_path}_{label_data['page']}"
                    if key in self.content_display.page_labels:
                        # 找到并删除标签
                        new_labels = []
                        for label in self.content_display.page_labels[key]:
                            if not (label['pos'] == label_data['pos'] and
                                    label['text'] == label_data['text']):
                                new_labels.append(label)
                        self.content_display.page_labels[key] = new_labels

                        # 如果页面没有标签了，删除整个页面的记录
                        if not self.content_display.page_labels[key]:
                            del self.content_display.page_labels[key]

                        # 更新显示
                        self.update_labels_list()
                        self.content_display.update()

                        # 显示删除成功提示
                        self.statusBar().showMessage("标签已删除", 2000)

        except Exception as e:
            print(f"删除标签时出错: {e}")
            QMessageBox.warning(self, "错误", f"删除标签失败: {str(e)}")

    def display_current_page(self):
        """显示当前页面"""
        # ... 现有的显示代码 ...
        self.load_labels()  # 加载标签

    def goto_label(self, item):
        """转到标签所在页面"""
        if not item.parent():  # 如果点击的是页码项
            page = int(item.text(0).split()[1]) - 1
            self.current_page = page
            self.show_current_page()
        else:  # 如果点击的是标签项
            label_data = item.data(0, Qt.ItemDataRole.UserRole)
            if label_data:
                # 跳转到标签所页面
                self.current_page = label_data['page']
                self.show_current_page()

                # 亮显示标签（可选）
                self.content_display.highlight_label = label_data
                self.content_display.update()

                # 3秒后取消高亮（可选）
                QTimer.singleShot(3000, lambda: self.clear_highlight())

    def clear_highlight(self):
        """清除标签高亮"""
        if hasattr(self.content_display, 'highlight_label'):
            self.content_display.highlight_label = None
            self.content_display.update()

    def convert_and_open_ebook(self, file_path):
        """转换并打开电子书"""
        try:
            # 显示转换提示
            self.statusBar().showMessage("正在转换电子书格式...", 2000)
            QApplication.processEvents()

            # 创建临时PDF文件路径
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_pdf')
            os.makedirs(temp_dir, exist_ok=True)
            pdf_path = os.path.join(temp_dir, os.path.basename(file_path) + '.pdf')

            # 如果已经有转换好的PDF，直接打开
            if os.path.exists(pdf_path):
                self.current_doc = fitz.open(pdf_path)
                self.current_page = 0
                self.show_current_page()
                return

            # 使用 calibre 的命令行工具转换
            try:
                import subprocess
                # 添加转换参数以优化输出质量
                cmd = [
                    'ebook-convert',
                    file_path,
                    pdf_path,
                    '--pdf-page-numbers',
                    '--paper-size', 'a4',
                    '--pdf-default-font-size', '12',
                    '--pdf-serif-family', 'Times New Roman',
                    '--pdf-sans-family', 'Arial',
                    '--pdf-mono-family', 'Courier New',
                    '--preserve-cover-aspect-ratio'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    self.current_doc = fitz.open(pdf_path)
                    self.current_page = 0
                    self.show_current_page()
                else:
                    raise Exception(f"转换失败: {result.stderr}")

            except FileNotFoundError:
                QMessageBox.warning(
                    self,
                    '错误',
                    '未找到 ebook-convert 工具。请安装 Calibre 软件。\n'
                    '下载地址: https://calibre-ebook.com/download\n'
                    '安装后需要重启程序。'
                )
                return

        except Exception as e:
            QMessageBox.warning(self, '错误', f'转换电子书失败: {str(e)}')
            print(f"转换电子详细错误: {e}")

    def undo_mark(self):
        """撤销上一次标记"""
        try:
            if self.content_display.marks_history:
                # 获取上一次的标记状态
                previous_marks = self.content_display.marks_history.pop()

                # 更新当前标记
                self.content_display.marks = previous_marks

                # 更新数据库
                if self.current_book_path:
                    book_id = self.books[self.current_book_path]['id']

                    # 删除当前页面的标记
                    self.cursor.execute('DELETE FROM marks WHERE book_id = ? AND page = ?',
                                        (book_id, self.current_page))

                    # 插入撤销后的标记
                    for mark in previous_marks:
                        self.cursor.execute(
                            '''INSERT INTO marks 
                               (book_id, page, start_x, start_y, end_x, end_y, color, width)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (book_id, self.current_page,
                             mark['start'].x(), mark['start'].y(),
                             mark['end'].x(), mark['end'].y(),
                             mark['color'].name(), mark['width'])
                        )

                    self.conn.commit()

                    # 更新显示
                    self.content_display.update()
                    self.statusBar().showMessage("已撤销上一次标记", 2000)
            else:
                self.statusBar().showMessage("没有可撤销的标记", 2000)

        except Exception as e:
            print(f"撤销标记时出错: {e}")
            QMessageBox.warning(self, "错误", f"撤销标记失败: {str(e)}")

    def undo_label(self):
        """撤销上一次标签"""
        try:
            # 获取当前页面的键值
            page_key = f"{self.current_book_path}_{self.current_page}"

            if page_key in self.content_display.page_labels and self.content_display.page_labels[page_key]:
                # 只删除最后一个标签
                removed_label = self.content_display.page_labels[page_key].pop()

                # 如果页面没有标签了，删除整个页面的记录
                if not self.content_display.page_labels[page_key]:
                    del self.content_display.page_labels[page_key]

                # 更新数据库 - 只删除最后一个标签
                if self.current_book_path:
                    book_id = self.books[self.current_book_path]['id']

                    # 删除数据库中的最后一个标签
                    sql = '''DELETE FROM labels WHERE id = (
                        SELECT id FROM labels 
                        WHERE book_id = ? AND page = ? AND text = ? AND pos_x = ? AND pos_y = ? 
                        ORDER BY id DESC LIMIT 1)'''
                    params = (book_id, self.current_page, removed_label['text'],
                              removed_label['pos'].x(), removed_label['pos'].y())
                    self.cursor.execute(sql, params)

                    self.conn.commit()

                    # 更新显示 - 只在最后更新一次
                    self.content_display.update()
                    self.update_label_tree_item(page_key)  # 只更新当前页面的标签树
                    self.statusBar().showMessage("已撤销上一个标签", 2000)
                else:
                    self.statusBar().showMessage("当前页面没有可撤销的标签", 2000)

        except Exception as e:
            print(f"撤销标签时出错: {e}")
            QMessageBox.warning(self, "错误", f"撤销标签失败: {str(e)}")

    def update_label_tree_item(self, page_key):
        """更新特定页面的标签树项"""
        try:
            # 找到对应的页面项
            page = int(page_key.split('_')[-1])
            page_text = f"第 {page + 1} 页"

            # 查找或创建页面项
            page_item = None
            for i in range(self.label_tree.topLevelItemCount()):
                item = self.label_tree.topLevelItem(i)
                if item.text(0) == page_text:
                    page_item = item
                    break

            if page_item:
                # 清除现有子项
                page_item.takeChildren()

                # 如果页面还有标签，添加新的子项
                if page_key in self.content_display.page_labels:
                    for label in self.content_display.page_labels[page_key]:
                        label_item = QTreeWidgetItem(page_item)
                        label_item.setText(0, label['text'])
                        label_item.setData(0, Qt.ItemDataRole.UserRole, {
                            'page': page,
                            'text': label['text'],
                            'pos': label['pos'],
                            'color': label['color'],
                            'font_size': label['font_size']
                        })
                else:
                    # 如果页面没有标签了，删除页面项
                    index = self.label_tree.indexOfTopLevelItem(page_item)
                    self.label_tree.takeTopLevelItem(index)

        except Exception as e:
            print(f"更新标签树项时出错: {e}")

    def save_labels(self):
        """保存标签到数据库"""
        try:
            if self.current_book_path:
                book_id = self.books[self.current_book_path]['id']

                # 删除该书籍的所有标签
                self.cursor.execute('DELETE FROM labels WHERE book_id =?', (book_id,))

                # 保存所有页面的标签
                for key, labels in self.content_display.page_labels.items():
                    if key.startswith(self.current_book_path):
                        try:
                            page = int(key.split('_')[-1])
                            for label in labels:
                                self.cursor.execute(
                                    'INSERT INTO labels (book_id, page, text, pos_x, pos_y, color, font_size) VALUES (?,?,?,?,?,?,?)',
                                    (book_id, page,
                                     label['text'],
                                     label['pos'].x(), label['pos'].y(),
                                     label['color'].name(),
                                     label['font_size'])
                                )
                        except (ValueError, IndexError) as e:
                            print(f"保存标签时出错: {e}, key: {key}")
                            continue

                # 提交事务
                self.conn.commit()
                print("标签已保存到数据库")

        except Exception as e:
            print(f"保存标签失败: {e}")
            QMessageBox.warning(self, "错误", f"保存标签失败: {str(e)}")


def main():
    app = QApplication(sys.argv)
    manager = EbookManager()
    manager.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
