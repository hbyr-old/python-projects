import speech_recognition as sr
import webbrowser
import os
import time


class VoiceController:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # 设置 Chrome 浏览器路径（Windows 默认安装路径）
        self.chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

    def listen_for_command(self):
        """监听语音命令"""
        with sr.Microphone() as source:
            print("正在听取命令...")
            # 调整环境噪音
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                # 获取音频输入
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                print("正在处理语音...")

                # 使用中文识别
                command = self.recognizer.recognize_google(audio, language='zh-CN')
                print(f"识别到的命令: {command}")
                return command.lower()

            except sr.WaitTimeoutError:
                print("没有检测到语音输入")
                return None
            except sr.UnknownValueError:
                print("无法识别语音")
                return None
            except sr.RequestError as e:
                print(f"无法连接到语音识别服务；{e}")
                return None

    def execute_command(self, command):
        """执行语音命令"""
        if command is None:
            return

        # 打开浏览器的命令关键词
        open_commands = ['打开谷歌', '打开浏览器', '打开chrome', '启动浏览器']

        # 检查是否包含打开浏览器的命令
        if any(cmd in command for cmd in open_commands):
            try:
                # 检查 Chrome 是否已安装
                if os.path.exists(self.chrome_path):
                    webbrowser.register('chrome', None,
                                        webbrowser.BackgroundBrowser(self.chrome_path))
                    webbrowser.get('chrome').open('https://www.google.com')
                    print("已打开 Google Chrome")
                else:
                    print("未找到 Chrome 浏览器，尝试打开默认浏览器")
                    webbrowser.open('https://www.google.com')
            except Exception as e:
                print(f"打开浏览器时出错：{e}")


def main():
    controller = VoiceController()
    print("语音控制已启动")
    print("支持的命令：'打开谷歌'、'打开浏览器'、'打开chrome'")
    print("按 Ctrl+C 退出程序")

    try:
        while True:
            command = controller.listen_for_command()
            controller.execute_command(command)
            time.sleep(0.5)  # 短暂暂停避免CPU过度使用

    except KeyboardInterrupt:
        print("\n程序已停止")


if __name__ == "__main__":
    main()