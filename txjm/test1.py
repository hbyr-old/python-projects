import json

# 假设你有一些JSON数据
data = {
  "name": "张三",
  "age": 30,
  "city": "北京",
  "email": "zhangsan@example.com"
}

# 将JSON数据转换为字符串
json_data = json.dumps(data)

# 写入到txt文件中
with open('path_to_your_file.txt', 'w') as file:
    file.write(json_data)