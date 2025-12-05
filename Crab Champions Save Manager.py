import sys, os, re, struct, shutil, subprocess, zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from datetime import datetime

# FUNCTIONS

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

def extract_resources(zip_path, target_folder):
    target_folder.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_folder)

def write_desc(folder: Path, name: str):
    desc_file = folder / ".description.txt"
    with open(desc_file, "w", encoding="utf-8") as f:
        f.write(name)

def read_desc(folder: Path) -> str | None:
    desc_file = folder / ".description.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return None

def list_refresh():
    if len(save_list.get_children()) > 0:
        for item in save_list.get_children():
            save_list.delete(item)
    folders = [f for f in save_folder.iterdir() if f.is_dir()]
    for item in folders:
        if item.name == "SaveGames":
            save_list.insert("", tk.END, values=("[Latest Save]",))
    
    for item in folders:
        if item.is_dir() and item.name not in ["Config", "Logs", "SaveGames", "New Save Template"]:
            save_list.insert("", tk.END, values=(item.name,))

def load_bytes(filename):
    with open(filename, "rb") as f:
        return f.read()
    
def read_array_length(data, property_name, offset_in_block, window_bytes=3000):
    idx = data.find(property_name.encode("utf-8"))
    if idx == -1:
        return None
    block = data[idx:idx + window_bytes]
    if offset_in_block + 4 > len(block):
        return None
    return struct.unpack("<i", block[offset_in_block:offset_in_block + 4])[0]

def read_unlocked_counts(filename, cats):
    data = load_bytes(filename)
    results = {}
    for prop, rel_offset in cats.items():
        val = read_array_length(data, prop, rel_offset)
        results[prop] = val
    return results

def read_bools(block, pos):
    start = pos + len(b"BoolProperty")
    tail = block[start:start+32]
    if len(tail) > 9:
        return tail[9]
    return None

def challenge_count(filename):
    with open(filename, "rb") as f:
        data = f.read()

    start = data.find(b"Challenges")
    if start == -1:
        return 0
    block = data[start:start+100000]

    total_true = 0
    for m in re.finditer(b"bChallengeCompleted", block):
        bp = block.find(b"BoolProperty", m.start(), m.start()+160)
        if bp != -1:
            start = bp + len(b"BoolProperty")
            tail = block[start:start+32]
            if len(tail) > 9 and tail[9] == 1:
                total_true += 1

    return total_true

def confirm(save_path=None):
    if save_path:
        if save_path.exists():
            shutil.rmtree(save_path)
            info_label.config(text="Select a save file to read its info")
        else:
            info_label.config(text="Error: Save not found")
        list_refresh()
        confirm_button.config(text="Create New Save", command=create)
        cancel_button.config(text="Delete Selected Save", command=delete)
    else:
        new_name = name_entry.get().strip()
        invalid_chars = '<>:"/\\|?*'

        if not new_name:
            info_label.config(text="Error: Name cannot be blank")
            return
        if any(ch in invalid_chars for ch in new_name):
            info_label.config(text=f"Error: Name contains invalid characters ({invalid_chars})")
            return
        if (save_folder / new_name).exists() or read_desc(savegames) == new_name:
            info_label.config(text="Error: A save with that name already exists")
            return
        
        list_refresh()
        name_entry.grid_remove()
        
        if save_list.get_children() == 0:
            new_save(new_name)
        else:
            save_list.unbind("<<TreeviewSelect>>")
            info_label.config(text=f"Make a new save from scratch:\n\n- or -\n\nSelect a save to copy:")
            confirm_button.config(text="New Empty Save", command=lambda: new_save(new_name))
            cancel_button.config(text="Copy Current Save", command=lambda: copy_save(new_name))

def cancel():
    list_refresh()
    name_entry.grid_remove()
    if save_list.selection():
        on_select()
    else:
        info_label.config(text="Select a save file to read its info")
        confirm_button.config(text="Create New Save", command=create)
        cancel_button.config(text="Delete Selected Save", command=delete)        
    
def play():
    selected = save_list.selection()
    if not selected:
        info_label.config(text="Error: No save selected")
        return
    
    save_name = save_list.item(selected[0], "values")[0]
    save_path = save_folder / save_name

    if save_name != "[Latest Save]":
        if savegames.exists():
            savegames.rename(save_folder / read_desc(savegames))
        save_path.rename(save_folder / "SaveGames")

    subprocess.Popen(["start", "steam://rungameid/774801"], shell=True)
    root.destroy()

def create():
    name_entry.delete(0, tk.END)
    name_entry.grid(row=1, column=0, sticky="nsew", padx=5, pady=5, columnspan=2)
    info_label.config(text="Enter a name for the new save:")
    confirm_button.config(text="Confirm", command=confirm)
    cancel_button.config(text="Cancel", command=cancel)
        
