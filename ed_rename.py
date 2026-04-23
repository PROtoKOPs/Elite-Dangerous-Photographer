import os
import sys
import time
import json
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import io
import sqlite3
from PIL import Image, ImageTk
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

try:
    import win32clipboard
    import win32event
    import win32api
    import winerror
except ImportError:
    win32clipboard = None
    winerror = None

CONFIG_FILE = "ed_config.json"
CACHE_DB = "thumbs_cache.db"
MAX_CACHE_SIZE = 500  
MUTEX_NAME = "Global\\EliteExplorerAssistantPro_Unique_Mutex_ID"

def init_cache_db():
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            hash TEXT PRIMARY KEY,
            data BLOB,
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

init_cache_db()

LANGS = {
    "RU": {
        "title": "Elite Dangerous Renamer",
        "monitoring_active": "● СИСТЕМА МОНИТОРИНГА АКТИВНА",
        "monitoring_off": "○ МОНИТОРИНГ ВЫКЛЮЧЕН",
        "settings": "НАСТРОЙКИ",
        "open": "Открыть",
        "go_to_file": "Перейти к файлу",
        "copy": "Копировать скриншот",
        "copy_location": "Копировать координаты",
        "delete": "Удалить",
        "delete_confirm": "Удалить этот скриншот?",
        "copied": "Скопировано в буфер!",
        "path_error": "Пути не найдены",
        "save_btn": "СОХРАНИТЬ",
        "screen_dir": "Папка скриншотов:",
        "logs_dir": "Папка логов:",
        "naming_format": "ФОРМАТ ИМЕНИ:",
        "add_date": "Добавлять дату",
        "add_time": "Добавлять время",
        "add_body": "Добавлять название тела",
        "add_coords": "Добавлять координаты",
        "folders_label": "ПАПКИ:",
        "sort_folders": "Сортировать по папкам систем",
        "load_history": "Загружать историю при запуске",
        "lang_label": "ЯЗЫК / LANGUAGE:",
        "select_lang_title": "Выбор языка / Select Language",
        "credits": "Сделано PROtoKOPs",
        "already_running": "Программа уже запущена!",
        "view_grid": "СЕТКА",
        "view_list": "СПИСОК",
        "yes": "ДА",
        "no": "НЕТ"
    },
    "EN": {
        "title": "Elite Dangerous Renamer",
        "monitoring_active": "● MONITORING SYSTEM ACTIVE",
        "monitoring_off": "○ MONITORING DISABLED",
        "settings": "SETTINGS",
        "open": "Open",
        "go_to_file": "Show in folder",
        "copy": "Copy screenshot",
        "copy_location": "Copy location info",
        "delete": "Delete",
        "delete_confirm": "Delete this screenshot?",
        "copied": "Copied to clipboard!",
        "path_error": "Paths not found",
        "save_btn": "SAVE",
        "screen_dir": "Screenshots folder:",
        "logs_dir": "Journal logs folder:",
        "naming_format": "NAMING FORMAT:",
        "add_date": "Add date",
        "add_time": "Add time",
        "add_body": "Add body name",
        "add_coords": "Add coordinates",
        "folders_label": "FOLDERS:",
        "sort_folders": "Sort into system folders",
        "load_history": "Load history on startup",
        "lang_label": "LANGUAGE:",
        "select_lang_title": "Select Language",
        "credits": "Created by PROtoKOPs",
        "already_running": "Application is already running!",
        "view_grid": "GRID",
        "view_list": "LIST",
        "yes": "YES",
        "no": "NO"
    }
}

class CustomConfirm:
    def __init__(self, parent, title, message, lang_keys):
        self.result = False
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#2d2d2d", highlightbackground="#ff8c00", highlightthickness=1)
        x = parent.winfo_pointerx()
        y = parent.winfo_pointery()
        self.win.geometry(f"220x100+{x}+{y}")
        tk.Label(self.win, text=message, fg="white", bg="#2d2d2d", font=("Segoe UI", 9)).pack(pady=15)
        btn_frame = tk.Frame(self.win, bg="#2d2d2d")
        btn_frame.pack(fill="x", side="bottom", pady=10)
        tk.Button(btn_frame, text=lang_keys['yes'], bg="#ff4444", fg="white", relief="flat", width=10, command=self.confirm).pack(side="left", padx=15)
        tk.Button(btn_frame, text=lang_keys['no'], bg="#444", fg="white", relief="flat", width=10, command=self.close).pack(side="right", padx=15)
        self.win.focus_set()
        self.win.grab_set()
        parent.wait_window(self.win)

    def confirm(self):
        self.result = True
        self.win.destroy()

    def close(self):
        self.result = False
        self.win.destroy()

