import json

# 打开并读取文件内容
with open('path_to_your_file.txt', 'r') as file:
    json_data = file.read()

# 解析JSON数据
data = json.loads(json_data)

# 现在你可以使用解析后的数据
print(data['name'])