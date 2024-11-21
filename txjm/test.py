import tkinter as tk
from txjm import file_base_io

def button_click():
    file_base_io.file_w('data.txt','^-^123^-^456^-^789^-^1111')
def button_click1():
    file_base_io.file_r('data.txt',3)

# 创建主窗口
root = tk.Tk()
root.title("My GUI App")

# 创建按钮
button = tk.Button(root, text="Click me", command=button_click)
button.pack()
# 创建按钮
button1 = tk.Button(root, text="Click1 me", command=button_click1)
button1.pack()

# 运行主循环
root.mainloop()