url='../datas/'
def file_w(file_name,data):
    # 打开文件并追加数据
    with open(url+file_name, "a") as file:
        file.write(data+"\n")

    # 关闭文件
    file.close()

def file_r(file_name,data_lines):
    # 打开文件
    with open(url+file_name, "r") as file:
        # 读取所有行
        lines = file.readlines()

        # 检查文件是否至少有两行
        if len(lines) >= data_lines:
            # 获取第二行数据
            second_line = lines[data_lines-1]

            # 打印第data_lines行数据
            print(second_line)
        else:
            print("文件中没有足够的行。")



