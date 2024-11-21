import random
import time
import cv2
import numpy as np
import pyautogui


def find_coordinates(image_path,timeout):
    # 定义要识别的图片
    target_image = cv2.imread(image_path)
    # 获取当前时间作为开始时间
    start_time = time.time()
    while True:
        # 捕获屏幕图像
        # Bug fix: Use the updated pyautogui version with the screenshot function
        screenshot = pyautogui.screenshot()
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # 使用模板匹配识别图片
        result = cv2.matchTemplate(frame, target_image, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # 如果找到了目标图片，则停止循环
        # 检查是否已经超过了超时时间
        if max_val > 0.8 or time.time() - start_time > timeout:
            break

    if max_val>0.8:
        # 获取图片的坐标
        top_left = max_loc
        bottom_right = (top_left[0] + target_image.shape[1], top_left[1] + target_image.shape[0])
        # 计算图片的中心坐标
        center_x = (top_left[0] + bottom_right[0]) // 2
        center_y = (top_left[1] + bottom_right[1]) // 2
        return center_x, center_y
    else:
        return -9999,-9999


def add_random_coordinates(center_x, center_y, sjs):
    # 在中心坐标添加随机范围在sj以内的偏移量
    random_x = random.randint(-sjs, sjs)
    random_y = random.randint(-sjs, sjs)
    return center_x + random_x, center_y + random_y
#单击随机坐标进行封装
def one_click(url,image_name,sjs,yc,timeout,cwbm):
    center_x, center_y = find_coordinates(url+image_name,timeout)
    print(f"{image_name}的中心坐标为: ({center_x}, {center_y})")
    if center_x != -9999 and center_y != -9999:
        # 延迟5秒
        time.sleep(yc)
        # 在中心坐标添加随机范围在50以内
        random_x, random_y = add_random_coordinates(center_x, center_y, sjs)
        print(f"{image_name}的随机坐标为: ({random_x}, {random_y})")
        # 单击图片的中心坐标
        pyautogui.click(random_x, random_y)
        return random_x,random_y
    elif cwbm == '9998':
        print(f"{image_name}，跳过此步骤")
        return center_x, center_y
    else:
        raise TimeoutError("抱歉未识别到图像")