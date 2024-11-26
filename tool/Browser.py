import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QInputDialog, QMenu, QDialog, QLabel,
                             QToolBar, QColorDialog, QMessageBox)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import Qt, QUrl, QPoint, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QAction, QPainter, QPen, QColor, QPixmap
from PyQt6.QtSql import QSqlDatabase, QSqlQuery


def init_database():
    """初始化数据库"""
    db = QSqlDatabase.addDatabase('QSQLITE')
    db.setDatabaseName('browser.db')
    if not db.open():
        return False

    query = QSqlQuery()

    # 创建书签表
    query.exec("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    """)

    # 创建绘图数据表
    query.exec("""
        CREATE TABLE IF NOT EXISTS drawings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            drawing_data BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 检查是否需要添加默认分类
    query.exec("SELECT COUNT(*) FROM bookmarks")
    if query.next() and query.value(0) == 0:
        # 添加默认分类
        default_categories = ["常用", "工作", "学习", "其他"]
        for category in default_categories:
            query.prepare("INSERT INTO bookmarks (category, title, url) VALUES (?, '默认书签', 'about:blank')")
            query.addBindValue(category)
            query.exec()

    return True


class DrawingLayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drawing = False
        self.last_point = None
        self.pixmap = QPixmap(self.size())
        self.pixmap.fill(Qt.GlobalColor.transparent)
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 2
        self.lines = []
        self.eraser_mode = False  # 添加擦除模式标志
        self.eraser_size = 20  # 添加擦除器大小

        # 修改窗口属性
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: transparent;")

    def toggle_eraser(self):
        """切换擦除模式"""
        self.eraser_mode = not self.eraser_mode
        # 更改鼠标样式
        if self.eraser_mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()

    def set_eraser_size(self, size):
        """设置擦除器大小"""
        self.eraser_size = size

    def erase_at_point(self, point):
        """在指定点擦除内容"""
        painter = QPainter(self.pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setPen(QPen(Qt.GlobalColor.transparent, self.eraser_size, Qt.PenStyle.SolidLine))
        painter.drawPoint(point)
        self.update()

        # 立即保存更改到数据库
        if isinstance(self.parent(), QWebEngineView):
            self.save_to_database(self.parent().url().toString())

    def draw_line(self, start, end):
        """绘制线条"""
        painter = QPainter(self.pixmap)
        painter.setPen(QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine))
        painter.drawLine(start, end)
        self.lines.append((start, end, self.pen_color, self.pen_width))
        self.update()

    def clear(self):
        """清除绘图"""
        self.pixmap.fill(Qt.GlobalColor.transparent)
        self.lines = []
        self.update()
        # 从数据库中删除当前URL的绘图数据
        if isinstance(self.parent(), QWebEngineView):
            url = self.parent().url().toString()
            query = QSqlQuery()
            query.prepare("DELETE FROM drawings WHERE url = ?")
            query.addBindValue(url)
            query.exec()

    def save_to_database(self, url):
        """保存绘图数据到数据库"""
        # 将pixmap转换为字节数据
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.pixmap.save(buffer, "PNG")
        buffer.close()

        # 保存到数据库，使用REPLACE语法确保更新现有记录
        query = QSqlQuery()
        query.prepare("""
            INSERT OR REPLACE INTO drawings (url, drawing_data)
            VALUES (?, ?)
        """)
        query.addBindValue(url)
        query.addBindValue(byte_array)
        success = query.exec()

        # 确保数据被写入
        if success:
            query.finish()
            return True
        return False

    def load_from_database(self, url):
        """从数据库加载绘图数据"""
        query = QSqlQuery()
        query.prepare("SELECT drawing_data FROM drawings WHERE url = ?")
        query.addBindValue(url)

        if query.exec() and query.next():
            drawing_data = query.value(0)
            new_pixmap = QPixmap()
            if new_pixmap.loadFromData(drawing_data):
                # 调整加载的pixmap大小以匹配当前大小
                if new_pixmap.size() != self.size():
                    new_pixmap = new_pixmap.scaled(self.size(),
                                                   Qt.AspectRatioMode.IgnoreAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
                self.pixmap = new_pixmap
                self.update()
                return True
        return False

    def paintEvent(self, event):
        """重写绘图事件"""
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

    def resizeEvent(self, event):
        """重写调整大小事件"""
        old_pixmap = self.pixmap
        new_size = event.size()
        new_pixmap = QPixmap(new_size)
        new_pixmap.fill(Qt.GlobalColor.transparent)

        if not old_pixmap.isNull():
            # 保持绘图内容，进行缩放
            painter = QPainter(new_pixmap)
            scaled_pixmap = old_pixmap.scaled(new_size,
                                              Qt.AspectRatioMode.IgnoreAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()

        self.pixmap = new_pixmap
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            self.last_point = None
            # 无论是绘图还是擦除，都保存到数据库
            if isinstance(self.parent(), QWebEngineView):
                self.save_to_database(self.parent().url().toString())

    def mouseMoveEvent(self, event):
        if self.drawing and self.last_point:
            current_point = event.pos()
            if self.eraser_mode:
                # 擦除模式
                self.erase_at_point(current_point)
            else:
                # 绘图模式
                self.draw_line(self.last_point, current_point)
            self.last_point = current_point


class SimpleBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bookmark_visible = True
        self.drawing_enabled = False

        # 初始化数据库
        if not init_database():
            QMessageBox.critical(self, "错误", "无法初始化数据库！")
            sys.exit(1)

        self.init_ui()
        self.load_bookmarks()
        self.setup_drawing_toolbar()

    def setup_drawing_toolbar(self):
        """设置绘图工具栏"""
        drawing_toolbar = QToolBar("图工具", self)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, drawing_toolbar)

        # 切换绘图式按钮
        self.toggle_drawing_action = QAction("✏️", self)
        self.toggle_drawing_action.setCheckable(True)
        self.toggle_drawing_action.triggered.connect(self.toggle_drawing_mode)
        drawing_toolbar.addAction(self.toggle_drawing_action)

        # 颜色选择按钮
        color_action = QAction("🎨", self)
        color_action.triggered.connect(self.choose_color)
        drawing_toolbar.addAction(color_action)

        # 擦除工具按钮
        eraser_action = QAction("🧽", self)
        eraser_action.setCheckable(True)
        eraser_action.triggered.connect(self.toggle_eraser)
        drawing_toolbar.addAction(eraser_action)

        # 擦除器大小按钮
        small_eraser_action = QAction("小橡皮", self)
        small_eraser_action.triggered.connect(lambda: self.set_eraser_size(10))
        drawing_toolbar.addAction(small_eraser_action)

        medium_eraser_action = QAction("中橡皮", self)
        medium_eraser_action.triggered.connect(lambda: self.set_eraser_size(20))
        drawing_toolbar.addAction(medium_eraser_action)

        large_eraser_action = QAction("大橡皮", self)
        large_eraser_action.triggered.connect(lambda: self.set_eraser_size(30))
        drawing_toolbar.addAction(large_eraser_action)

        # 清除按钮
        clear_action = QAction("🗑️", self)
        clear_action.triggered.connect(self.clear_drawing)
        drawing_toolbar.addAction(clear_action)

        # 设置画笔宽度按钮
        thin_pen_action = QAction("细线", self)
        thin_pen_action.triggered.connect(lambda: self.set_pen_width(2))
        drawing_toolbar.addAction(thin_pen_action)

        thick_pen_action = QAction("粗线", self)
        thick_pen_action.triggered.connect(lambda: self.set_pen_width(5))
        drawing_toolbar.addAction(thick_pen_action)

    def init_ui(self):
        self.setWindowTitle('简洁浏览器')
        self.setGeometry(100, 100, 1200, 800)

        # 主窗口布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建浏览器视图并设置权限
        self.browser = QWebEngineView()
        self.browser.urlChanged.connect(self.update_url)

        # 设置页面设置以忽略某些权限警告
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

        # 创建绘图层
        self.drawing_layer = DrawingLayer(self.browser)
        self.drawing_layer.hide()

        # 浏览器视图容器
        self.browser_container = QWidget()
        browser_layout = QVBoxLayout(self.browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.addWidget(self.browser)

        # 顶导航栏
        nav_bar = QWidget()
        nav_bar.setFixedHeight(50)
        nav_bar.setObjectName("nav_bar")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(5, 5, 5, 5)

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

        # 下方的内容区域
        content_widget = QWidget()
        self.content_layout = QHBoxLayout(content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # 左侧收藏夹面板
        self.bookmark_widget = QWidget()
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

        # 添加到内容布局
        self.content_layout.addWidget(self.bookmark_widget)
        self.content_layout.addWidget(self.browser_container)
        self.content_layout.setStretch(1, 1)

        # 添加内容区域到主布局
        main_layout.addWidget(nav_bar, 0)
        main_layout.addWidget(content_widget, 1)

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
        """从数据库加载书签"""
        self.bookmarks = {"分类": {}}
        query = QSqlQuery()

        # 获取所有分类
        query.exec("SELECT DISTINCT category FROM bookmarks")
        while query.next():
            category = query.value(0)
            self.bookmarks["分类"][category] = []

        # 如果没有任何分类，添加默认分类
        if not self.bookmarks["分类"]:
            default_categories = ["常用", "工作", "学习", "其他"]
            for category in default_categories:
                self.bookmarks["分类"][category] = []
                query.prepare("INSERT INTO bookmarks (category, title, url) VALUES (?, '默认书签', 'about:blank')")
                query.addBindValue(category)
                query.exec()

        # 获取每个分类的书签
        for category in self.bookmarks["分类"].keys():
            query.prepare("SELECT title, url FROM bookmarks WHERE category = ?")
            query.addBindValue(category)
            if query.exec():
                while query.next():
                    self.bookmarks["分类"][category].append({
                        'title': query.value(0),
                        'url': query.value(1)
                    })

        self.update_bookmark_tree()

    def save_bookmarks(self):
        """保存书签到数据库"""
        query = QSqlQuery()

        # 清空现有书签
        query.exec("DELETE FROM bookmarks")

        # 插入新的签数据
        for category, bookmarks in self.bookmarks["分类"].items():
            for bookmark in bookmarks:
                query.prepare("""
                    INSERT INTO bookmarks (category, title, url)
                    VALUES (?, ?, ?)
                """)
                query.addBindValue(category)
                query.addBindValue(bookmark['title'])
                query.addBindValue(bookmark['url'])
                query.exec()

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

            # 到并更新书签
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

        # 显示话框
        dialog.exec()

    def delete_bookmark(self, item):
        """删除藏"""
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
        # 如果在绘图模式下，先保存当前页面的绘图
        if self.drawing_enabled:
            self.drawing_layer.save_to_database(self.browser.url().toString())

        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.browser.setUrl(QUrl(url))

    def update_url(self, url):
        """更新地址栏并加载对应的绘图数据"""
        self.url_bar.setText(url.toString())
        self.url_bar.setCursorPosition(0)

        # 如果绘图模式已启用，加该URL对应的绘图数据
        if self.drawing_enabled:
            # 调整绘图层大小
            self.drawing_layer.setGeometry(0, 0,
                                           self.browser.width(),
                                           self.browser.height())
            # 先清空当前绘图内容
            self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)
            # 加载新页面的绘图数据
            self.drawing_layer.load_from_database(url.toString())
            self.drawing_layer.show()
            self.drawing_layer.raise_()

    def navigate_back(self):
        """返回上一页"""
        # 如果在绘图模式下，先保存当前页面的绘图
        if self.drawing_enabled:
            self.drawing_layer.save_to_database(self.browser.url().toString())
        self.browser.back()

    def navigate_forward(self):
        """前进到下一页"""
        # 如果在绘图模式下，先保存当前页面的绘图
        if self.drawing_enabled:
            self.drawing_layer.save_to_database(self.browser.url().toString())
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

    def toggle_drawing_mode(self):
        """切换绘图模式"""
        if self.drawing_enabled:
            # 关闭绘图模式前保存当前内容
            current_url = self.browser.url().toString()
            self.drawing_layer.save_to_database(current_url)
            # 清空绘图层
            self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)
            self.drawing_layer.update()
            self.drawing_layer.hide()
            # 更新工具栏按钮状态
            self.toggle_drawing_action.setChecked(False)
        else:
            # 开启绘图模式
            # 调整绘图层大小以匹配浏览器视图
            self.drawing_layer.setGeometry(0, 0,
                                           self.browser.width(),
                                           self.browser.height())

            # 创建新的空白 pixmap
            self.drawing_layer.pixmap = QPixmap(self.drawing_layer.size())
            self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)

            # 加载当前页面的绘图数据
            current_url = self.browser.url().toString()
            self.drawing_layer.load_from_database(current_url)

            # 确保绘图层可见并在正确位置
            self.drawing_layer.show()
            self.drawing_layer.raise_()

            # 更新工具栏按钮状态
            self.toggle_drawing_action.setChecked(True)

        # 最后更新状态
        self.drawing_enabled = not self.drawing_enabled

    def choose_color(self):
        """选择画笔颜色"""
        color = QColorDialog.getColor(self.drawing_layer.pen_color, self)
        if color.isValid():
            self.drawing_layer.pen_color = color

    def set_pen_width(self, width):
        """设画笔宽度"""
        self.drawing_layer.pen_width = width

    def clear_drawing(self):
        """清除所有绘图"""
        self.drawing_layer.clear()

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        if hasattr(self, 'drawing_layer') and hasattr(self, 'browser'):
            if self.drawing_enabled:
                # 调整绘图层大小以匹配浏览器视图
                self.drawing_layer.setGeometry(0, 0,
                                               self.browser.width(),
                                               self.browser.height())

    def toggle_eraser(self):
        """切换擦除模式"""
        self.drawing_layer.toggle_eraser()

    def set_eraser_size(self, size):
        """设置擦除器大小"""
        self.drawing_layer.set_eraser_size(size)


def main():
    app = QApplication(sys.argv)
    browser = SimpleBrowser()
    browser.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()