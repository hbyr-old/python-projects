import random
import time

from tuxsb import base

url = '../images/sht_images/'
#单刷魂土
for i in range(400):
    # 3、进入魂土界面，配置御魂和开加成，随机20像素，延迟2-10s
    for m in range(1, 4):
        if m == 1:
            base.one_click(url,f'ht{m}.png', 50, random.randint(1, 2), 60, '0000')
        else:
            base.one_click(url,f'ht{m}.png', 150, random.randint(1, 2), 60, '0000')

    print(f"============================{i}===========================================")
    #time.sleep(random.randint(2, 30))


