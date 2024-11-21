import random
import time

from tuxsb import base

url = '../images/yj_gw_images/'
#业原火副本
for i in range(1000):
    for m in range(1, 4):
        if m == 1:
            base.one_click(url,f'gw{m}.png', 50, random.randint(1, 2), 60, '0000')
        elif m == 2:
            base.one_click(url,f'gw{m}.png', 100, random.randint(1, 2), 60, '0000')
        else:
            base.one_click(url,f'gw{m}.png', 150, random.randint(1, 2), 5, '9998')

    print(f"============================{i+1}===========================================")
    #time.sleep(random.randint(2, 30))


