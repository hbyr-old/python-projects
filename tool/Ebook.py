import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QListWidget, QLineEdit, QPushButton,
                             QLabel, QFileDialog, QMessageBox, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QMenu, QTextEdit)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QImage, QPixmap, QAction
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
import json
import re


class EbookManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.epub', '.pdf', '.mobi', '.azw', '.azw3', '.txt']
        self.books = {}  # 存储书籍信息
        self.notes = {}  # 存储笔记信息
        self.current_doc = None  # 当前打开的文档
        self.current_page = 0  # 当前页码
        self.init_ui()
        self.load_library()
        self.load_notes()

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

        # 右侧阅读区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 工具栏
        toolbar = QHBoxLayout()
        self.prev_btn = QPushButton('上一页')
        self.next_btn = QPushButton('下一页')
        self.add_note_btn = QPushButton('添加笔记')

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.add_note_btn.clicked.connect(self.add_note)

        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)
        toolbar.addWidget(self.add_note_btn)

        right_layout.addLayout(toolbar)

        # 阅读区域
        self.content_display = QTextEdit()
        self.content_display.setReadOnly(True)
        self.content_display.setStyleSheet("""
            QTextEdit {
                padding: 20px;
                background: white;
                font-size: 16px;
                line-height: 1.6;
            }
        """)
        right_layout.addWidget(self.content_display)

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

    def save_library(self):
        """保存书库信息"""
        with open('library.json', 'w', encoding='utf-8') as f:
            json.dump(self.books, f, ensure_ascii=False, indent=2)

    def save_notes(self):
        """保存笔记"""
        with open('notes.json', 'w', encoding='utf-8') as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)

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
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                self.open_pdf(file_path)
            elif ext == '.epub':
                self.open_epub(file_path)
            elif ext == '.txt':
                self.open_txt(file_path)
            else:
                QMessageBox.warning(self, '错误', f'不支持的文件格式: {ext}')
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
                page = self.current_doc[self.current_page]
                text = page.get_text()
                self.content_display.setText(text)
        elif isinstance(self.current_doc, epub.EpubBook):  # EPUB
            items = list(self.current_doc.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            if 0 <= self.current_page < len(items):
                content = items[self.current_page].get_content().decode('utf-8')
                content = content.replace('<p>', '\n').replace('</p>', '\n')
                content = content.replace('<br>', '\n')
                content = re.sub('<[^<]+?>', '', content)
                self.content_display.setText(content)

    def prev_page(self):
        """上一页"""
        if self.current_doc and self.current_page > 0:
            self.current_page -= 1
            self.show_current_page()

    def next_page(self):
        """下一页"""
        if self.current_doc:
            if isinstance(self.current_doc, fitz.Document):
                if self.current_page < len(self.current_doc) - 1:
                    self.current_page += 1
                    self.show_current_page()
            elif isinstance(self.current_doc, epub.EpubBook):
                items = list(self.current_doc.get_items_of_type(ebooklib.ITEM_DOCUMENT))
                if self.current_page < len(items) - 1:
                    self.current_page += 1
                    self.show_current_page()

    def add_note(self):
        """添加笔记"""
        # TODO: 实现添加笔记功能
        pass

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