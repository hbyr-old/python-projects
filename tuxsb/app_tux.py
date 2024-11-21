import random
import pyautogui
from tuxsb import base

url = '../images/'
# 使用封装的方法识别并点击图片
# 1、双击打开模拟器
center_x, center_y = base.find_coordinates('../images/app.png',60)
print(f"app.png的中心坐标为: ({center_x}, {center_y})")
if center_x == -9999 and center_y == -9999:
    raise TimeoutError("抱歉未识别到图像")
# 双击图片的中心坐标
pyautogui.doubleClick(center_x, center_y)
print("============================1、双击打开模拟器=============================")

# 2、单击开始界面的“开始游戏”,随机50像素，延迟8s
base.one_click(url,'start.png',50,8,240,'0000')
print("============================2、单击开始界面的“开始游戏”=============================")

# 3、进入魂土界面，配置御魂和开加成，随机20像素，延迟2-10s
for i in range(1, 11):
    if i==3:
        base.one_click(url,f'syh{i}.png', 200, random.randint(2, 10),60,'0000')
    elif i==8:
        base.one_click(url,f'syh{i}.png', 20, random.randint(2, 10),10,'9998')
    else:
        base.one_click(url,f'syh{i}.png', 20, random.randint(2, 10), 60,'0000')
print("============================3、进入魂土界面，配置御魂和开加成===========================================")

