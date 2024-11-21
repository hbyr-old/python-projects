import tkinter as tk
import json

def save_to_json():
    data = {}
    for entry, key in zip(entries, keys):
        data[key] = entry.get()
    with open('data.txt', 'w') as f:
        json.dump(data, f)

root = tk.Tk()
root.title("Multiple Textbox to JSON")

keys = ['name', 'age', 'city', 'email']
entries = []

for i, key in enumerate(keys):
    tk.Label(root, text=key).grid(row=i, column=0)
    entry = tk.Entry(root)
    entry.grid(row=i, column=1)
    entries.append(entry)

button = tk.Button(root, text="Save", command=save_to_json)
button.grid(row=len(keys), column=0, columnspan=2)

root.mainloop()
