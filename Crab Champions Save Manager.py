import os, re, shutil, struct, subprocess, sys, zipfile
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

class SavePanel:
    def __init__(self, parent, colors):
        self.frame = tk.Frame(parent, padx=5, pady=5, bg=colors["accent"], borderwidth=2, relief=tk.GROOVE)
        self.tree = ttk.Treeview(self.frame, columns=("SaveName",), show="headings", selectmode=tk.BROWSE)

class InfoPanel:
    def __init__(self, parent, colors, font):
        self.frame = tk.Frame(parent, width=160, height=200, padx=2, pady=2, bg=colors["accent"], borderwidth=2, relief=tk.GROOVE)
        self.label = tk.Label(self.frame, text="Select a save file to read its info", bg=colors["main"], font=font, width=15, wraplength=240)
        self.confirm_button = tk.Button(self.frame, text="Create New Save", font=font, width=13, padx=5, bg=colors["buttons"], activebackground=colors["pressed"], fg=colors["text"])
        self.cancel_button = tk.Button(self.frame, text="Delete Selected Save", font=font, width=16, padx=5, bg=colors["buttons"], activebackground=colors["pressed"], fg=colors["text"])
        self.name_entry = tk.Entry(self.frame)

class CCSMApp:
    def __init__(self):
        self.invalid_chars = '<>:"/\\|?*'
        self.dark_mode = "dark"
        self.info_error = False
        self.copy_in_progress = False
        self.colors = SimpleNamespace(
            light = {
                "main": "#edf7ff",
                "accent": "#b7d2e8",
                "buttons": "#c7e6ff",
                "pressed": "#b3cfe6",
                "text": "black",
                "error": "red"
            },
            dark = {
                "main": "#2d363d",
                "accent": "#4a555e",
                "buttons": "#384c5c",
                "pressed": "#283642",
                "text": "white",
                "error": "brown1"
            }
        )
        self.offsets = {
            "UnlockedWeapons": 62,
            "UnlockedAbilities": 64,
            "UnlockedMeleeWeapons": 67,
            "UnlockedWeaponMods": 65,
            "UnlockedAbilityMods": 66,
            "UnlockedMeleeMods": 64,
            "UnlockedPerks": 60,
            "UnlockedRelics": 61
        }
        self.font = ("Helvetica", 9)
        self.Saved = Path(os.environ["LOCALAPPDATA"]) / "CrabChampions" / "Saved"
        self.SaveGames = self.Saved / "SaveGames"
        
        self.root = tk.Tk()
        self.container = tk.Frame(self.root, padx=5, pady=5, bg=self.colors.light["main"])
        self.play_button = tk.Button(self.container, text="Play Selected Save", font=self.font, height=2, padx=3, bg=self.colors.light["buttons"], activebackground=self.colors.light["pressed"], fg=self.colors.light["text"], command=self.play)
        self.dark_button = tk.Button(self.container, text="Enable Dark Mode", font=self.font, height=1, padx=3, bg=self.colors.dark["buttons"], activebackground=self.colors.light["pressed"], fg=self.colors.dark["text"], command=self.dark_toggle)
        self.save_panel = SavePanel(self.container, self.colors.light)
        self.save_panel.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.info_panel = InfoPanel(self.container, self.colors.light, self.font)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.layout("Treeview", [
            ('Treeview.padding', {
                'sticky': 'nswe',
                'children': [
                    ('Treeview.treearea', {'sticky': 'nswe'})
                ]
            })
        ])
        
    def unlocked_counts(self, filename):
        if (data := load_bytes(filename)):
            results = {}
            for prop, rel_offset in self.offsets.items():
                idx = data.find(prop.encode("utf-8"))
                if idx == -1:
                    return None
                block = data[idx:idx + 80]
                if rel_offset + 4 > len(block):
                    return None
                results[prop] = struct.unpack("<i", block[rel_offset:rel_offset + 4])[0]
            return results
        else:
            return None

    def challenge_count(self, filename):
        data = load_bytes(filename)
        start = data.find(b"Challenges")
        if start == -1:
            return None
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

    def refresh_list(self):
        save_tree = self.save_panel.tree
        save_tree.delete(*save_tree.get_children())
        folders = [("[Last Used Save]" if f.name == "SaveGames" else f.name) for f in self.Saved.iterdir() if f.is_dir()]
        folders.sort(key=lambda name: (name != "[Last Used Save]", name))
        
        for name in folders:
            if name not in ["Config", "Logs", "New Save Template"]:
                save_tree.insert("", tk.END, values=(name,))

    def update_info_text(self, new_text: str):
        color = getattr(self.colors, self.dark_mode)
        if new_text[0:5] == "Error":
            self.info_panel.label.config(fg=color["error"], text=new_text)
            self.info_error = True
        else:
            self.info_panel.label.config(fg=color["text"], text=new_text)
            self.info_error = False

    def confirm(self, save_path=None):
        save_tree = self.save_panel.tree
        info_label = self.info_panel.label
        confirm_button = self.info_panel.confirm_button
        cancel_button = self.info_panel.cancel_button
        name_entry = self.info_panel.name_entry
        
        if save_path:
            if save_path.exists():
                shutil.rmtree(save_path)
                self.update_info_text("Select a save file to read its info")
            else:
                self.update_info_text("Error: Save file not found")
                
            self.refresh_list()
            self.reset_buttons()
        else:
            new_name = name_entry.get().strip()

            if not new_name:
                self.update_info_text("Error: Name cannot be blank")
                return
            if any(ch in self.invalid_chars for ch in new_name):
                self.update_info_text(f"Error: Entered name contains invalid characters ({self.invalid_chars})")
                return
            if (self.Saved / new_name).exists() or read_desc(self.SaveGames) == new_name:
                self.update_info_text("Error: A save file with that name already exists")
                return
            
            self.refresh_list()
            name_entry.grid_remove()
            
            if save_tree.get_children() == 0:
                self.new_save(new_name)
            else:
                self.copy_in_progress = True
                self.update_info_text(f"Make a new save from scratch:\n\n- or -\n\nSelect a save to copy:")
                confirm_button.config(text="New Empty Save", command=lambda: self.new_save(new_name))
                cancel_button.config(text="Copy Selected Save", command=lambda: self.copy_save(new_name))

    def cancel(self):
        self.refresh_list()
        self.info_panel.name_entry.grid_remove()
        if self.save_panel.tree.selection():
            self.on_select()
        else:
            self.update_info_text("Select a save file to read its info")
            self.reset_buttons()        
        
    def reset_buttons(self):
        self.info_panel.confirm_button.config(text="Create New Save", command=self.create)
        self.info_panel.cancel_button.config(text="Delete Selected Save", command=self.delete)

    def create(self):
        info_panel = self.info_panel
        
        info_panel.name_entry.delete(0, tk.END)
        info_panel.name_entry.grid(row=1, column=0, sticky="nsew", padx=5, pady=5, columnspan=2)
        self.update_info_text("Enter a name for the new save")
        info_panel.confirm_button.config(text="Confirm", command=self.confirm)
        info_panel.cancel_button.config(text="Cancel", command=self.cancel)
            
    def delete(self):
        info_panel = self.info_panel
        
        selected = self.save_panel.tree.selection()
        if selected:
            save_name = self.save_panel.tree.item(selected[0], "values")[0]
            save_path = self.Saved / save_name

            if save_name == "[Last Used Save]":
                self.update_info_text("Error: Cannot erase the last used save file")
            else:
                self.update_info_text(f"Delete '{save_name}'?\nThis cannot be undone.")
                info_panel.confirm_button.config(text="Confirm", command=lambda: self.confirm(save_path))
                info_panel.cancel_button.config(text="Cancel", command=self.cancel)
        else:
            self.update_info_text("Error: No save file selected")

    def save_update(self, new_name):
        write_desc(self.Saved / new_name, new_name)
        self.refresh_list()
        
        for item_id in self.save_panel.tree.get_children():
            values = self.save_panel.tree.item(item_id, "values")
            if values and values[0] == new_name:
                self.save_panel.tree.selection_set(item_id)
                self.save_panel.tree.focus(item_id)
                self.save_panel.tree.see(item_id)
                break
        
        self.reset_buttons()
        self.on_select()
    
    def new_save(self, new_name):
        self.copy_in_progress = False
        (self.Saved / new_name).mkdir()
        (self.Saved / new_name / "SaveSlot.sav").touch(exist_ok=False)
        self.save_update(new_name)

    def copy_save(self, new_name):
        self.copy_in_progress = False
        selected = self.save_panel.tree.selection()
        
        if not selected:
            self.update_info_text("Error: No save file selected")
            return
        else:
            selected_name = self.save_panel.tree.item(selected[0], "values")[0]
            if selected_name == "[Last Used Save]":
                save_path = self.Saved / "SaveGames"
            else:
                save_path = self.Saved / selected_name
        
        shutil.copytree(save_path, self.Saved / new_name)
        self.save_update(new_name)

    def on_select(self, *e):
        if not self.copy_in_progress:
            color = getattr(self.colors, self.dark_mode)
            selected = self.save_panel.tree.selection()
            
            if selected:
                self.info_panel.name_entry.grid_remove()
                self.reset_buttons()
                selected_name = self.save_panel.tree.item(selected[0], "values")[0]
                
                if selected_name == "[Last Used Save]":
                    save_name = "SaveGames"
                else:
                    save_name = selected_name
                save_path = self.Saved / save_name / "SaveSlot.sav"

                if load_bytes(save_path) == b"":
                    self.update_info_text("New Save File\n\nNo info to show")
                else:
                    if (unlocks := self.unlocked_counts(save_path)):
                        unlocks = list(unlocks.values())
                    else:
                        self.update_info_text("Error: Could not read save file")
                        return
                    mod_time = datetime.fromtimestamp(save_path.stat().st_mtime).strftime("%A, %B %d, %Y  %H:%M")
                    total = self.challenge_count(save_path)
                    self.update_info_text(f"""
Save name: {read_desc(self.Saved / save_name)}

Last Updated:
{mod_time}

Challenges: {total} / 110
Unlocked weapons: {unlocks[0]} / 20
Unlocked abilities: {unlocks[1]} / 7
Unlocked melee weapons: {unlocks[2]} / 5
Unlocked weapon mods: {unlocks[3]} / 90
Unlocked ability mods: {unlocks[4]} / 43
Unlocked melee mods: {unlocks[5]} / 12
Unlocked perks: {unlocks[6]} / 107
Unlocked relics: {unlocks[7]} / 53
""")

    def dark_toggle(self):
        self.dark_mode = ("light" if self.dark_mode == "dark" else "dark")
        color = getattr(self.colors, self.dark_mode)
        
        self.style.configure("Treeview", background=color["main"], fieldbackground=color["main"], foreground=color["text"])
        self.style.configure("Treeview.Heading", background=color["buttons"], foreground=color["text"], borderwidth = 0)
        self.style.map("Treeview.Heading", background=[("active", color["buttons"])])
        self.container.config(bg=color["main"])
        self.info_panel.label.config(bg=color["main"], fg=(color["error"] if self.info_error else color["text"]))
        self.save_panel.frame.config(bg=color["accent"])
        self.info_panel.frame.config(bg=color["accent"])
        for button in [self.info_panel.confirm_button, self.info_panel.cancel_button, self.play_button, self.dark_button]:
            button.config(bg=color["buttons"], activebackground=color["pressed"], fg=color["text"], activeforeground=color["text"])
        self.dark_button.config(text=f"Enable {'Light' if self.dark_mode == 'dark' else 'Dark'} Mode")
        
    def play(self):
        selected = self.save_panel.tree.selection()
        
        if not selected:
            self.update_info_text("Error: No save selected")
            return
        
        save_name = self.save_panel.tree.item(selected[0], "values")[0]
        save_path = self.Saved / save_name

        if save_name != "[Last Used Save]":
            if self.SaveGames.exists():
                self.SaveGames.rename(self.Saved / read_desc(self.SaveGames))
            save_path.rename(self.Saved / "SaveGames")

        subprocess.Popen(["start", "steam://rungameid/774801"], shell=True)
        self.root.destroy()

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

