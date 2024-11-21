import pyautogui
import pytesseract
from PIL import Image
import time
import cv2
import numpy as np
import re


class ScreenTimeReader:
    def __init__(self):
        # 设置Tesseract路径
        pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'

        # 优化时间识别的配置
        self.custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:'

    def capture_screen_region(self, x, y, width, height):
        """截取指定区域的屏幕"""
        try:
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            # 放大图像以提高识别率
            screenshot = screenshot.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
            return screenshot
        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def preprocess_image(self, image):
        """针对时间格式优化的图像预处理"""
        # 转换为OpenCV格式
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # 转换为灰度图
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)

        # 增强对比度
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 二值化处理
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 降噪
        denoised = cv2.fastNlMeansDenoising(binary)

        # 轻微膨胀，使数字更清晰
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(denoised, kernel, iterations=1)

        # 保存处理后的图像用于调试
        cv2.imwrite('processed_time.png', dilated)

        return Image.fromarray(dilated)

    def is_valid_time(self, time_str):
        """验证时间格式是否有效"""
        # 检查基本格式 HH:MM:SS 或 HH:MM
        time_patterns = [
            r'^\d{1,2}:\d{2}:\d{2}$',  # HH:MM:SS
            r'^\d{1,2}:\d{2}$'  # HH:MM
        ]

        for pattern in time_patterns:
            if re.match(pattern, time_str):
                parts = time_str.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    h, m, s = map(int, parts)
                    return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
                elif len(parts) == 2:  # HH:MM
                    h, m = map(int, parts)
                    return 0 <= h <= 23 and 0 <= m <= 59
        return False

    def read_time_from_region(self, x, y, width, height):
        """从指定区域读取时间"""
        screenshot = self.capture_screen_region(x, y, width, height)
        if screenshot is None:
            return None

        try:
            # 保存原始截图
            screenshot.save('original_time.png')

            # 预处理图像
            processed_image = self.preprocess_image(screenshot)

            # 尝试不同的处理方式
            results = []

            # 直接识别
            text1 = pytesseract.image_to_string(
                processed_image,
                config=self.custom_config
            ).strip()
            if text1:
                results.append(text1)

            # 反色识别
            inverted_image = Image.fromarray(255 - np.array(processed_image))
            text2 = pytesseract.image_to_string(
                inverted_image,
                lang='chi_sim',
                config=self.custom_config
            ).strip()
            if text2:
                results.append(text2)

            # 合并结果
            if results:
                # 清理结果，去除空白字符
                cleaned_results = [' '.join(result.split()) for result in results]
                # 选择最长的有效结果
                final_result = max(cleaned_results, key=len, default='')
                if final_result:
                    return final_result

            return None

        except Exception as e:
            print(f"OCR识别失败: {e}")
            return None


def main():
    reader = ScreenTimeReader()

    print("请准备在3秒内将鼠标移动到目标区域左上角...")
    time.sleep(3)
    x1, y1 = pyautogui.position()
    print(f"捕获左上角坐标: ({x1}, {y1})")

    print("请准备在3秒内将鼠标移动到目标区域右下角...")
    time.sleep(3)
    x2, y2 = pyautogui.position()
    print(f"捕获右下角坐标: ({x2}, {y2})")

    width = x2 - x1
    height = y2 - y1

    print(f"\n开始监控区域: ({x1}, {y1}, {width}, {height})")

    try:
        while True:
            text = reader.read_time_from_region(x1, y1, width, height)
            if text:
                print(f"识别到的时间: {text}")
            else:
                print("未识别到时间")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n程序已停止")


if __name__ == "__main__":
    main()