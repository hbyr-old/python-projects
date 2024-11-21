import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QMenu, QDialog, QLabel, QTextEdit,
                             QScrollArea, QColorDialog, QMessageBox, QSplitter, QFileDialog)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QAction
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
import json
import re
from datetime import datetime


class MarkableLabel(QLabel):
    """可以手写标记的标签"""

    def __init__(self):
        super().__init__()
        self.drawing = False
        self.last_point = None
        self.marks = []  # 存储标记
        self.current_color = QColor(Qt.GlobalColor.red)  # 默认红色
        self.current_width = 2  # 默认线宽

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if self.drawing:
            current_point = event.pos()
            self.marks.append({
                'start': self.last_point,
                'end': current_point,
                'color': self.current_color,
                'width': self.current_width
            })
            self.last_point = current_point
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False

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
        self.update()


class EbookManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.epub', '.pdf', '.mobi', '.azw', '.azw3', '.txt']
        self.books = {}  # 存储书籍信息
        self.notes = {}  # 存储笔记信息
        self.current_doc = None  # 当前打开的文档
        self.current_page = 0  # 当前页码
        self.current_book_path = None  # 当前打开的书籍路径
        self.page_marks = {}  # 存储每页的标记
        self.zoom_factor = 1.0  # 缩放因子
        self.min_zoom = 0.1  # 最小缩放
        self.max_zoom = 5.0  # 最大缩放
        self.init_ui()
        self.load_library()
        self.load_notes()
        self.load_marks()

    def init_ui(self):
        self.setWindowTitle('电子书管理系统')
        self.setGeometry(100, 100, 1200, 800)

        # 主窗口布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

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

        # 书籍列表
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
        toolbar = QHBoxLayout()

        # 页面导航
        self.prev_btn = QPushButton('上一页')
        self.next_btn = QPushButton('下一页')

        # 页码显示和跳转
        page_nav_layout = QHBoxLayout()
        self.current_page_label = QLabel('0/0')  # 显示当前页码
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(50)
        self.page_input.setPlaceholderText('页码')
        self.goto_btn = QPushButton('跳转')

        # 缩放控制
        self.zoom_in_btn = QPushButton('放大')
        self.zoom_out_btn = QPushButton('缩小')
        self.zoom_label = QLabel('100%')

        # 其他按钮
        self.add_note_btn = QPushButton('添加笔记')
        self.color_btn = QPushButton('标记颜色')
        self.clear_marks_btn = QPushButton('清除标记')

        # 连接信号
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.goto_btn.clicked.connect(self.goto_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.add_note_btn.clicked.connect(self.add_note)
        self.color_btn.clicked.connect(self.choose_color)
        self.clear_marks_btn.clicked.connect(self.clear_current_marks)

        # 添加到工具栏
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)
        toolbar.addWidget(self.current_page_label)
        toolbar.addWidget(self.page_input)
        toolbar.addWidget(self.goto_btn)
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addWidget(self.add_note_btn)
        toolbar.addWidget(self.color_btn)
        toolbar.addWidget(self.clear_marks_btn)

        right_layout.addLayout(toolbar)

        # 创建可标记的阅读区域
        scroll_area = QScrollArea()
        self.content_display = MarkableLabel()
        self.content_display.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
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
        toolbar.addWidget(self.toggle_notes_btn)

        # 添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 2)

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

    def load_library(self):
        """加载书库"""
        try:
            with open('library.json', 'r', encoding='utf-8') as f:
                self.books = json.load(f)
            self.update_book_tree()
        except FileNotFoundError:
            self.books = {}

    def load_notes(self):
        """加载笔记"""
        try:
            with open('notes.json', 'r', encoding='utf-8') as f:
                self.notes = json.load(f)
        except FileNotFoundError:
            self.notes = {}

    def load_marks(self):
        """加载标记"""
        try:
            with open('marks.json', 'r', encoding='utf-8') as f:
                marks_data = json.load(f)

            for key, marks in marks_data.items():
                self.page_marks[key] = [
                    {
                        'start': QPoint(mark['start'][0], mark['start'][1]),
                        'end': QPoint(mark['end'][0], mark['end'][1]),
                        'color': QColor(mark['color']),
                        'width': mark['width']
                    }
                    for mark in marks
                ]
        except FileNotFoundError:
            self.page_marks = {}
        except Exception as e:
            print(f"加载标记失败: {e}")

    def save_library(self):
        """保存书库信息"""
        with open('library.json', 'w', encoding='utf-8') as f:
            json.dump(self.books, f, ensure_ascii=False, indent=2)

    def save_notes(self):
        """保存笔记"""
        with open('notes.json', 'w', encoding='utf-8') as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)

    def save_marks(self):
        """保存标记"""
        try:
            marks_data = {}
            for key, marks in self.page_marks.items():
                marks_data[key] = [
                    {
                        'start': (mark['start'].x(), mark['start'].y()),
                        'end': (mark['end'].x(), mark['end'].y()),
                        'color': mark['color'].name(),
                        'width': mark['width']
                    }
                    for mark in marks
                ]

            with open('marks.json', 'w', encoding='utf-8') as f:
                json.dump(marks_data, f)
        except Exception as e:
            print(f"保存标记失败: {e}")

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
        """添加书籍到库"""
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

        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.exists(file_path):
            QMessageBox.warning(self, '错误', '文件不存在！')
            return

        try:
            self.current_book_path = file_path
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                self.open_pdf(file_path)
            elif ext == '.epub':
                self.open_epub(file_path)
            elif ext == '.txt':
                self.open_txt(file_path)
            else:
                QMessageBox.warning(self, '错误', f'不支持的文件格式: {ext}')

            # 更新笔记列表
            self.update_notes_list()

        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开文件失败: {str(e)}')

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
            self.current_doc = epub.read_epub(file_path)
            self.current_page = 0
            self.show_current_page()
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开EPUB失败: {str(e)}')

    def open_txt(self, file_path):
        """打开TXT文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.content_display.setText(content)
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打开TXT失败: {str(e)}')

    def show_current_page(self):
        """显示当前页面"""
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

                # 加载标记
                key = f"{self.current_book_path}_{self.current_page}"
                if key in self.page_marks:
                    self.content_display.marks = self.page_marks[key]
                else:
                    self.content_display.marks = []

        elif isinstance(self.current_doc, epub.EpubBook):  # EPUB
            items = list(self.current_doc.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            if 0 <= self.current_page < len(items):
                content = items[self.current_page].get_content().decode('utf-8')
                content = content.replace('<p>', '\n').replace('</p>', '\n')
                content = content.replace('<br>', '\n')
                content = re.sub('<[^<]+?>', '', content)

                # 创建图像以显示文本
                pixmap = QPixmap(self.content_display.size())
                pixmap.fill(Qt.GlobalColor.white)
                painter = QPainter(pixmap)
                painter.drawText(pixmap.rect(), Qt.TextFlag.TextWordWrap, content)
                painter.end()
                self.content_display.setPixmap(pixmap)

                # 加载标记
                key = f"{self.current_book_path}_{self.current_page}"
                if key in self.page_marks:
                    self.content_display.marks = self.page_marks[key]
                else:
                    self.content_display.marks = []

    def prev_page(self):
        """上一页"""
        if self.current_doc and self.current_page > 0:
            self.save_current_marks()
            self.current_page -= 1
            self.show_current_page()

    def next_page(self):
        """下一页"""
        if self.current_doc:
            if isinstance(self.current_doc, fitz.Document):
                if self.current_page < len(self.current_doc) - 1:
                    self.save_current_marks()
                    self.current_page += 1
                    self.show_current_page()
            elif isinstance(self.current_doc, epub.EpubBook):
                items = list(self.current_doc.get_items_of_type(ebooklib.ITEM_DOCUMENT))
                if self.current_page < len(items) - 1:
                    self.save_current_marks()
                    self.current_page += 1
                    self.show_current_page()

    def zoom_in(self):
        """放大"""
        if self.zoom_factor < self.max_zoom:
            self.zoom_factor *= 1.2
            self.zoom_factor = min(self.zoom_factor, self.max_zoom)
            self.update_zoom_label()
            self.show_current_page()

    def zoom_out(self):
        """缩小"""
        if self.zoom_factor > self.min_zoom:
            self.zoom_factor /= 1.2
            self.zoom_factor = max(self.zoom_factor, self.min_zoom)
            self.update_zoom_label()
            self.show_current_page()

    def update_zoom_label(self):
        """更新缩放比例显示"""
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")

    def goto_page(self):
        """跳转到指定页面"""
        try:
            page_num = int(self.page_input.text()) - 1  # 转换为从0开始的索引
            if isinstance(self.current_doc, fitz.Document):
                if 0 <= page_num < len(self.current_doc):
                    self.save_current_marks()
                    self.current_page = page_num
                    self.show_current_page()
                else:
                    QMessageBox.warning(self, '警告', '页码超出范围！')
        except ValueError:
            QMessageBox.warning(self, '警告', '请输入有效的页码！')

    def choose_color(self):
        """选择标记颜色"""
        color = QColorDialog.getColor(self.content_display.current_color, self)
        if color.isValid():
            self.content_display.current_color = color

    def clear_current_marks(self):
        """清除当前页面的标记"""
        self.content_display.clear_marks()
        if self.current_book_path and self.current_page is not None:
            key = f"{self.current_book_path}_{self.current_page}"
            if key in self.page_marks:
                del self.page_marks[key]
                self.save_marks()

    def save_current_marks(self):
        """保存当前页面的标记"""
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
        """查看笔记"""
        note = item.data(0, Qt.ItemDataRole.UserRole)
        if note:
            dialog = QDialog(self)
            dialog.setWindowTitle('查看笔记')
            dialog.setFixedWidth(400)

            layout = QVBoxLayout(dialog)

            # 笔记信息
            info_label = QLabel(f"页码：第{note['page'] + 1}页\n时间：{note['timestamp']}")
            layout.addWidget(info_label)

            # 笔记内容
            content_edit = QTextEdit()
            content_edit.setPlainText(note['content'])
            content_edit.setReadOnly(True)
            layout.addWidget(content_edit)

            # 关闭按钮
            close_btn = QPushButton('关闭')
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

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
        """显示书籍右键菜单"""
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
            del self.books[file_path]
            self.save_library()
            self.update_book_tree()


def main():
    app = QApplication(sys.argv)
    manager = EbookManager()
    manager.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()