def write_desc(folder: Path, name: str):
    desc_file = folder / ".description.txt"
    with open(desc_file, "w", encoding="utf-8") as f:
        f.write(name)

def read_desc(folder: Path) -> str | None:
    desc_file = folder / ".description.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return None

def load_bytes(filename):
    try:
        f = open(filename, "rb")
    except:
        return None
    else:
        return f.read()

def main():
    window = CCSMApp()
    
    window.root.title("Crab Champions Save Manager")
    window.root.iconbitmap(str(resource_path("crab_icon.ico")))
    window.root.resizable(False, False)

    if window.Saved.exists():
        window.root.geometry("420x350")
        window.container.place(x=0, y=0, relwidth=1, relheight=1)
        window.save_panel.tree.column("SaveName", width=0, anchor="w")
        window.save_panel.tree.heading("SaveName", text="Saves:")
        window.save_panel.frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=6)
        window.save_panel.tree.pack(fill=tk.BOTH, expand=True)
        window.info_panel.frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=6, rowspan=3)
        window.info_panel.label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5, columnspan=2)
        window.info_panel.confirm_button.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        window.info_panel.cancel_button.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
        window.dark_button.grid(row=1, column=0, sticky="nsew", padx=5)
        window.play_button.grid(row=2, column=0, sticky="nsew", padx=5, pady=7)

        window.container.grid_columnconfigure(0, weight=1)
        window.container.grid_columnconfigure(1, weight=0)
        window.container.grid_rowconfigure(0, weight=1)
        window.container.grid_rowconfigure(1, weight=0)
        window.info_panel.frame.grid_rowconfigure(0, weight=1)

        window.reset_buttons()
        window.dark_toggle()
        window.refresh_list()
    else:
        window.root.geometry("350x100")
        window.dark_toggle()
        window.container.pack(fill=tk.BOTH, expand=True)
        window.update_info_text('Error: "Saved" folder not found')
        window.info_panel.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        window.info_panel.label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    window.root.mainloop()

if __name__ == "__main__":
    if (saved_path := Path(os.environ["LOCALAPPDATA"]) / "CrabChampions" / "Saved").exists():
        for item in saved_path.iterdir():
            if item.is_dir() and item.name not in ["Config", "Logs", "New Save Template"]:
                if not read_desc(item):
                    if item.name == "SaveGames":
                        write_desc(item, "Initial Save")
                    else:
                        write_desc(item, item.name)
    main()
