import tkinter as tk
import json

def add_entry():
    entry = tk.Entry(root)
    entry.pack()
    entries.append(entry)

def save_to_json():
    data = {}
    for entry in entries:
        data[entry.winfo_name()] = entry.get()
    with open('data.txt', 'w') as f:
        json.dump(data, f)

root = tk.Tk()
root.title("Add Entry")

entries = []

button_add = tk.Button(root, text="Add Entry", command=add_entry)
button_add.pack()

button_save = tk.Button(root, text="Save", command=save_to_json)
button_save.pack()

root.mainloop()