import random
import time

from tuxsb import base

url = '../images/zdsht_images/'
sj = 0 #司机
dx = 1 #打手小屏
#组队刷魂土
for i in range(400):
    # 3、进入魂土界面，配置御魂和开加成，随机20像素，延迟2-10s
    if sj == 1:
        for m in range(1, 4):
            if m == 1:
                base.one_click(url, f's_zdsht{m}.png', 50, random.randint(1, 2), 60, '0000')
            else:
                base.one_click(url, f's_zdsht{m}.png', 50, random.randint(1, 2), 60, '0000')
    else:
        if dx == 1:
            for m in range(1, 3):
                base.one_click(url, f'dx_zdsht{m}.png', 50, random.randint(1, 2), 60, '9998')
        else:
            base.one_click(url, f'dx_zdsht{m}.png', 50, random.randint(1, 2), 60, '9998')


    print(f"============================{i}===========================================")
    #time.sleep(random.randint(2, 30))



