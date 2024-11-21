import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QFileDialog, QSlider, QLabel, QStyle)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont

class ChineseStyleVideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("墨韵播放器")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5E6E8;
            }
            QPushButton {
                background-color: #8B4513;
                color: #F5E6E8;
                border: 2px solid #654321;
                border-radius: 5px;
                padding: 5px;
                min-width: 80px;
                font-family: "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #654321;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #8B4513;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #654321;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
        """)
        
        # 设置窗口大小
        self.resize(800, 600)
        
        # 创建媒体播放器
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        
        # 创建视频显示窗口
        self.videoWidget = QVideoWidget()
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        
        # 创建控制按钮
        self.playButton = QPushButton("播放")
        self.playButton.clicked.connect(self.play)
        
        self.openButton = QPushButton("打开文件")
        self.openButton.clicked.connect(self.open_file)
        
        # 创建进度条
        self.positionSlider = QSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.set_position)
        
        # 创建音量控制
        self.volumeSlider = QSlider(Qt.Orientation.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(50)
        self.volumeSlider.setMaximumWidth(100)
        self.volumeSlider.valueChanged.connect(self.set_volume)
        
        # 创建时间标签
        self.timeLabel = QLabel("00:00 / 00:00")
        self.timeLabel.setStyleSheet("color: #8B4513; font-family: 'Microsoft YaHei';")
        
        # 创建布局
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        layout.addWidget(self.videoWidget)
        
        # 控制栏布局
        controlLayout = QHBoxLayout()
        controlLayout.addWidget(self.openButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)
        controlLayout.addWidget(self.timeLabel)
        controlLayout.addWidget(QLabel("音量"))
        controlLayout.addWidget(self.volumeSlider)
        
        layout.addLayout(controlLayout)
        
        # 连接信号
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)
        
        # 设置初始音量
        self.audioOutput.setVolume(0.5)

    def open_file(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "打开视频",
                "", "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)")
        
        if fileName:
            self.mediaPlayer.setSource(QUrl.fromLocalFile(fileName))
            self.playButton.setText("播放")
            self.play()

    def play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
            self.playButton.setText("播放")
        else:
            self.mediaPlayer.play()
            self.playButton.setText("暂停")

    def position_changed(self, position):
        self.positionSlider.setValue(position)
        duration = self.mediaPlayer.duration()
        self.update_time_label(position, duration)

    def duration_changed(self, duration):
        self.positionSlider.setRange(0, duration)
        self.update_time_label(self.mediaPlayer.position(), duration)

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def set_volume(self, volume):
        self.audioOutput.setVolume(volume / 100)

    def update_time_label(self, position, duration):
        position_time = self.format_time(position)
        duration_time = self.format_time(duration)
        self.timeLabel.setText(f"{position_time} / {duration_time}")

    def format_time(self, ms):
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = ChineseStyleVideoPlayer()
    player.show()
    sys.exit(app.exec()) 