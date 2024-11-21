import random
import time
from platform import system

from tuxsb import base

url = '../images/fengmo_images/'
def zhixing():
    # 1、进入战斗界面，配置御魂和开加成，随机20像素，延迟2-10s
    m=1
    for m in range(1, 7):
        if m == 4:
            time.sleep(3)
            x,y=base.one_click(url,f'fengmo_qx.png', 3, random.randint(1, 1), 2, '9998')
            if x!= -9999 and y!= -9999:
                break
            base.one_click(url,f'fengmo{m}.png', 4, random.randint(1, 1), 15, '9998')
        elif m == 2:
            start_time = time.time()
            base.one_click(url, f'fengmo{m}.png', 10, random.randint(3, 4), 10, '9998')
            if time.time()-start_time >=10:
                while time.time()-start_time>10:
                    base.one_click(url, f'fengmo{m-1}.png', 10, random.randint(3, 4), 10, '9998')
                    base.one_click(url, f'fengmo{m}.png', 10, random.randint(3, 4), 10, '9998')
                    start_time = time.time()
        elif m == 3:
            start_time = time.time()
            base.one_click(url, f'fengmo{m}.png', 10, random.randint(1, 3), 3, '9998')
            if time.time() - start_time >= 9:
                break
        elif m == 5:
            start_time = time.time()
            base.one_click(url, f'fengmo{m}.png', 10, random.randint(1, 3), 10, '9998')
            base.one_click(url, f'fengmo{m}.png', 10, random.randint(1, 3), 10, '9998')
            if time.time() - start_time >= 9:
                break
        else:
            base.one_click(url,f'fengmo{m}.png', 10, random.randint(1, 3), 60, '0000')
    if m in (3,5):
        zhixing()
#逢魔捡体力
for i in range(10000):
    zhixing()
    print(f"============================{i+1}===========================================")
    #time.sleep(random.randint(2, 30))