def delete():
    selected = save_list.selection()
    if selected:
        item_id = selected[0]
        values = save_list.item(item_id, "values")
        save_name = values[0]
        save_path = save_folder / save_name

        if save_name == "[Latest Save]":
            info_label.config(text=f"Cannot erase the main save folder.")
        else:
            info_label.config(text=f"Delete '{save_name}'?\nThis cannot be undone.")
            confirm_button.config(text="Confirm", command=lambda: confirm(save_path))
            cancel_button.config(text="Cancel", command=cancel)
        
def new_save(new_name):
    (save_folder / new_name).mkdir()
    write_desc(save_folder / new_name, new_name)
    (save_folder / new_name / "SaveSlot.sav").touch(exist_ok=False)
    list_refresh()
    for item_id in save_list.get_children():
        values = save_list.item(item_id, "values")
        if values and values[0] == new_name:
            save_list.selection_set(item_id)
            save_list.focus(item_id)
            save_list.see(item_id)
            break
    confirm_button.config(text="Create New Save", command=create)
    cancel_button.config(text="Delete Selected Save", command=delete)
    save_list.bind("<<TreeviewSelect>>", lambda e: on_select(e))
    on_select()

def copy_save(new_name):
    selected = save_list.selection()
    if not selected:
        info_label.config(text="Error: No save selected.")
        return
    else:
        selected_name = save_list.item(selected[0], "values")[0]
        if selected_name == "[Latest Save]":
            save_path = save_folder / "SaveGames"
        else:
            save_path = save_folder / selected_name
    
    shutil.copytree(save_path, save_folder / new_name)
    write_desc(save_folder / new_name, new_name)
    list_refresh()
    for item_id in save_list.get_children():
        values = save_list.item(item_id, "values")
        if values and values[0] == new_name:
            save_list.selection_set(item_id)
            save_list.focus(item_id)
            save_list.see(item_id)
            break
    confirm_button.config(text="Create New Save", command=create)
    cancel_button.config(text="Delete Selected Save", command=delete)
    save_list.bind("<<TreeviewSelect>>", lambda e: on_select(e))
    on_select()

def on_select(*e):
    selected = save_list.selection()
    if selected:
        name_entry.grid_remove()
        confirm_button.config(text="Create New Save", command=create)
        cancel_button.config(text="Delete Selected Save", command=delete)
        info_label.config(text="Select a save file to read its info:")
        selected_name = save_list.item(selected[0], "values")[0]
        if selected_name == "[Latest Save]":
            save_name = "SaveGames"
        else:
            save_name = selected_name
        save_path = save_folder / save_name / "SaveSlot.sav"

        if not load_bytes(save_path):
            info_label.config(text="New Save File\n\nNo info to show")
        else:
            unlocks = list(read_unlocked_counts(save_path, cats).values())
            mod_time = datetime.fromtimestamp(save_path.stat().st_mtime).strftime("%A, %B %d, %Y  %H:%M")
            total = challenge_count(save_path)
            info_label.config(text=f"""
Save name: {read_desc(save_folder / save_name)}

Last Updated:
{mod_time}

Achievements: {total} / 110
Unlocked weapons: {unlocks[0]} / 20
Unlocked abilities: {unlocks[1]} / 7
Unlocked melee weapons: {unlocks[2]} / 5
Unlocked weapon mods: {unlocks[3]} / 90
Unlocked ability mods: {unlocks[4]} / 43
Unlocked melee mods: {unlocks[5]} / 12
Unlocked perks: {unlocks[6]} / 107
Unlocked relics: {unlocks[7]} / 53
""")

def dark_mode():
    global dark_toggle
    if dark_toggle:
        style.configure("Treeview", background=light_color_main, fieldbackground=light_color_main, foreground="black")
        container.config(bg=light_color_main)
        save_frame.config(bg=light_color_accent)
        for button in [confirm_button, cancel_button, play_button]:
            button.config(bg=light_color_buttons, fg="black")
        info_frame.config(bg=light_color_accent)
        info_label.config(bg=light_color_main, fg="black")
        style.configure("Treeview.Heading", background=light_color_buttons, foreground="black")
        style.map("Treeview.Heading",
            background=[("active", light_color_buttons)]
        )
        dark_mode.config(bg=dark_color_buttons, fg="white", text="Enable Dark Mode")
        dark_toggle = False
    else:
        style.configure("Treeview", background=dark_color_main, fieldbackground=dark_color_main, foreground="white")
        container.config(bg=dark_color_main)
        save_frame.config(bg=dark_color_accent)
        for button in [confirm_button, cancel_button, play_button]:
            button.config(bg=dark_color_buttons, fg="white")
        info_frame.config(bg=dark_color_accent)
        info_label.config(bg=dark_color_main, fg="white")
        style.configure("Treeview.Heading", background=dark_color_buttons, foreground="white")
        style.map("Treeview.Heading",
            background=[("active", dark_color_buttons)]
        )
        dark_mode.config(bg=light_color_buttons, fg="black", text="Enable Light Mode")
        dark_toggle = True

# GLOBAL VARIABLES

