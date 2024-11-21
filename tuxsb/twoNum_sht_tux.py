import random
import time

from tuxsb import base

url = '../images/twoNum_zdsht_images/'
#单刷魂土
for i in range(100):
    # 3、进入魂土界面，配置御魂和开加成，随机20像素，延迟2-10s
    for m in range(1, 6):
        if m == 5:
            base.one_click(url,f't_zdsht{m}.png', 20, random.randint(1, 2), 60, '0000')
            base.one_click(url, f't_zdsht{m}.png', 20, random.randint(1, 2), 10, '9998')
        else:
            base.one_click(url,f't_zdsht{m}.png', 20, random.randint(1, 2), 60, '0000')

    print(f"============================{i}===========================================")
    #time.sleep(random.randint(2, 30))


