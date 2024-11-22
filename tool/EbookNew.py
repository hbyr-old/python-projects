import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QMenu, QDialog, QLabel, QTextEdit,
                             QScrollArea, QColorDialog, QMessageBox, QSplitter, QFileDialog, QProgressBar)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QAction
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

        # 添加以下代码，使标签可以接收键盘焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 添加以下代码，设置滚动步长
        self.scroll_step = 50  # 每次滚动的像素值

    def mousePressEvent(self, event):
        main_window = self.get_main_window()
        if event.button() == Qt.MouseButton.LeftButton and main_window and main_window.marking_enabled:
            self.drawing = True
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        main_window = self.get_main_window()
        if self.drawing and main_window and main_window.marking_enabled:
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
            # 立即保存标记到当前页面
            if self.current_page_key:
                self.page_marks[self.current_page_key] = self.marks.copy()
                main_window.save_marks()  # 立即保存到文件

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            # 保存标记
            self.save_current_marks()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        for mark in self.marks:
            pen = QPen(mark['color'], mark['width'])
            painter.setPen(pen)
            painter.drawLine(mark['start'], mark['end'])

    def clear_marks(self):
        """清除所有标记"""
        self.marks = []
        if self.current_page_key and self.current_page_key in self.page_marks:
            del self.page_marks[self.current_page_key]
        self.update()

    def set_current_page(self, page_key):
        """设置当前页面，加载对应的标记"""
        self.current_page_key = page_key
        self.marks = []

        if page_key in self.page_marks:
            # 创建深拷贝以避免引用问题
            for mark in self.page_marks[page_key]:
                self.marks.append({
                    'start': QPoint(mark['start'].x(), mark['start'].y()),
                    'end': QPoint(mark['end'].x(), mark['end'].y()),
                    'color': QColor(mark['color'].name()),
                    'width': mark['width']
                })
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
                    # 获取当前垂直滚动条的值
                    current = scroll_area.verticalScrollBar().value()
                    # 向上滚动
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


class EbookManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.epub', '.pdf', '.txt']
        self.books = {}  # 存储书籍信息
        self.notes = {}  # 存储笔记信息
        self.current_doc = None  # 当前打开的文档
        self.current_page = 0  # 当前页码
        self.current_book_path = None  # 当前打开的书籍路径
        self.page_marks = {}  # 存储每页的标记
        self.zoom_factor = 1.0  # 缩放因子
        self.min_zoom = 0.1  # 最小缩放
        self.max_zoom = 5.0  # 最大缩放
        self.booklist_visible = True  # 书籍列表显示状态
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

    def initial_file_check(self):
        """系统启动时检查文件是否存在"""
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
            status_label = QLabel("正在检查文件完整性...", progress)
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

            # 如果有文件不存在，删除相关数据
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

                # 更新界面
                self.update_book_tree()
                self.update_notes_list()

                # 显示结果
                QMessageBox.warning(self, "文件检查结果",
                                    f"检测到 {len(deleted_paths)} 个文件已不存在，相关数据已清理。")

            # 关闭进度对话框
            progress.close()

            print(f"初始文件检查完成，删除了 {len(deleted_paths)} 个不存在文件的数据")

        except Exception as e:
            print(f"初始文件检查时出错: {e}")

    def init_ui(self):
        self.setWindowTitle('晓阅')
        self.setGeometry(100, 100, 1200, 800)

        # 主窗口布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 创建分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # 左侧面板
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
        import_btn.clicked.connect(self.import_books)
        search_layout.addWidget(import_btn)

        left_layout.addLayout(search_layout)

        # 书籍列
        self.book_tree = QTreeWidget()
        self.book_tree.setHeaderLabels(['书籍'])
        self.book_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.book_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.book_tree.customContextMenuRequested.connect(self.show_book_menu)
        left_layout.addWidget(self.book_tree)

        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 工具栏
        self.toolbar = QHBoxLayout()

        # 显示/隐藏书籍列表按钮
        self.toggle_booklist_btn = QPushButton('隐藏书籍列表')
        self.toggle_booklist_btn.clicked.connect(self.toggle_booklist)
        self.toolbar.addWidget(self.toggle_booklist_btn)

        # 页面导航
        self.prev_btn = QPushButton('上一页')
        self.next_btn = QPushButton('下一页')

        # 页码显跳
        self.current_page_label = QLabel('0/0')  # 显示前页码
        self.current_page_label.setFixedWidth(50)
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(50)
        self.page_input.setPlaceholderText('页码')
        self.goto_btn = QPushButton('跳转')

        # 缩放控制
        self.zoom_in_btn = QPushButton('放大')
        self.zoom_out_btn = QPushButton('缩小')
        self.zoom_label = QLabel('100%')
        self.zoom_label.setFixedWidth(40)

        # # 当前书籍名称
        # self.current_book_label = QLabel()
        # self.current_book_label.setStyleSheet("font-weight: bold;")

        # 其他按钮
        self.save_button = QPushButton("保存标记")
        self.save_button.hide()  # 隐藏
        self.toolbar.addWidget(self.save_button)
        self.color_btn = QPushButton('标记颜色')
        self.clear_marks_btn = QPushButton('清除标记')
        # 添加保存按��到工具栏
        self.add_note_btn = QPushButton('添加笔记')

        # 连接信号
        self.save_button.clicked.connect(self.save_drawings)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.goto_btn.clicked.connect(self.goto_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.add_note_btn.clicked.connect(self.add_note)
        self.color_btn.clicked.connect(self.choose_color)
        self.clear_marks_btn.clicked.connect(self.clear_current_marks)

        # 添加到工具栏
        self.toolbar.addWidget(self.prev_btn)
        self.toolbar.addWidget(self.next_btn)
        self.toolbar.addWidget(self.current_page_label)
        self.toolbar.addWidget(self.page_input)
        self.toolbar.addWidget(self.goto_btn)
        self.toolbar.addWidget(self.zoom_out_btn)
        self.toolbar.addWidget(self.zoom_label)
        self.toolbar.addWidget(self.zoom_in_btn)
        #self.toolbar.addWidget(self.current_book_label)
        self.toolbar.addWidget(self.add_note_btn)
        self.toolbar.addWidget(self.color_btn)
        self.toolbar.addWidget(self.clear_marks_btn)

        right_layout.addLayout(self.toolbar)

        # 创���可标记的阅读区域
        scroll_area = QScrollArea()
        self.content_display = MarkableLabel()
        self.content_display.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_display.setFocus()  # 设置初始焦点
        scroll_area.setWidget(self.content_display)
        scroll_area.setWidgetResizable(True)
        right_layout.addWidget(scroll_area)

        # 笔记面板
        self.notes_panel = QWidget()
        notes_layout = QVBoxLayout(self.notes_panel)

        # 笔记列表
        self.notes_list = QTreeWidget()
        self.notes_list.setHeaderLabels(['笔记'])
        self.notes_list.itemDoubleClicked.connect(self.view_note)
        notes_layout.addWidget(self.notes_list)

        # 添加到右侧布局
        right_layout.addWidget(self.notes_panel)
        self.notes_panel.hide()  # 默认隐藏笔记面板

        # 添加显示/隐藏笔记按钮
        self.toggle_notes_btn = QPushButton('显示笔记')
        self.toggle_notes_btn.clicked.connect(self.toggle_notes_panel)
        self.toolbar.addWidget(self.toggle_notes_btn)

        # 添加到分割器
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(1, 2)

        # 设置样式
        self.setStyleSheet("""
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)

    def init_database(self):
        """初始化数据库"""
        try:
            db_path = Path('library.db')
            self.conn = sqlite3.connect(str(db_path))
            self.cursor = self.conn.cursor()

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

            # 启用外键约束
            self.cursor.execute('PRAGMA foreign_keys = ON')

            self.conn.commit()
        except Exception as e:
            print(f"初始化数据库失败: {e}")

    def load_library(self):
        """从数库加载书库"""
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
            # 不再删除所有记录，而是更新现有记录或插入新记录
            for path, info in self.books.items():
                if 'id' in info:  # 如果已有ID，更新记录
                    self.cursor.execute(
                        '''UPDATE books 
                           SET title = ?, format = ?, size = ?
                           WHERE id = ?''',
                        (info['title'], info['format'], info['size'], info['id'])
                    )
                else:  # 如果是新记录，插入
                    self.cursor.execute(
                        '''INSERT INTO books (path, title, format, size)
                           VALUES (?, ?, ?, ?)''',
                        (path, info['title'], info['format'], info['size'])
                    )
                    # 获取新插入记录的ID
                    info['id'] = self.cursor.lastrowid
            self.conn.commit()
        except Exception as e:
            print(f"存书库失败: {e}")

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
            self.cursor.execute('DELETE FROM notes')
            for book_path, notes in self.notes.items():
                book_id = self.books[book_path]['id']
                for note in notes:
                    self.cursor.execute(
                        'INSERT INTO notes (book_id, content, page, timestamp) VALUES (?, ?, ?, ?)',
                        (book_id, note['content'], note['page'], note['timestamp'])
                    )
            self.conn.commit()
        except Exception as e:
            print(f"保存笔记失败: {e}")

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

            print("从数据库加载标记完成")
        except Exception as e:
            print(f"从数据库加载标记失败: {e}")
            self.page_marks = {}
            if hasattr(self, 'content_display'):
                self.content_display.page_marks = {}

    def save_marks(self):
        """保存标记到数据库"""
        try:
            self.cursor.execute('DELETE FROM marks')
            for key, marks in self.page_marks.items():
                book_path, page = key.rsplit('_', 1)
                book_id = self.books[book_path]['id']
                for mark in marks:
                    self.cursor.execute(
                        '''INSERT INTO marks 
                           (book_id, page, start_x, start_y, end_x, end_y, color, width)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (book_id, int(page),
                         mark['start'].x(), mark['start'].y(),
                         mark['end'].x(), mark['end'].y(),
                         mark['color'].name(), mark['width'])
                    )
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
            print(f"加载缩放状态失败: {e}")

    def save_zoom_states(self):
        """保存缩放状态到数据库"""
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
            print(f"保存缩放状态失败: {e}")

    def closeEvent(self, event):
        """程序关闭时的处理"""
        try:
            # 保存当前页面的标记到数据库
            if self.current_book_path and self.marking_enabled:
                try:
                    book_id = self.books[self.current_book_path]['id']
                    # 先删除当前页面的标记
                    self.cursor.execute('DELETE FROM marks WHERE book_id = ? AND page = ?',
                                        (book_id, self.current_page))

                    # 插入新标记
                    for mark in self.content_display.marks:
                        self.cursor.execute(
                            '''INSERT INTO marks 
                               (book_id, page, start_x, start_y, end_x, end_y, color, width)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
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
            self.toggle_booklist_btn.setText('显示书列表')
        else:
            self.left_panel.show()
            self.toggle_booklist_btn.setText('隐藏书籍列表')
        self.booklist_visible = not self.booklist_visible

    def import_books(self):
        """导入书籍"""
        folder = QFileDialog.getExistingDirectory(self, '选择书籍文件夹')
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
            QMessageBox.warning(self, '错误', f'添加书籍失败: {str(e)}')

    def get_book_info(self, file_path):
        """获取书籍信息"""
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
        """更新书籍树形显示"""
        self.book_tree.clear()

        # 按格式分组
        formats = {}
        for book in self.books.values():
            fmt = book['format']
            if fmt not in formats:
                formats[fmt] = []
            formats[fmt].append(book)

        # 添到树形结构
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

    # 修改 open_book 法
    def open_book(self, item):
        """打开书籍"""
        if not item.parent():
            return

        # 保存之前书籍的标记到数据库
        if self.current_book_path and self.marking_enabled:
            try:
                # 先删除当前页面的旧标记
                self.cursor.execute('DELETE FROM marks WHERE book_path = ? AND page = ?',
                                    (self.current_book_path, self.current_page))

                # 插入新标记
                for mark in self.content_display.marks:
                    self.cursor.execute(
                        '''INSERT INTO marks 
                           (book_path, page, start_x, start_y, end_x, end_y, color, width)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (self.current_book_path, self.current_page,
                         mark['start'].x(), mark['start'].y(),
                         mark['end'].x(), mark['end'].y(),
                         mark['color'].name(), mark['width'])
                    )

                # 提交事务
                self.conn.commit()
                print(f"保存了 {len(self.content_display.marks)} 个标记到数据库")
            except Exception as e:
                print(f"保存标记到数据库时出错: {e}")

        # 保存之前书籍的绘图
        if self.current_book_path and self.marking_enabled:
            self.save_drawings()

        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.exists(file_path):
            QMessageBox.warning(self, '错误', '文件不存在！')
            return

        try:
            self.current_book_path = file_path
            self.zoom_factor = self.zoom_states.get(file_path, 1.0)
            self.update_zoom_label()

            # 清除当前显示的标记
            self.content_display.marks = []
            self.current_page = 0  # 重置页码

            # 先加载标记数据
            self.load_marks()

            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                self.open_pdf(file_path)
            elif ext == '.epub':
                self.open_epub(file_path)
            elif ext == '.txt':
                self.open_txt(file_path)
            else:
                QMessageBox.warning(self, '错误', f'不支持的文件格式: {ext}')
                return

            # 更新窗口标题为书籍名称
            if file_path in self.books:
                book_title = self.books[file_path]['title']
                # 设置窗口标题为：电子书管理系统 - 书籍名称
                self.setWindowTitle(f"晓阅 - 阅我所悦，享受时光 - {book_title}")

            # 加载当前页面的标记
            key = f"{file_path}_{self.current_page}"
            if key in self.page_marks:
                # 创建深拷贝以避免引用问题
                self.content_display.marks = []
                for mark in self.page_marks[key]:
                    self.content_display.marks.append({
                        'start': QPoint(mark['start'].x(), mark['start'].y()),
                        'end': QPoint(mark['end'].x(), mark['end'].y()),
                        'color': QColor(mark['color'].name()),
                        'width': mark['width']
                    })

            # 设置当前页面键值
            self.content_display.current_page_key = key

            # 显示当前页面（包括标记）
            self.show_current_page()

            # 确保阅读框获得焦点
            self.content_display.setFocus()

            # 更新笔记列表
            self.update_notes_list()

        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开文件失败: {str(e)}')
            print(f"打开文件详细错误: {e}")  # 详细错误信息

    def open_pdf(self, file_path):
        """打开PDF文件"""
        try:
            self.current_doc = fitz.open(file_path)
            self.current_page = 0
            self.show_current_page()
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开PDF失败: {str(e)}')

    def open_epub(self, file_path):
        """打开EPUB文件"""
        try:
            # 显示加载提示
            self.statusBar().showMessage("正在转换电子书格式...", 2000)
            QApplication.processEvents()

            # 创建临时PDF文件路径
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
            print(f"打开EPUB详细错误: {e}")

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

                # 继续加载后面的页面
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

            # 尝试不同的编码方式打开文件
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

            # 设置基本样式，添加自动换行和宽度限制
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
            error_msg = f"打开TXT文件失败: {str(e)}"
            QMessageBox.warning(self, '错误', error_msg)
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

                    # 加载当前页面的标记
                    key = f"{self.current_book_path}_{self.current_page}"
                    print(f"当前页面键值: {key}")
                    print(f"可用的标记: {self.page_marks.get(key, [])}")

                    self.content_display.marks = []
                    if key in self.page_marks:
                        for mark in self.page_marks[key]:
                            new_mark = {
                                'start': QPoint(mark['start'].x(), mark['start'].y()),
                                'end': QPoint(mark['end'].x(), mark['end'].y()),
                                'color': QColor(mark['color'].name()),
                                'width': mark['width']
                            }
                            self.content_display.marks.append(new_mark)
                        print(f"已加载标记数量: {len(self.content_display.marks)}")

                    self.content_display.current_page_key = key
                    self.content_display.update()

                    # 检查是否需要预加载更多页面
                    QTimer.singleShot(100, self.check_and_preload)

            elif isinstance(self.current_doc, epub.EpubBook):  # EPUB
                if 0 <= self.current_page < len(self.epub_items):
                    # 更新页码显示
                    self.current_page_label.setText(f"{self.current_page + 1}/{len(self.epub_items)}")

                    # 显示加载提示
                    self.statusBar().showMessage("正在加载页面...", 1000)
                    QApplication.processEvents()

                    # 获取内容
                    content = None
                    if self.current_page in self.page_cache:
                        cache_data = self.page_cache[self.current_page]
                        if not cache_data['processed']:
                            content = self.process_epub_images(cache_data['content'],
                                                               self.epub_items[self.current_page])
                            cache_data['content'] = content
                            cache_data['processed'] = True
                        else:
                            content = cache_data['content']

                    if content is None:
                        # 如果当前页面未缓存，立即加载
                        item = self.epub_items[self.current_page]
                        content = item.get_content().decode('utf-8')
                        content = self.process_epub_images(content, item)

                    # 设置基本样式
                    styled_content = f"""
                        <html>
                        <head>
                            <style>
                                body {{
                                    font-family: Arial, sans-serif;
                                    font-size: 14px;
                                    line-height: 1.6;
                                    margin: 20px;
                                    background-color: white;
                                }}
                                img {{
                                    max-width: 100%;
                                    height: auto;
                                }}
                            </style>
                        </head>
                        <body>
                            {content}
                        </body>
                        </html>
                    """

                    self.content_display.setTextFormat(Qt.TextFormat.RichText)
                    self.content_display.setText(styled_content)

                    # 加载当前页面的标记
                    key = f"{self.current_book_path}_{self.current_page}"
                    print(f"当前页面键值: {key}")
                    print(f"可用的标记: {self.page_marks.get(key, [])}")

                    self.content_display.marks = []
                    if key in self.page_marks:
                        for mark in self.page_marks[key]:
                            new_mark = {
                                'start': QPoint(mark['start'].x(), mark['start'].y()),
                                'end': QPoint(mark['end'].x(), mark['end'].y()),
                                'color': QColor(mark['color'].name()),
                                'width': mark['width']
                            }
                            self.content_display.marks.append(new_mark)
                        print(f"已加载标记数量: {len(self.content_display.marks)}")

                    self.content_display.current_page_key = key
                    self.content_display.update()

                    # 检查是否需要预加载更多页面
                    QTimer.singleShot(100, self.check_and_preload)

        except Exception as e:
            print(f"显示当前页面时出错: {e}")

    def process_epub_images(self, content, item):
        """处理EPUB中的图片路径"""
        try:
            # 查是否已经处理过
            if hasattr(self, 'processed_images') and item.file_name in self.processed_images:
                return self.processed_images[item.file_name]

            # 获取当前文件的目录
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
                                    print(f"保图片失败: {e}")
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
                # 先保存前页面的标记
                if self.marking_enabled:
                    self.content_display.save_current_marks()
                    QApplication.processEvents()  # 让界面响应
                    self.save_marks()

                self.current_page -= 1
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
                    self.show_current_page()
                else:
                    QMessageBox.warning(self, '警告', '页码超范围！')
        except ValueError:
            QMessageBox.warning(self, '警告', '请输入有效的页码！')

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
                # 禁用标记前先保存
                if self.current_book_path:
                    self.save_drawings()

                # 禁用标记
                self.marking_enabled = False
                self.color_btn.setText('标记颜色')
                self.content_display.setMouseTracking(False)
                # 隐藏保存按钮并停止自动保存
                self.save_button.hide()
                self.auto_save_timer.stop()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"切换标记模式时出错: {str(e)}")

    def clear_current_marks(self):
        """清除当前页面的标记"""
        self.content_display.clear_marks()
        if self.current_book_path and self.current_page is not None:
            key = f"{self.current_book_path}_{self.current_page}"
            if key in self.page_marks:
                del self.page_marks[key]
                self.save_marks()

    def save_current_marks(self):
        """保存当前面的标记"""
        if self.current_book_path and self.current_page is not None:
            key = f"{self.current_book_path}_{self.current_page}"
            self.page_marks[key] = self.content_display.marks.copy()
            self.save_marks()

    def add_note(self):
        """添加笔记"""
        if not self.current_book_path:
            QMessageBox.warning(self, '警告', '请先打开一本书！')
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('添加笔记')
        dialog.setFixedWidth(400)

        layout = QVBoxLayout(dialog)

        # 笔记内容输入
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
        self.notes_list.clear()
        if self.current_book_path and self.current_book_path in self.notes:
            for note in self.notes[self.current_book_path]:
                item = QTreeWidgetItem(self.notes_list)
                item.setText(0, f"第{note['page'] + 1}页 - {note['timestamp']}")
                item.setData(0, Qt.ItemDataRole.UserRole, note)

    def view_note(self, item):
        """查看和编辑记"""
        note = item.data(0, Qt.ItemDataRole.UserRole)
        if note:
            dialog = QDialog(self)
            dialog.setWindowTitle('查看/编辑笔记')
            dialog.setFixedWidth(400)

            layout = QVBoxLayout(dialog)

            # 笔记信息
            info_label = QLabel(f"页码：第{note['page'] + 1}页\n时间：{note['timestamp']}")
            layout.addWidget(info_label)

            # 笔记内容 - 改为可编辑
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
                    # 找到当前记在列表中的索引
                    note_list = self.notes[self.current_book_path]
                    note_index = note_list.index(note)

                    # 更新笔记内容
                    note_list[note_index]['content'] = content_edit.toPlainText()
                    # 更新时间戳
                    note_list[note_index]['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # 保存到文件
                    self.save_notes()
                    # 更新列表显示
                    self.update_notes_list()
                    # 显示保存成功提示
                    self.statusBar().showMessage("笔记已保存", 2000)
                    # 关闭对话框
                    dialog.accept()
                except Exception as e:
                    print(f"保存笔记修改时出错: {e}")
                    QMessageBox.warning(self, "错误", "保存笔记失败")

            save_btn.clicked.connect(save_changes)
            button_layout.addWidget(save_btn)

            # 删除按钮
            delete_btn = QPushButton('删除')
            delete_btn.clicked.connect(lambda: self.delete_note(note, dialog))
            button_layout.addWidget(delete_btn)

            # 关闭按钮
            close_btn = QPushButton('关闭')
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)

            layout.addLayout(button_layout)

            dialog.exec()

    def delete_note(self, note, dialog):
        """删除笔记"""
        reply = QMessageBox.question(self, '确认删',
                                     '确定要删除这条笔记吗？',
                                     QMessageBox.StandardButton.Yes |
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # 从笔记表中删除
            self.notes[self.current_book_path].remove(note)
            if not self.notes[self.current_book_path]:
                del self.notes[self.current_book_path]

            self.save_notes()
            self.update_notes_list()
            dialog.accept()

    def toggle_notes_panel(self):
        """切换笔记面板显示状态"""
        if self.notes_panel.isHidden():
            self.notes_panel.show()
            self.toggle_notes_btn.setText('隐藏笔记')
        else:
            self.notes_panel.hide()
            self.toggle_notes_btn.setText('显示笔记')

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
        """显示书右键菜"""
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
                # 删除书籍（级联删除会自动删除相关的笔记、标记和缩放状态）
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
                print(f"删除书籍失败: {e}")
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
                if self.content_display.marks:  # 如果有标记
                    for mark in self.content_display.marks:
                        self.cursor.execute(
                            '''INSERT INTO marks 
                               (book_id, page, start_x, start_y, end_x, end_y, color, width)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (book_id, self.current_page,
                             mark['start'].x(), mark['start'].y(),
                             mark['end'].x(), mark['end'].y(),
                             mark['color'].name(), mark['width'])
                        )

                    # 提交事务
                    self.conn.commit()

                    # 更新内存中的标记
                    key = f"{self.current_book_path}_{self.current_page}"
                    self.page_marks[key] = self.content_display.marks.copy()

                    # 显示临时提示
                    self.statusBar().showMessage("绘图已保存", 2000)
                    print(f"保存了 {len(self.content_display.marks)} 个标记到数据库")

        except Exception as e:
            print(f"保存绘图到数据库时出错: {str(e)}")
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
            print(f"加载剩余项目时出错: {e}")

    def keyPressEvent(self, event):
        """处理键盘事件"""
        try:
            if event.key() == Qt.Key.Key_Left:  # 左方向键
                self.prev_page()
            elif event.key() == Qt.Key.Key_Right:  # 右方向键
                self.next_page()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            print(f"处理键盘事件时出错: {e}")


def main():
    app = QApplication(sys.argv)
    manager = EbookManager()
    manager.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