class SingleInstance:
    def __init__(self):
        if win32event:
            self.mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
            self.last_error = win32api.GetLastError()
        else:
            self.last_error = 0
    def is_already_running(self):
        return self.last_error == winerror.ERROR_ALREADY_EXISTS if win32event else False

class EliteJournalReader:
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir
        self.current_system = "Unknown"
        self.current_body = ""
        self.coords = ""

    def update_state(self):
        try:
            if not os.path.exists(self.logs_dir): return
            logs = [os.path.join(self.logs_dir, f) for f in os.listdir(self.logs_dir) if f.startswith('Journal.') and f.endswith('.log')]
            if not logs: return
            latest_log = max(logs, key=os.path.getmtime)
            with open(latest_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event = data.get('event')
                        if event in ['Location', 'FSDJump', 'CarrierJump']:
                            self.current_system = data.get('StarSystem', self.current_system)
                            self.current_body = data.get('Body', "")
                            self.coords = "" 
                        elif event in ['ApproachBody', 'Touchdown']:
                            self.current_body = data.get('Body', self.current_body)
                        elif event == 'Liftoff': self.coords = ""
                        elif event == 'LeaveBody': self.current_body = ""; self.coords = ""
                        if 'Latitude' in data and 'Longitude' in data and event != 'Liftoff':
                            lat, lon = round(data['Latitude'], 2), round(data['Longitude'], 2)
                            self.coords = f"[{lat}, {lon}]"
                    except: continue
        except: pass

    def get_info(self):
        self.update_state()
        return {
            "system": re.sub(r'[\\/*?:"<>|]', "", self.current_system),
            "body": re.sub(r'[\\/*?:"<>|]', "", self.current_body.replace(self.current_system, "").strip()),
            "coords": self.coords,
            "date": time.strftime("%Y-%m-%d"),
            "time": time.strftime("%H-%M-%S")
        }
def resource_path(relative_path):
    
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class App:
    def __init__(self, root):
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.root.withdraw() 
        self.observer = None
        self.file_map = {} 
        self.preview_win = None
        self.tooltip_win = None
        self.last_idx = -1
        self.config = self.load_config()
        self.monitoring_on = tk.BooleanVar(value=True)
        self.view_mode = "grid"
        self.grid_widgets = [] 
        self.grid_photos = {} 
        self.all_files = [] 
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        if not self.config:
            self.first_run_language_select()
        else:
            self.apply_theme_and_start()

    def on_closing(self):
        try:
            if self.observer:
                self.observer.stop()
        except:
            pass
        self.executor.shutdown(wait=False)
        self.root.destroy()
        os._exit(0)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return None
        return None

    def save_config(self, config):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        self.config = config

    def first_run_language_select(self):
        lang_win = tk.Toplevel(self.root)
        lang_win.title("Select Language")
        lang_win.geometry("300x200")
        lang_win.configure(bg="#1e1e1e")
        lang_win.protocol("WM_DELETE_WINDOW", self.root.quit)
        tk.Label(lang_win, text="Choose your language:\nВыберите язык:", fg="white", bg="#1e1e1e").pack(pady=20)
        def set_lang(l):
            self.config = {"lang": l}
            lang_win.destroy()
            self.open_settings_window(is_initial=True)
        tk.Button(lang_win, text="Русский", width=15, command=lambda: set_lang("RU")).pack(pady=5)
        tk.Button(lang_win, text="English", width=15, command=lambda: set_lang("EN")).pack(pady=5)

    def apply_theme_and_start(self):
        l = LANGS[self.config['lang']]
        self.root.deiconify() 
        self.root.title(l['title'])
        try:
            from tkinter import PhotoImage
            icon_path = resource_path("Edr.ico")
            img = PhotoImage(file=icon_path)
            self.root.iconphoto(False, img)
        except Exception as e:
            print(f"Ico load error: {e}")
        self.root.geometry("950x750")
        self.root.minsize(600, 450)
        self.root.configure(bg="#1e1e1e")
        self.show_main_interface()

    def show_main_interface(self):
        for widget in self.root.winfo_children(): widget.destroy()
        l = LANGS[self.config['lang']]
        
        header = tk.Frame(self.root, bg="#2d2d2d", height=60)
        header.pack(fill="x", side="top")
        
        status_text = l['monitoring_active'] if self.monitoring_on.get() else l['monitoring_off']
        status_color = "#00ff00" if self.monitoring_on.get() else "#ff4444"
        
        self.status_label = tk.Label(header, text=status_text, fg=status_color, bg="#2d2d2d", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="left", padx=20, pady=15)

        btn_frame = tk.Frame(header, bg="#2d2d2d")
        btn_frame.pack(side="right", padx=20)

        self.view_btn = tk.Button(btn_frame, text=l['view_grid'] if self.view_mode == "list" else l['view_list'], 
                                  bg="#444", fg="white", relief="flat", command=self.toggle_view, width=8)
        self.view_btn.pack(side="left", padx=5)

        self.toggle_btn = tk.Checkbutton(btn_frame, text="ON/OFF", variable=self.monitoring_on, 
                                         command=self.toggle_monitoring, bg="#444", fg="white", 
                                         selectcolor="#ff8c00", indicatoron=False, relief="flat", padx=10)
        self.toggle_btn.pack(side="left", padx=5)

        tk.Button(btn_frame, text=l['settings'], bg="#444", fg="white", relief="flat", command=self.open_settings_window).pack(side="left", padx=5)

        self.content_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.content_frame.pack(fill="both", expand=True, padx=0, pady=(5, 5))

        self.menu = tk.Menu(self.root, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#ff8c00")
        self.menu.add_command(label=l['open'], command=self.open_file)
        self.menu.add_command(label=l['go_to_file'], command=self.open_folder)
        self.menu.add_command(label=l['copy'], command=self.copy_to_clipboard)
        self.menu.add_command(label=l['copy_location'], command=self.copy_location_to_clipboard)
        self.menu.add_separator()
        self.menu.add_command(label=l['delete'], command=self.delete_file, foreground="red")

        if self.view_mode == "list":
            self.setup_list_view()
        else:
            self.setup_grid_view()

        tk.Label(self.root, text=l['credits'], fg="#444", bg="#1e1e1e", font=("Consolas", 8, "italic")).pack(side="bottom", pady=5)

        self.reader = EliteJournalReader(self.config['logs_dir'])
        
        if self.config.get('load_history', True):
            self.load_history_list()
        if self.monitoring_on.get():
            self.start_watching()

    def setup_list_view(self):
        self.log_box = tk.Listbox(self.content_frame, bg="#121212", fg="#00d2ff", font=("Consolas", 10), borderwidth=0, highlightthickness=0, selectbackground="#333")
        self.log_box.pack(fill="both", expand=True, padx=5)
        self.log_box.bind('<Double-1>', lambda e: self.open_file())
        self.log_box.bind('<Button-3>', self.show_context_menu)
        self.log_box.bind('<Motion>', self.handle_motion)
        self.log_box.bind('<Leave>', lambda e: self.hide_preview())

    def setup_grid_view(self):
        self.grid_widgets = []
        self.grid_photos = {}
        self.grid_canvas = tk.Canvas(self.content_frame, bg="#1e1e1e", highlightthickness=0)
        v_scroll = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.grid_canvas.yview)
        
        self.grid_container = tk.Frame(self.grid_canvas, bg="#1e1e1e")
        self.canvas_window = self.grid_canvas.create_window((0, 0), window=self.grid_container, anchor="nw")
        
        self.grid_canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        self.grid_canvas.pack(side="left", fill="both", expand=True)
        
        self.grid_canvas.bind("<Configure>", self.on_canvas_configure)
        self.grid_canvas.bind_all("<MouseWheel>", lambda e: self.grid_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def on_canvas_configure(self, event):
        self.grid_canvas.itemconfig(self.canvas_window, width=event.width)
        self.reposition_grid()

    def load_history_list(self):
        screen_dir = self.config.get('screen_dir')
        if not screen_dir or not os.path.exists(screen_dir): return
        
        self.all_files = []
        for root_path, dirs, files in os.walk(screen_dir):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.bmp')):
                    full_path = os.path.join(root_path, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                        self.all_files.append((full_path, file, mtime))
                    except: continue
        
        self.all_files.sort(key=lambda x: x[2], reverse=True)
        
        if self.view_mode == "list":
            for path, name, mtime in self.all_files:
                ts = time.strftime('%H:%M:%S', time.localtime(mtime))
                entry = f"[{ts}] {name}"
                self.file_map[entry] = path
                self.log_box.insert(tk.END, entry)
        else:
            self.load_grid_progressive(0)

    def load_grid_progressive(self, start_idx):
        if self.view_mode != "grid": return
        end_idx = min(start_idx + 24, len(self.all_files))
        
        for i in range(start_idx, end_idx):
            path, name, mtime = self.all_files[i]
            ts = time.strftime('%H:%M:%S', time.localtime(mtime))
            self.add_to_grid(f"[{ts}] {name}", path)
        
        self.reposition_grid()
        if end_idx < len(self.all_files):
            self.root.after(100, lambda: self.load_grid_progressive(end_idx))

    def reposition_grid(self):
        if not self.grid_widgets: return
        
        container_width = self.grid_canvas.winfo_width()
        if container_width < 100: 
            container_width = self.root.winfo_width() - 25 
        
        item_width = 210 
        cols = max(1, container_width // item_width)
        
        total_grid_width = cols * item_width
        side_padding = max(5, (container_width - total_grid_width) // 2)

        for i, (frame, _) in enumerate(self.grid_widgets):
            row, col = divmod(i, cols)
            if col == 0:
                frame.grid(row=row, column=col, padx=(side_padding, 5), pady=5, sticky="n")
            else:
                frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")
                
        self.grid_container.update_idletasks()
        self.grid_canvas.config(scrollregion=self.grid_canvas.bbox("all"))

    def add_to_grid(self, entry_text, path, at_start=False):
        frame = tk.Frame(self.grid_container, bg="#2d2d2d", width=200, height=155)
        frame.pack_propagate(False)
        btn = tk.Button(frame, bg="#121212", relief="flat", command=lambda p=path: os.startfile(p))
        btn.pack(fill="both", expand=True)
        full_name = os.path.basename(path)
        name_clean = entry_text.split("] ", 1)[-1] if "] " in entry_text else entry_text
        short_name = (name_clean[:22] + '..') if len(name_clean) > 22 else name_clean
        lbl = tk.Label(frame, text=short_name, fg="#aaa", bg="#2d2d2d", font=("Segoe UI", 8))
        lbl.pack(side="bottom", fill="x")

        self.executor.submit(self._async_load_thumb, path, btn)
        if at_start: self.grid_widgets.insert(0, (frame, path))
        else: self.grid_widgets.append((frame, path))
        
        btn.bind("<Button-3>", lambda e, p=path: self.show_grid_context(e, p))
        btn.bind("<Enter>", lambda e, n=full_name: self.show_tooltip(e, n))
        btn.bind("<Motion>", self.handle_grid_motion) 
        btn.bind("<Leave>", lambda e: self.hide_tooltip())

    def _async_load_thumb(self, path, btn):
        try:
            file_hash = str(abs(hash(path + str(os.path.getmtime(path)))))
            
            conn = sqlite3.connect(CACHE_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM cache WHERE hash=?", (file_hash,))
            row = cursor.fetchone()

            if row:
                img_data = row[0]
                img = Image.open(io.BytesIO(img_data))
            else:
                img = Image.open(path)
                img.thumbnail((190, 110))
                buffer = io.BytesIO()
                img.convert("RGB").save(buffer, "JPEG", quality=75)
                img_data = buffer.getvalue()

                cursor.execute("INSERT OR REPLACE INTO cache (hash, data, timestamp) VALUES (?, ?, ?)", 
                               (file_hash, img_data, time.time()))
                
                cursor.execute("SELECT COUNT(*) FROM cache")
                if cursor.fetchone()[0] > MAX_CACHE_SIZE:
                    cursor.execute("DELETE FROM cache WHERE hash IN (SELECT hash FROM cache ORDER BY timestamp ASC LIMIT 50)")
                
                conn.commit()
            
            conn.close()
            photo = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: self._safe_update_ui(btn, photo, path))
        except: pass

    def _safe_update_ui(self, btn, photo, path):
        try:
            if btn.winfo_exists():
                btn.config(image=photo)
                self.grid_photos[path] = photo
        except (tk.TclError, RuntimeError):
            pass

    def toggle_view(self):
        self.hide_preview()
        self.view_mode = "grid" if self.view_mode == "list" else "list"
        self.show_main_interface()

    def toggle_monitoring(self):
        l = LANGS[self.config['lang']]
        if self.monitoring_on.get():
            self.status_label.config(text=l['monitoring_active'], fg="#00ff00")
            self.start_watching()
        else:
            self.status_label.config(text=l['monitoring_off'], fg="#ff4444")
            if self.observer:
                self.observer.stop()
                self.observer = None

    def start_watching(self):
        if self.observer: self.observer.stop()
        try:
            self.observer = Observer()
            self.observer.schedule(Handler(self), self.config['screen_dir'], recursive=True)
            self.observer.start()
        except: pass

    def add_log(self, text, path):
        timestamp = time.strftime('%H:%M:%S')
        entry = f"[{timestamp}] {text}"
        self.file_map[entry] = path
        if self.view_mode == "list":
            if hasattr(self, 'log_box') and self.log_box.winfo_exists():
                self.log_box.insert(0, entry)
        else:
            self.add_to_grid(entry, path, at_start=True)
            self.reposition_grid()

    def remove_log_by_path(self, path):
        if self.view_mode == "list":
            entry_to_remove = None
            for entry, p in self.file_map.items():
                if p == path:
                    entry_to_remove = entry
                    break
            
            if entry_to_remove:
                idx = 0
                while idx < self.log_box.size():
                    if self.log_box.get(idx) == entry_to_remove:
                        self.log_box.delete(idx)
                        break
                    idx += 1
                if entry_to_remove in self.file_map: del self.file_map[entry_to_remove]
        else:
            for i, (frame, p) in enumerate(self.grid_widgets):
                if p == path:
                    frame.destroy()
                    self.grid_widgets.pop(i)
                    if path in self.grid_photos:
                        del self.grid_photos[path]
                    break
            self.reposition_grid()

    def show_tooltip(self, event, text):
        self.hide_tooltip()
        self.tooltip_win = tk.Toplevel(self.root)
        self.tooltip_win.wm_overrideredirect(True)
        self.tooltip_win.attributes("-topmost", True)
        self.tooltip_win.geometry(f"+{event.x_root+15}+{event.y_root+10}")
        tk.Label(self.tooltip_win, text=text, bg="#333", fg="white", padx=5, pady=2, font=("Segoe UI", 9), highlightbackground="#ff8c00", highlightthickness=1).pack()

    def handle_grid_motion(self, event):
        if self.tooltip_win and self.tooltip_win.winfo_exists():
            self.tooltip_win.geometry(f"+{event.x_root+15}+{event.y_root+10}")

    def hide_tooltip(self):
        if self.tooltip_win:
            self.tooltip_win.destroy()
            self.tooltip_win = None

    def show_grid_context(self, event, path):
        self.current_grid_path = path
        self.menu.post(event.x_root, event.y_root)

    def handle_motion(self, event):
        if self.view_mode != "list": return
        idx = self.log_box.nearest(event.y)
        bbox = self.log_box.bbox(idx)
        
        if not bbox or not (bbox[1] <= event.y <= bbox[1] + bbox[3]):
            self.hide_preview()
            return
            
        if idx != self.last_idx:
            self.last_idx = idx
            path = self.file_map.get(self.log_box.get(idx))
            if path: 
                self.show_preview(path, event.x_root, event.y_root)
        else:

            if self.preview_win and self.preview_win.winfo_exists():
                self.preview_win.geometry(f"+{event.x_root+20}+{event.y_root+10}")

    def show_preview(self, path, x, y):
        self.hide_preview()
        if not os.path.exists(path): return
        try:
            self.preview_win = tk.Toplevel(self.root)
            self.preview_win.wm_overrideredirect(True)
            self.preview_win.geometry(f"+{x+20}+{y+10}")
            self.preview_win.attributes("-topmost", True)
            img = Image.open(path)
            img.thumbnail((300, 200))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(self.preview_win, image=photo, bg="#ff8c00", bd=2)
            lbl.image = photo 
            lbl.pack()
        except: pass

    def hide_preview(self):
        if self.preview_win:
            self.preview_win.destroy()
            self.preview_win = None
        self.last_idx = -1

    def open_settings_window(self, is_initial=False):
        l = LANGS[self.config['lang']]
        settings_win = tk.Toplevel(self.root)
        settings_win.title(l['settings'])
        settings_win.geometry("500x650")
        settings_win.configure(bg="#1e1e1e")
        settings_win.grab_set()
        if is_initial: settings_win.protocol("WM_DELETE_WINDOW", self.root.quit)

        container = tk.Frame(settings_win, bg="#1e1e1e")
        container.pack(expand=True, fill="both", padx=30, pady=20)

        s_entry = self.create_field(container, l['screen_dir'], self.config.get('screen_dir', ""))
        l_entry = self.create_field(container, l['logs_dir'], self.config.get('logs_dir', ""))
        
        tk.Label(container, text=l['lang_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        lang_var = tk.StringVar(value=self.config.get('lang', 'RU'))
        lang_menu = tk.OptionMenu(container, lang_var, "RU", "EN")
        lang_menu.config(bg="#333", fg="white", highlightthickness=0, relief="flat")
        lang_menu.pack(anchor="w", fill="x", pady=(0, 10))

        vars = {
            "show_date": tk.BooleanVar(value=self.config.get('show_date', True)),
            "show_time": tk.BooleanVar(value=self.config.get('show_time', True)),
            "show_body": tk.BooleanVar(value=self.config.get('show_body', True)),
            "show_coords": tk.BooleanVar(value=self.config.get('show_coords', True)),
            "use_folders": tk.BooleanVar(value=self.config.get('use_folders', True)),
            "load_history": tk.BooleanVar(value=self.config.get('load_history', True))
        }

        for text, key in [(l['add_date'], "show_date"), (l['add_time'], "show_time"), (l['add_body'], "show_body"), (l['add_coords'], "show_coords")]:
            tk.Checkbutton(container, text=text, variable=vars[key], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333", activebackground="#1e1e1e").pack(anchor="w")

        tk.Label(container, text=l['folders_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 5))
        tk.Checkbutton(container, text=l['sort_folders'], variable=vars["use_folders"], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333", activebackground="#1e1e1e").pack(anchor="w")
        tk.Checkbutton(container, text=l['load_history'], variable=vars["load_history"], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333", activebackground="#1e1e1e").pack(anchor="w")

        def save():
            new_conf = {
                "screen_dir": s_entry.get(), "logs_dir": l_entry.get(), "lang": lang_var.get(),
                "show_date": vars["show_date"].get(), "show_time": vars["show_time"].get(),
                "show_body": vars["show_body"].get(), "show_coords": vars["show_coords"].get(),
                "use_folders": vars["use_folders"].get(), "load_history": vars["load_history"].get()
            }
            if os.path.exists(new_conf['screen_dir']) and os.path.exists(new_conf['logs_dir']):
                self.save_config(new_conf); settings_win.destroy(); self.apply_theme_and_start()
            else: messagebox.showerror("Error", l['path_error'])

        tk.Button(container, text=l['save_btn'], bg="#ff8c00", command=save, font=("Segoe UI", 10, "bold"), pady=5, padx=20, relief="flat").pack(pady=25)

    def create_field(self, parent, label, val):
        tk.Label(parent, text=label, bg="#1e1e1e", fg="#aaa").pack(anchor="w")
        f = tk.Frame(parent, bg="#1e1e1e"); f.pack(fill="x", pady=(0, 10))
        e = tk.Entry(f, bg="#333", fg="white", relief="flat", insertbackground="white")
        e.insert(0, val); e.pack(side="left", fill="x", expand=True, padx=(0,5), ipady=3)
        tk.Button(f, text="...", bg="#444", fg="white", command=lambda: self.browse(e), relief="flat").pack(side="right")
        return e

    def browse(self, e):
        p = filedialog.askdirectory()
        if p: e.delete(0, tk.END); e.insert(0, p)

    def show_context_menu(self, event):
        idx = self.log_box.nearest(event.y)
        self.log_box.selection_clear(0, tk.END); self.log_box.selection_set(idx)
        self.menu.post(event.x_root, event.y_root)

    def get_selected_path(self):
        if self.view_mode == "grid": return self.current_grid_path
        s = self.log_box.curselection()
        return self.file_map.get(self.log_box.get(s[0])) if s else None

    def open_file(self):
        p = self.get_selected_path()
        if p and os.path.exists(p): os.startfile(p)

    def open_folder(self):
        p = self.get_selected_path()
        if p and os.path.exists(p): subprocess.Popen(f'explorer /select,"{os.path.normpath(p)}"')

    def copy_to_clipboard(self):
        p = self.get_selected_path()
        if p and win32clipboard and os.path.exists(p):
            try:
                img = Image.open(p); out = io.BytesIO()
                img.convert("RGB").save(out, "BMP")
                data = out.getvalue()[14:]
                win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
            except: pass

    def copy_location_to_clipboard(self):
        p = self.get_selected_path()
        if not p: return
        filename = os.path.basename(p)
        coords_match = re.search(r'\[-?\d+\.\d+,\s*-?\d+\.\d+\]', filename)
        system_match = re.search(r'\((.*?)\)', filename)
        result = system_match.group(1) if system_match else (coords_match.group(0) if coords_match else os.path.splitext(filename)[0])
        if result and win32clipboard:
            try:
                win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(result, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except: pass

    def delete_file(self):
        l = LANGS[self.config['lang']]
        p = self.get_selected_path()
        if p and os.path.exists(p):
            confirm_win = CustomConfirm(self.root, l['delete'], l['delete_confirm'], l)
            if confirm_win.result:
                try: 
                    os.remove(p)
                    self.remove_log_by_path(p)
                except Exception as e: 
                    messagebox.showerror("Error", str(e))

class Handler(FileSystemEventHandler):
    def __init__(self, app): 
        self.app = app

    def on_created(self, event):
        
        if event.is_directory:
            return
        
        path = event.src_path
        
        if not path.lower().endswith(('.png', '.jpg', '.bmp')):
            return

        parent_dir = os.path.dirname(os.path.abspath(path))
        base_screen_dir = os.path.abspath(self.app.config['screen_dir'])
        
        if self.app.config.get('use_folders'):
            if parent_dir != base_screen_dir:
                return
        
        time.sleep(1.5) 
        
        if not os.path.exists(path):
            return

        info = self.app.reader.get_info()
        parts = [info['date']] if self.app.config.get("show_date") else []
        if self.app.config.get("show_time"): parts.append(info['time'])
        
        main_info = info['system']
        if self.app.config.get("show_body") and info['body']: main_info += f" — {info['body']}"
        if self.app.config.get("show_coords") and info['coords']: main_info += f" {info['coords']}"
        parts.append(f"({main_info})")
        
        ext = os.path.splitext(path)[1]
        new_filename = f"{' '.join(parts)}{ext}"
        
        target = os.path.join(self.app.config['screen_dir'], info['system']) if self.app.config['use_folders'] else self.app.config['screen_dir']
        
        try:
            if not os.path.exists(target): 
                os.makedirs(target)
            
            new_path = os.path.join(target, new_filename)
            
            if os.path.normpath(path) == os.path.normpath(new_path):
                return

            if os.path.exists(new_path): 
                new_path = os.path.join(target, f"{' '.join(parts)}_{int(time.time())}{ext}")

            shutil.move(path, new_path)
            
            self.app.root.after(100, lambda: self.app.add_log(f"{info['system']}", new_path))
        except Exception as e:
            print(f"Ошибка при перемещении: {e}")

    def on_deleted(self, event):
        if not event.is_directory:
            self.app.root.after(100, lambda: self.app.remove_log_by_path(event.src_path))

if __name__ == "__main__":
    instance = SingleInstance()
    if instance.is_already_running():
        temp_root = tk.Tk(); temp_root.withdraw()
        messagebox.showwarning("Warning", "Application is already running!")
    else:
        root = tk.Tk()
        app = App(root)
        root.mainloop()