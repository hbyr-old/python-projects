import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QInputDialog, QMenu, QDialog, QLabel)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction
import json


class SimpleBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bookmark_visible = True  # 添加收藏夹显示状态标记
        self.init_ui()
        self.load_bookmarks()

    def init_ui(self):
        self.setWindowTitle('简洁浏览器')
        self.setGeometry(100, 100, 1200, 800)

        # 主窗口布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除主布局边距
        main_layout.setSpacing(0)  # 移除组件间距

        # 顶部导航栏
        nav_bar = QWidget()
        nav_bar.setFixedHeight(50)  # 固定导航栏高度
        nav_bar.setObjectName("nav_bar")  # 设置对象名以便应用样式
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(5, 5, 5, 5)  # 设置导航栏内边距

        # 添加显示/隐藏收藏夹按钮
        self.toggle_bookmark_btn = QPushButton('☰')
        self.toggle_bookmark_btn.setFixedWidth(40)
        self.toggle_bookmark_btn.clicked.connect(self.toggle_bookmark)
        nav_layout.addWidget(self.toggle_bookmark_btn)

        # 导航按钮
        self.back_btn = QPushButton('←')
        self.back_btn.setFixedWidth(40)
        self.back_btn.clicked.connect(self.navigate_back)

        self.forward_btn = QPushButton('→')
        self.forward_btn.setFixedWidth(40)
        self.forward_btn.clicked.connect(self.navigate_forward)

        self.reload_btn = QPushButton('↻')
        self.reload_btn.setFixedWidth(40)
        self.reload_btn.clicked.connect(self.reload_page)

        # 地址栏
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        # 收藏按钮
        self.bookmark_btn = QPushButton('★')
        self.bookmark_btn.setFixedWidth(40)
        self.bookmark_btn.clicked.connect(self.add_bookmark)

        # 添加到导航栏
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.reload_btn)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(self.bookmark_btn)

        # 添加导航栏到主布局
        main_layout.addWidget(nav_bar, 0)  # 导航栏不拉伸

        # 下方的内容区域
        content_widget = QWidget()
        self.content_layout = QHBoxLayout(content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # 左侧收藏夹面板
        self.bookmark_widget = QWidget()  # 保存为实例变量
        self.bookmark_widget.setFixedWidth(250)
        bookmark_layout = QVBoxLayout(self.bookmark_widget)
        bookmark_layout.setContentsMargins(0, 0, 0, 0)

        # 收藏夹树形结构
        self.bookmark_tree = QTreeWidget()
        self.bookmark_tree.setHeaderLabel('收藏夹')
        self.bookmark_tree.itemDoubleClicked.connect(self.open_bookmark)
        self.bookmark_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookmark_tree.customContextMenuRequested.connect(self.show_bookmark_menu)
        bookmark_layout.addWidget(self.bookmark_tree)

        # 浏览器视图容器
        self.browser_container = QWidget()
        browser_layout = QVBoxLayout(self.browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)

        # 浏览器视图
        self.browser = QWebEngineView()
        self.browser.urlChanged.connect(self.update_url)
        browser_layout.addWidget(self.browser)

        # 添加到内容布局
        self.content_layout.addWidget(self.bookmark_widget)
        self.content_layout.addWidget(self.browser_container)

        # 设置伸缩因子
        self.content_layout.setStretch(1, 1)  # 浏览器视图可伸缩

        # 添加内容区域到主布局
        main_layout.addWidget(nav_bar, 0)  # 导航栏不拉伸
        main_layout.addWidget(content_widget, 1)  # 内容区域占用所有剩余空间

        # 设置主页
        self.browser.setUrl(QUrl('https://www.google.com'))

        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background: white;
            }
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background: white;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin: 0 5px;
            }
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            #nav_bar {
                background: white;
                border-bottom: 1px solid #ddd;
            }
        """)

    def load_bookmarks(self):
        """加载收藏夹"""
        try:
            with open('bookmarks.json', 'r', encoding='utf-8') as f:
                self.bookmarks = json.load(f)
        except FileNotFoundError:
            self.bookmarks = {
                "分类": {
                    "常用": [],
                    "工作": [],
                    "学习": [],
                    "其他": []
                }
            }
        self.update_bookmark_tree()

    def save_bookmarks(self):
        """保存收藏夹"""
        with open('bookmarks.json', 'w', encoding='utf-8') as f:
            json.dump(self.bookmarks, f, ensure_ascii=False, indent=2)

    def update_bookmark_tree(self):
        """更新收藏夹显示"""
        self.bookmark_tree.clear()

        # 添加分类
        for category, bookmarks in self.bookmarks["分类"].items():
            category_item = QTreeWidgetItem(self.bookmark_tree)
            category_item.setText(0, category)
            category_item.setFlags(category_item.flags() | Qt.ItemFlag.ItemIsDropEnabled)

            # 添加该分类下的书签
            for bookmark in bookmarks:
                item = QTreeWidgetItem(category_item)
                item.setText(0, bookmark['title'])
                item.setData(0, Qt.ItemDataRole.UserRole, bookmark['url'])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)

    def add_bookmark(self):
        """添加当前页面到收藏夹"""
        dialog = QDialog(self)
        dialog.setWindowTitle('添加收藏')
        dialog.setFixedWidth(400)

        layout = QVBoxLayout(dialog)

        # 名称输入
        name_layout = QHBoxLayout()
        name_label = QLabel('名称:')
        name_edit = QLineEdit(self.browser.page().title())
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # 网址输入
        url_layout = QHBoxLayout()
        url_label = QLabel('网址:')
        url_edit = QLineEdit(self.browser.url().toString())
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_edit)
        layout.addLayout(url_layout)

        # 分类选择
        category_layout = QHBoxLayout()
        category_label = QLabel('分类:')
        category_edit = QLineEdit()
        category_edit.setPlaceholderText('选择分类...')
        category_btn = QPushButton('选择')
        category_layout.addWidget(category_label)
        category_layout.addWidget(category_edit)
        category_layout.addWidget(category_btn)
        layout.addLayout(category_layout)

        def show_category_menu():
            menu = QMenu()
            for category in self.bookmarks["分类"].keys():
                action = menu.addAction(category)
                action.triggered.connect(lambda checked, c=category: category_edit.setText(c))
            menu.exec(category_btn.mapToGlobal(category_btn.rect().bottomLeft()))

        category_btn.clicked.connect(show_category_menu)

        # 按钮布局
        button_layout = QHBoxLayout()
        save_btn = QPushButton('保存')
        cancel_btn = QPushButton('取消')
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # 设置样式
        dialog.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin: 5px;
            }
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QLabel {
                margin: 5px;
            }
        """)

        def save_bookmark():
            category = category_edit.text() or "其他"
            new_bookmark = {
                'title': name_edit.text(),
                'url': url_edit.text()
            }
            self.bookmarks["分类"][category].append(new_bookmark)
            self.save_bookmarks()
            self.update_bookmark_tree()
            dialog.accept()

        save_btn.clicked.connect(save_bookmark)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def show_bookmark_menu(self, position):
        """显示右键菜单"""
        item = self.bookmark_tree.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # 如果是分类节点
        if item.parent() is None:
            add_action = QAction('添加书签', self)
            add_action.triggered.connect(lambda: self.add_bookmark_to_category(item.text(0)))
            menu.addAction(add_action)

            rename_action = QAction('重命名分类', self)
            rename_action.triggered.connect(lambda: self.rename_category(item))
            menu.addAction(rename_action)

            if item.text(0) not in ["常用", "工作", "学习", "其他"]:
                delete_action = QAction('删除分类', self)
                delete_action.triggered.connect(lambda: self.delete_category(item))
                menu.addAction(delete_action)
        else:
            # 如果是书签节点
            edit_action = QAction('编辑', self)
            edit_action.triggered.connect(lambda: self.edit_bookmark(item))
            menu.addAction(edit_action)

            delete_action = QAction('删除', self)
            delete_action.triggered.connect(lambda: self.delete_bookmark(item))
            menu.addAction(delete_action)

            move_menu = menu.addMenu('移动到')
            for category in self.bookmarks["分类"].keys():
                if category != item.parent().text(0):
                    action = move_menu.addAction(category)
                    action.triggered.connect(
                        lambda checked, c=category: self.move_bookmark(item, c))

        menu.exec(self.bookmark_tree.viewport().mapToGlobal(position))

    def move_bookmark(self, item, new_category):
        """移动书签到新分类"""
        old_category = item.parent().text(0)
        bookmark_data = {
            'title': item.text(0),
            'url': item.data(0, Qt.ItemDataRole.UserRole)
        }

        # 从旧分类移除
        self.bookmarks["分类"][old_category].remove(
            next(b for b in self.bookmarks["分类"][old_category]
                 if b['title'] == bookmark_data['title']))

        # 添加到新分类
        self.bookmarks["分类"][new_category].append(bookmark_data)

        self.save_bookmarks()
        self.update_bookmark_tree()

    def rename_category(self, item):
        """重命名分类"""
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, '重命名分类',
                                            '请输入新的分类名称:',
                                            text=old_name)
        if ok and new_name and new_name != old_name:
            bookmarks = self.bookmarks["分类"][old_name]
            del self.bookmarks["分类"][old_name]
            self.bookmarks["分类"][new_name] = bookmarks
            self.save_bookmarks()
            self.update_bookmark_tree()

    def delete_category(self, item):
        """删除分类"""
        category = item.text(0)
        del self.bookmarks["分类"][category]
        self.save_bookmarks()
        self.update_bookmark_tree()

    def edit_bookmark(self, item):
        """编辑收藏"""
        dialog = QDialog(self)
        dialog.setWindowTitle('编辑收藏')
        dialog.setFixedWidth(400)

        layout = QVBoxLayout(dialog)

        # 名称输入框
        name_layout = QHBoxLayout()
        name_label = QLabel('名称:')
        name_edit = QLineEdit(item.text(0))
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # 网址输入框
        url_layout = QHBoxLayout()
        url_label = QLabel('网址:')
        url_edit = QLineEdit(item.data(0, Qt.ItemDataRole.UserRole))
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_edit)
        layout.addLayout(url_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        save_btn = QPushButton('保存')
        cancel_btn = QPushButton('取消')
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # 设置样式
        dialog.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin: 5px;
            }
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QLabel {
                margin: 5px;
            }
        """)

        def save_changes():
            category = item.parent().text(0)
            old_title = item.text(0)

            # 找到并更新书签
            for bookmark in self.bookmarks["分类"][category]:
                if bookmark['title'] == old_title:
                    bookmark['title'] = name_edit.text()
                    bookmark['url'] = url_edit.text()
                    break

            self.save_bookmarks()
            self.update_bookmark_tree()
            dialog.accept()

        # 只连接一次信号
        save_btn.clicked.connect(save_changes)
        cancel_btn.clicked.connect(dialog.reject)

        # 显示对话框
        dialog.exec()

    def delete_bookmark(self, item):
        """删除收藏"""
        category = item.parent().text(0)
        bookmark_title = item.text(0)

        # 从对应分类中删除书签
        self.bookmarks["分类"][category] = [
            b for b in self.bookmarks["分类"][category]
            if b['title'] != bookmark_title
        ]

        self.save_bookmarks()
        self.update_bookmark_tree()

    def open_bookmark(self, item):
        """打开收藏的网址"""
        url = item.data(0, Qt.ItemDataRole.UserRole)
        if url:
            self.browser.setUrl(QUrl(url))

    def navigate_to_url(self):
        """导航到输入的网址"""
        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.browser.setUrl(QUrl(url))

    def update_url(self, url):
        """更新地址栏"""
        self.url_bar.setText(url.toString())
        self.url_bar.setCursorPosition(0)

    def navigate_back(self):
        self.browser.back()

    def navigate_forward(self):
        self.browser.forward()

    def reload_page(self):
        self.browser.reload()

    def toggle_bookmark(self):
        """切换收藏夹显示状态"""
        if self.bookmark_visible:
            self.bookmark_widget.hide()
            self.toggle_bookmark_btn.setText('☰')
            # 隐藏时移除收藏夹的空间
            self.bookmark_widget.setFixedWidth(0)
        else:
            self.bookmark_widget.show()
            self.toggle_bookmark_btn.setText('✕')
            # 显示时恢复收藏夹宽度
            self.bookmark_widget.setFixedWidth(250)

        self.bookmark_visible = not self.bookmark_visible


def main():
    app = QApplication(sys.argv)
    browser = SimpleBrowser()
    browser.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main() 