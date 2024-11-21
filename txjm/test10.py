import json

data = {"xhcs": "1", "hh": "2", "sdf": "3", "gg": "4"}
person = {"name": "4", "age": "5", "sex": "6"}

data["person"] = [person]

with open('data.txt', 'w') as f:
    json.dump(data, f)
