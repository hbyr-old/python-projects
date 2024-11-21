import random
import time

from tuxsb import base

url = '../images/yyh_images/'
#业原火副本
for i in range(100):
    for m in range(1, 4):
        if m == 1:
            base.one_click(url,f'yyh{m}.png', 20, random.randint(1, 3), 60, '0000')
        else:
            base.one_click(url,f'yyh{m}.png', 50, random.randint(1, 3), 60, '0000')

    print(f"============================{i+1}===========================================")
    #time.sleep(random.randint(2, 30))


