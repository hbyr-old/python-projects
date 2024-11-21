import tkinter as tk
import json


def add_entries():
    frame = tk.Frame(root)
    frame.pack()

    name_label = tk.Label(frame, text="Name:")
    name_label.grid(row=0, column=0)
    name_entry = tk.Entry(frame)
    name_entry.grid(row=0, column=1)

    age_label = tk.Label(frame, text="Age:")
    age_label.grid(row=1, column=0)
    age_entry = tk.Entry(frame)
    age_entry.grid(row=1, column=1)

    sex_label = tk.Label(frame, text="Sex:")
    sex_label.grid(row=2, column=0)
    sex_entry = tk.Entry(frame)
    sex_entry.grid(row=2, column=1)

    entries.append((name_entry, age_entry, sex_entry))


def save_to_json():
    data = []
    for name_entry, age_entry, sex_entry in entries:
        data.append({
            "name": name_entry.get(),
            "age": age_entry.get(),
            "sex": sex_entry.get()
        })
    with open('data.txt', 'w') as f:
        json.dump(data, f)


root = tk.Tk()
root.title("Add Entries")

entries = []

button_add = tk.Button(root, text="Add Entries", command=add_entries)
button_add.pack()

button_save = tk.Button(root, text="Save", command=save_to_json)
button_save.pack()

root.mainloop()