dark_toggle = False
dark_color_main = "#2d363d"
dark_color_accent = "#4a555e"
dark_color_buttons = "#384c5c"
light_color_main = "#edf7ff"
light_color_accent = "#b7d2e8"
light_color_buttons = "#c7e6ff"
global_font = ("Helvetica", 9)
save_folder = Path(os.environ["LOCALAPPDATA"]) / "CrabChampions" / "Saved"
savegames = save_folder / "SaveGames"

offsets = [10141, 10935, 11725, 12482, 13246, 14038, 14804, 15594, 16397,
           17208, 17969, 18742, 19522, 20299, 21067, 21825, 22612, 23396,
           24174, 24955, 25726, 26518, 27284, 28036, 28796, 29560, 30387,
           31186, 31944, 32719, 33533, 34354, 35169, 35972, 36767, 37590,
           38412, 39249, 40090, 40917, 41714, 42575, 43439, 44218, 45035,
           45840, 46641, 47433, 48242, 49025, 49841, 50644, 51465, 52257,
           53066, 53862, 54675, 55479, 56300, 57110, 57937, 58731, 59542,
           60350, 61175, 61987, 62816, 63620, 64441, 65243, 66062, 66868,
           67680, 68466, 69254, 70046, 70850, 71657, 72456, 73264, 74084,
           74889, 75701, 76477, 77255, 78066, 78874, 79699, 80499, 81316,
           82116, 82933, 83731, 84546, 85352, 86175, 86975, 87792, 88580,
           89385, 90177, 90986, 91778, 92587, 93381, 94192, 94984, 95793, 96561]

root = tk.Tk()
style = ttk.Style()
style.theme_use("clam")
style.layout("Treeview", [
    ('Treeview.padding', {
        'sticky': 'nswe',
        'children': [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ]
    })
])
style.configure("Treeview", background=light_color_main, fieldbackground=light_color_main, foreground="black")
style.configure("Treeview.Heading", background=light_color_buttons, foreground="black", borderwidth = 0)
style.map("Treeview.Heading",
    background=[("active", light_color_buttons)]  # hover/pressed color
)
container = tk.Frame(root, padx=5, pady=5, bg=light_color_main)
save_frame = tk.Frame(container, padx=5, pady=5, bg=light_color_accent, borderwidth=2, relief=tk.GROOVE)
save_list = ttk.Treeview(save_frame, columns=("SaveName",), show="headings", selectmode="browse")
info_frame = tk.Frame(container, width=160, height=200, padx=2, pady=2, bg=light_color_accent, borderwidth=2, relief=tk.GROOVE)
info_label = tk.Label(info_frame, text="Select a save file to read its info", bg=light_color_main, font=global_font, width=15, wraplength=240)
confirm_button = tk.Button(info_frame, text="Create New Save", font=global_font, width=13, padx=5, bg=light_color_buttons, fg="black", command=create)
cancel_button = tk.Button(info_frame, text="Delete Selected Save", font=global_font, width=16, padx=5, bg=light_color_buttons, fg="black", command=delete)
play_button = tk.Button(container, text="Play Selected Save", font=global_font, height=2, padx=3, bg=light_color_buttons, fg="black", command=play)
dark_mode = tk.Button(container, text="Enable Dark Mode", font=global_font, height=1, padx=3, bg=dark_color_buttons, fg="white", command=dark_mode)
name_entry = tk.Entry(info_frame)
cats = {
    "UnlockedWeapons": 62,
    "UnlockedAbilities": 64,
    "UnlockedMeleeWeapons": 67,
    "UnlockedWeaponMods": 65,
    "UnlockedAbilityMods": 66,
    "UnlockedMeleeMods": 64,
    "UnlockedPerks": 60,
    "UnlockedRelics": 61,
}

# MAIN SCRIPT

def main():    
    root.geometry("420x350")
    root.title("Crab Champions Save Manager")
    root.iconbitmap(str(resource_path("crab_icon.ico")))
    root.resizable(False, False)

    container.place(x=0, y=0, relwidth=1, relheight=1)

    save_list.column("SaveName", width=0, anchor="w")
    save_list.heading("SaveName", text="Saves:")

    save_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=6)
    save_list.pack(fill=tk.BOTH, expand=True)
    info_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=6, rowspan=3)
    info_label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5, columnspan=2)
    confirm_button.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
    cancel_button.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
    dark_mode.grid(row=1, column=0, sticky="nsew", padx=5)
    play_button.grid(row=2, column=0, sticky="nsew", padx=5, pady=7)

    container.grid_columnconfigure(0, weight=1)
    container.grid_columnconfigure(1, weight=0)
    container.grid_rowconfigure(0, weight=1)
    container.grid_rowconfigure(1, weight=0)
    info_frame.grid_rowconfigure(0, weight=1)

    list_refresh()
    save_list.bind("<<TreeviewSelect>>", lambda e: on_select(e))
    
    root.mainloop()

if __name__ == "__main__":
    for item in save_folder.iterdir():
        if item.is_dir() and item.name not in ["Config", "Logs", "New Save Template"]:
            if not read_desc(item):
                if item.name == "SaveGames":
                    write_desc(item, "Initial Save")
                else:
                    write_desc(item, item.name)
    main()
