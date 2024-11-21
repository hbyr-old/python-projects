# 迭代器
import itertools as itls

# 定义变量，变量的值用于生成密码本
words = "1234567890"
# 生成8位的密码
pwds = itls.product(words,repeat=8)

# 打开文件wifipwd.txt,并且指定为以a模式打开（在文件最后进行添加）
dic = open("wifipwd.txt", "a")

for pwd in pwds:
    # 将密码保存到txt文件中
    dic.write("".join(pwd))
    # 每一个密码进行换行处理
    dic.write("".join("\n"))
#  关闭文件
dic.close()