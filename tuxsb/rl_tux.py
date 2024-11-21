import random
import time

from tuxsb import base

url = '../images/rl_images/'
#单刷日轮
for i in range(43):
    for m in range(1, 4):
        if m == 1:
            base.one_click(url,f'rl{m}.png', 50, random.randint(1, 2), 60, '0000')
        elif m == 2:
            base.one_click(url,f'rl{m}.png', 50, random.randint(2, 3), 60, '9998')
        else:
            base.one_click(url,f'rl{m}.png', 100, random.randint(1, 2), 60, '0000')

    print(f"============================{i+1}===========================================")
    #time.sleep(random.randint(2, 30))


