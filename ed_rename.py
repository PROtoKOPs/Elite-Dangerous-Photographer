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
import requests
import webbrowser
import winsound
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

# ----- ВЕРСИЯ ПРИЛОЖЕНИЯ -----
VERSION = "1.3"
GITHUB_REPO = "PROtoKOPs/Elite-Dangerous-Photographer"
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
        "title": "Elite Dangerous Photographer v{VERSION}",
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
        "target_dir": "Папка сохранения скриншотов (опционально):",
        "logs_dir": "Папка логов Journal:",
        "naming_format": "ФОРМАТ ИМЕНИ:",
        "add_date": "Добавлять дату",
        "add_time": "Добавлять время",
        "add_body": "Добавлять название тела",
        "add_coords": "Добавлять координаты",
        "folders_label": "ПАПКИ И ФОРМАТ:",
        "sort_folders": "Сортировать по папкам с названием систем",
        "load_history": "Отображать скриншоты из папки (может замедлить запуск при большом количестве файлов)",
        "lang_label": "ЯЗЫК / LANGUAGE:",
        "select_lang_title": "Выбор языка / Select Language",
        "credits": "Сделано PROtoKOPs",
        "already_running": "Программа уже запущена!",
        "view_grid": "СЕТКА",
        "view_list": "СПИСОК",
        "yes": "ДА",
        "no": "НЕТ",
	"save_order": "СОХРАНИТЬ",
        "format_order": "НАСТРОИТЬ ПОРЯДОК",
        "order_title": "Порядок",
        "reset": "СБРОС",
        "up": "Выше",
        "down": "Ниже",
        "field_date": "Дата",
        "field_time": "Время",
        "field_body": "Небесное тело",
        "field_coords": "Координаты",
        "convert_label": "Конвертировать в:",
        "none": "Нет",
"time_mode_label": "ФОРМАТ ВРЕМЕНИ:",
"time_local": "Местное",
"time_utc": "Игровое (UTC)",
"add_cmdr": "Добавлять имя командира",
"sound_label": "ЗВУК УВЕДОМЛЕНИЯ:",
        "check_updates": "ПРОВЕРИТЬ ОБНОВЛЕНИЯ",
        "upd_found": "Доступно обновление!",
        "upd_msg": "Найдена новая версия {v}. Открыть страницу загрузки?",
        "upd_latest": "У вас установлена последняя версия.",
        "upd_error": "Не удалось проверить обновления."
    },
    "EN": {
        "title": "Elite Dangerous Photographer v{VERSION}",
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
        "target_dir": "Screenshots output folder (optional):",
        "logs_dir": "Journal logs folder:",
        "naming_format": "NAMING FORMAT:",
        "add_date": "Add date",
        "add_time": "Add time",
        "add_body": "Add body name",
        "add_coords": "Add coordinates",
        "folders_label": "FOLDERS & FORMAT:",
        "sort_folders": "Sort by folders with the system names",
        "load_history": "Display screenshots from folder (may slow down startup with many files)",
        "lang_label": "LANGUAGE:",
        "select_lang_title": "Select Language",
        "credits": "Created by PROtoKOPs",
        "already_running": "Application is already running!",
        "view_grid": "GRID",
        "view_list": "LIST",
        "yes": "YES",
        "no": "NO",
        "save_order": "SAVE",
        "format_order": "CONSTRUCT ORDER",
        "order_title": "Order",
        "reset": "RESET",
        "up": "Up",
        "down": "Down",
        "field_date": "Date",
        "field_time": "Time",
        "field_body": "Celestial Body",
        "field_coords": "Coordinates",
        "convert_label": "Convert to:",
        "none": "None",
"time_mode_label": "TIME MODE:",
"time_local": "Local",
"time_utc": "In-game (UTC)",
"add_cmdr": "Add Commander name",
"sound_label": "NOTIFICATION SOUND:",
        "check_updates": "CHECK FOR UPDATES",
        "upd_found": "Update available!",
        "upd_msg": "New version {v} is available. Open download page?",
        "upd_latest": "You are using the latest version.",
        "upd_error": "Failed to check for updates."
    }
}

def get_base_path():

    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_sounds_dir():

    base_path = get_base_path()
    path = os.path.join(base_path, "sounds")
    

    if not os.path.exists(path):
        os.makedirs(path)
    
    readme_path = os.path.join(path, "README.txt")
    
    if not os.path.exists(readme_path):
        content = (
            "=== Elite Dangerous Photographer - Sounds Guide ===\n\n"
            "[RU]\n"
            "1. Положите в эту папку любые звуковые файлы в формате .wav\n"
            "2. Откройте настройки в приложении\n"
            "3. В выпадающем списке 'ЗВУК УВЕДОМЛЕНИЯ' выберите ваш файл\n\n"
            "Примечание: Программа видит файлы только в формате .wav\n\n"
            "--------------------------------------------------\n\n"
            "[EN]\n"
            "1. Place any .wav sound files in this folder\n"
            "2. Open the application settings\n"
            "3. Select your file from the 'NOTIFICATION SOUND' dropdown menu\n\n"
            "Note: Only .wav files are supported\n"
        )
        try:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"Не удалось создать README: {e}")
            
    return path
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
        self.current_station = ""
        self.cmdr = ""

    def update_state(self):
        try:
            if not os.path.exists(self.logs_dir): return
            
            logs = [os.path.join(self.logs_dir, f) for f in os.listdir(self.logs_dir) if f.startswith('Journal.') and f.endswith('.log')]
            if logs:
                latest_log = max(logs, key=os.path.getmtime)
                with open(latest_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            event = data.get('event')
                            
                            if event in ['Location', 'FSDJump', 'CarrierJump']:
                                self.current_system = data.get('StarSystem', self.current_system)
                                self.current_body = data.get('Body', "")
                                self.current_station = data.get('StationName', "") if data.get('Docked') else ""
                                self.coords = ""
                            elif event in ['Commander', 'LoadGame']:
                                self.cmdr = data.get('Name', self.cmdr)
                            elif event == 'Docked':
                                self.current_station = data.get('StationName', "")
                                self.coords = ""
                            elif event == 'Undocked':
                                self.current_station = ""

                            elif event in ['ApproachBody', 'Touchdown']:
                                self.current_body = data.get('Body', self.current_body)
                            elif event == 'Liftoff' or event == 'LeaveBody':
                                if event == 'LeaveBody': self.current_body = ""
                                self.coords = ""

                        except: continue

            status_path = os.path.join(self.logs_dir, 'Status.json')
            if os.path.exists(status_path):
                with open(status_path, 'r', encoding='utf-8') as f:
                    try:
                        status_data = json.load(f)
                        if 'Latitude' in status_data and 'Longitude' in status_data and not self.current_station:
                            lat = round(status_data['Latitude'], 2)
                            lon = round(status_data['Longitude'], 2)
                            self.coords = f"[{lat}, {lon}]"
                            
                            if 'BodyName' in status_data:
                                self.current_body = status_data['BodyName']
                    except:
                        pass
                        
        except Exception as e:
            print(f"Update state error: {e}")

    def get_info(self, time_mode='local'):
        self.update_state()
        
        display_coords = self.coords
        if self.current_station:
            display_coords = f"[{self.current_station}]"

       
        if time_mode == 'utc':
            t_struct = time.gmtime()
        else:
            t_struct = time.localtime()

        return {
            "system": re.sub(r'[\\/*?:"<>|]', "", self.current_system),
            "body": re.sub(r'[\\/*?:"<>|]', "", self.current_body.replace(self.current_system, "").strip()),
            "coords": display_coords,
            "date": time.strftime("%Y-%m-%d", t_struct),
            "time": time.strftime("%H-%M-%S", t_struct),
            "cmdr": self.cmdr
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
            Thread(target=self.check_for_updates, args=(True,), daemon=True).start()
     
    def check_for_updates(self, silent=True):
        l = LANGS[self.config['lang']]
        try:

            response = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_v = data['tag_name'].replace('v', '').strip()
                
                if latest_v != VERSION:
                    if silent:
                        self.root.after(0, lambda: self.show_update_notification(latest_v))
                    else:
                        if messagebox.askyesno(l['upd_found'], l['upd_msg'].format(v=latest_v)):
                            webbrowser.open(data['html_url'])
                elif not silent:
                    messagebox.showinfo("Update", l['upd_latest'])
            elif not silent:
                messagebox.showerror("Error", l['upd_error'])
        except:
            if not silent: messagebox.showerror("Error", l['upd_error'])

    def show_update_notification(self, version):
        l = LANGS[self.config['lang']]
        upd_bar = tk.Frame(self.root, bg="#ff8c00", height=30)
        upd_bar.pack(fill="x", side="bottom")
        tk.Label(upd_bar, text=f"{l['upd_found']} ({version})", bg="#ff8c00", fg="black", font=("Segoe UI", 9, "bold")).pack(side="left", padx=10)
        tk.Button(upd_bar, text="DOWNLOAD", bg="black", fg="white", relief="flat", font=("Segoe UI", 8), 
                  command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases")).pack(side="right", padx=10)

    def on_closing(self):
        try:
            if self.observer:
                self.observer.stop()
        except: pass
        self.executor.shutdown(wait=False)
        self.root.destroy()
        os._exit(0)
    def check_width_for_burger(self, event):
        # Если это событие самого главного окна (а не его дочерних элементов)
        if event.widget == self.root:
            # Порог ширины (например, 650 пикселей), при котором кнопки начинают тесниться
            threshold = 650 
            if event.width < threshold:
                self.full_btn_frame.pack_forget() # Прячем панель кнопок
                self.burger_btn.pack(side="right", padx=20) # Показываем бургер
            else:
                self.burger_btn.pack_forget() # Прячем бургер
                self.full_btn_frame.pack(side="right", padx=20) # Возвращаем кнопки

    def show_burger_menu(self):
        self.burger_menu.delete(0, tk.END)
        l = LANGS[self.config['lang']]
        
        # Добавляем пункты в меню
        self.burger_menu.add_command(label=self.buttons_data[0][0], command=self.buttons_data[0][1])
        # Переключатель мониторинга прямо в меню
        mon_label = f"✓ {l['monitoring_active']}" if self.monitoring_on.get() else l['monitoring_off']
        self.burger_menu.add_command(label=mon_label, command=lambda: [self.monitoring_on.set(not self.monitoring_on.get()), self.toggle_monitoring()])
        self.burger_menu.add_separator()
        self.burger_menu.add_command(label=self.buttons_data[1][0], command=self.buttons_data[1][1])
        
        # Показываем меню под кнопкой бургера
        x = self.burger_btn.winfo_rootx()
        y = self.burger_btn.winfo_rooty() + self.burger_btn.winfo_height()
        self.burger_menu.post(x, y)
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    if "target_dir" not in cfg:
                        cfg["target_dir"] = ""
                    if "convert_to" not in cfg:
                        cfg["convert_to"] = "none"
                    return cfg
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
            home = os.path.expanduser("~")
            
            possible_screens = [
                os.path.join(home, "OneDrive", "Изображения", "Frontier Developments", "Elite Dangerous"),
                os.path.join(home, "OneDrive", "Pictures", "Frontier Developments", "Elite Dangerous"),
                os.path.join(home, "Pictures", "Frontier Developments", "Elite Dangerous"),
                os.path.join(home, "Изображения", "Frontier Developments", "Elite Dangerous")
            ]
            

            default_screens = possible_screens[2]
            for p in possible_screens:
                if os.path.exists(p):
                    default_screens = p
                    break
            
            possible_logs = [
                os.path.join(home, "OneDrive", "Saved Games", "Frontier Developments", "Elite Dangerous"),
                os.path.join(home, "Saved Games", "Frontier Developments", "Elite Dangerous")
            ]
            
            default_logs = possible_logs[1]
            for p in possible_logs:
                if os.path.exists(p):
                    default_logs = p
                    break

            self.config = {
                "lang": l, 
                "screen_dir": default_screens, 
                "logs_dir": default_logs,
                "target_dir": "", 
                "convert_to": "none",
                "use_folders": False,
                "load_history": False,
                "show_date": True,
                "show_time": True,
                "show_body": True,
                "show_coords": True,
                "time_mode": "local",
                "show_cmdr": False
            }
            lang_win.destroy()
            self.open_settings_window(is_initial=True)
        tk.Button(lang_win, text="Русский", width=15, command=lambda: set_lang("RU")).pack(pady=5)
        tk.Button(lang_win, text="English", width=15, command=lambda: set_lang("EN")).pack(pady=5)

    def apply_theme_and_start(self):
        l = LANGS[self.config['lang']]
        self.root.deiconify() 
        self.root.title(l['title'].format(VERSION=VERSION))
        
        # Установка иконок
        icon_path = resource_path("Edr.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
                import ctypes
                myappid = f'proto.edrenamer.v{VERSION}' 
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except: pass

        self.root.geometry("950x750")
        self.root.minsize(400, 300)
        self.root.configure(bg="#1e1e1e")
        self.show_main_interface()

    def show_main_interface(self):
        for widget in self.root.winfo_children(): widget.destroy()
        l = LANGS[self.config['lang']]
        
        self.header = tk.Frame(self.root, bg="#2d2d2d", height=60)
        self.header.pack(fill="x", side="top")
        
        status_text = l['monitoring_active'] if self.monitoring_on.get() else l['monitoring_off']
        status_color = "#00ff00" if self.monitoring_on.get() else "#ff4444"
        
        self.status_label = tk.Label(self.header, text=status_text, fg=status_color, bg="#2d2d2d", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="left", padx=20, pady=15)

        # Контейнер для обычных кнопок
        self.full_btn_frame = tk.Frame(self.header, bg="#2d2d2d")
        self.full_btn_frame.pack(side="right", padx=20)

        # Сами кнопки (сохраняем в self, чтобы обращаться из меню)
        self.buttons_data = [
            (l['view_grid'] if self.view_mode == "list" else l['view_list'], self.toggle_view),
            (l['settings'], self.open_settings_window)
        ]

        # Кнопки для полной панели
        self.view_btn = tk.Button(self.full_btn_frame, text=self.buttons_data[0][0], 
                                  bg="#444", fg="white", relief="flat", command=self.buttons_data[0][1], width=10)
        self.view_btn.pack(side="left", padx=5)

        self.toggle_btn = tk.Checkbutton(self.full_btn_frame, text="ON/OFF", variable=self.monitoring_on, 
                                         command=self.toggle_monitoring, bg="#444", fg="white", 
                                         selectcolor="#ff8c00", indicatoron=False, relief="flat", padx=10)
        self.toggle_btn.pack(side="left", padx=5)

        self.settings_btn = tk.Button(self.full_btn_frame, text=self.buttons_data[1][0], 
                                      bg="#444", fg="white", relief="flat", command=self.buttons_data[1][1], width=10)
        self.settings_btn.pack(side="left", padx=5)

        # Кнопка БУРГЕР (изначально скрыта)
        self.burger_btn = tk.Button(self.header, text="☰", bg="#2d2d2d", fg="#ff8c00", 
                                    font=("Segoe UI", 16, "bold"), relief="flat", command=self.show_burger_menu)
        
        # Создаем выпадающее меню для бургера
        self.burger_menu = tk.Menu(self.root, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#ff8c00", font=("Segoe UI", 10))

        # Контент
        self.content_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.content_frame.pack(fill="both", expand=True)

        if self.view_mode == "list": self.setup_list_view()
        else: self.setup_grid_view()

        # Привязываем проверку ширины при изменении размера окна
        self.root.bind("<Configure>", self.check_width_for_burger)

        self.reader = EliteJournalReader(self.config['logs_dir'])
        if self.config.get('load_history', False): self.load_history_list()
        if self.monitoring_on.get(): self.start_watching()

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
        search_dir = self.config.get('target_dir') if self.config.get('target_dir') else self.config.get('screen_dir')
        if not search_dir or not os.path.exists(search_dir): return
        self.all_files = []
        for root_path, dirs, files in os.walk(search_dir):
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
        else: self.load_grid_progressive(0)

    def load_grid_progressive(self, start_idx):
        if self.view_mode != "grid": return
        end_idx = min(start_idx + 24, len(self.all_files))
        for i in range(start_idx, end_idx):
            path, name, mtime = self.all_files[i]
            ts = time.strftime('%H:%M:%S', time.localtime(mtime))
            self.add_to_grid(f"[{ts}] {name}", path)
        self.reposition_grid()
        if end_idx < len(self.all_files): self.root.after(100, lambda: self.load_grid_progressive(end_idx))

    def reposition_grid(self):
        if not self.grid_widgets: return
        container_width = self.grid_canvas.winfo_width()
        if container_width < 100: container_width = self.root.winfo_width() - 25 
        item_width = 210 
        cols = max(1, container_width // item_width)
        total_grid_width = cols * item_width
        side_padding = max(5, (container_width - total_grid_width) // 2)
        for i, (frame, _) in enumerate(self.grid_widgets):
            row, col = divmod(i, cols)
            frame.grid(row=row, column=col, padx=(side_padding if col==0 else 5, 5), pady=5, sticky="n")
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
        tk.Label(frame, text=short_name, fg="#aaa", bg="#2d2d2d", font=("Segoe UI", 8)).pack(side="bottom", fill="x")
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
                img = Image.open(io.BytesIO(row[0]))
            else:
                img = Image.open(path); img.thumbnail((190, 110))
                buffer = io.BytesIO(); img.convert("RGB").save(buffer, "JPEG", quality=75)
                img_data = buffer.getvalue()
                cursor.execute("INSERT OR REPLACE INTO cache (hash, data, timestamp) VALUES (?, ?, ?)", (file_hash, img_data, time.time()))
                conn.commit()
            conn.close()
            photo = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: self._safe_update_ui(btn, photo, path))
        except: pass

    def _safe_update_ui(self, btn, photo, path):
        try:
            if btn.winfo_exists():
                btn.config(image=photo); self.grid_photos[path] = photo
        except: pass

    def toggle_view(self):
        self.hide_preview(); self.view_mode = "grid" if self.view_mode == "list" else "list"
        self.show_main_interface()

    def toggle_monitoring(self):
        l = LANGS[self.config['lang']]
        if self.monitoring_on.get():
            self.status_label.config(text=l['monitoring_active'], fg="#00ff00")
            self.start_watching()
        else:
            self.status_label.config(text=l['monitoring_off'], fg="#ff4444")
            if self.observer: self.observer.stop(); self.observer = None

    def start_watching(self):
        if self.observer: 
            self.observer.stop()
        try:
            path_to_watch = os.path.normpath(self.config['screen_dir'])
            if not os.path.exists(path_to_watch):
                print(f"Путь не найден: {path_to_watch}")
                return
                
            self.observer = Observer()
            self.observer.schedule(Handler(self), path_to_watch, recursive=False) # recursive=False лучше для производительности
            self.observer.start()
        except Exception as e:
            print(f"Ошибка запуска мониторинга: {e}")

    def add_log(self, text, path):
        ts = time.strftime('%H:%M:%S'); entry = f"[{ts}] {text}"
        self.file_map[entry] = path
        if self.view_mode == "list":
            if hasattr(self, 'log_box') and self.log_box.winfo_exists(): self.log_box.insert(0, entry)
        else:
            self.add_to_grid(entry, path, at_start=True); self.reposition_grid()

    def remove_log_by_path(self, path):
        target_path = os.path.normcase(os.path.abspath(path))
        
        if self.view_mode == "list":
            
            entry_to_remove = next((e for e, p in self.file_map.items() 
                                   if os.path.normcase(os.path.abspath(p)) == target_path), None)
            if entry_to_remove:
                for i in range(self.log_box.size()):
                    if self.log_box.get(i) == entry_to_remove: 
                        self.log_box.delete(i)
                        break
                del self.file_map[entry_to_remove]
        else:
            
            for i, (frame, p) in enumerate(self.grid_widgets):
                if os.path.normcase(os.path.abspath(p)) == target_path:
                    frame.destroy()
                    self.grid_widgets.pop(i)
                    break
            
           
            keys_to_del = [k for k in self.grid_photos.keys() 
                          if os.path.normcase(os.path.abspath(k)) == target_path]
            for k in keys_to_del:
                del self.grid_photos[k]
                
            self.reposition_grid()

    def show_tooltip(self, event, text):
        self.hide_tooltip(); self.tooltip_win = tk.Toplevel(self.root)
        self.tooltip_win.wm_overrideredirect(True); self.tooltip_win.attributes("-topmost", True)
        self.tooltip_win.geometry(f"+{event.x_root+15}+{event.y_root+10}")
        tk.Label(self.tooltip_win, text=text, bg="#333", fg="white", padx=5, pady=2, font=("Segoe UI", 9), highlightbackground="#ff8c00", highlightthickness=1).pack()

    def handle_grid_motion(self, event):
        if self.tooltip_win and self.tooltip_win.winfo_exists(): self.tooltip_win.geometry(f"+{event.x_root+15}+{event.y_root+10}")

    def hide_tooltip(self):
        if self.tooltip_win: self.tooltip_win.destroy(); self.tooltip_win = None

    def show_grid_context(self, event, path):
        self.current_grid_path = path; self.menu.post(event.x_root, event.y_root)

    def handle_motion(self, event):
        if self.view_mode != "list": return
        idx = self.log_box.nearest(event.y); bbox = self.log_box.bbox(idx)
        if not bbox or not (bbox[1] <= event.y <= bbox[1] + bbox[3]): self.hide_preview(); return
        if idx != self.last_idx:
            self.last_idx = idx; p = self.file_map.get(self.log_box.get(idx))
            if p: self.show_preview(p, event.x_root, event.y_root)
        elif self.preview_win: self.preview_win.geometry(f"+{event.x_root+20}+{event.y_root+10}")

    def show_preview(self, path, x, y):
        self.hide_preview()
        if not os.path.exists(path): return
        try:
            self.preview_win = tk.Toplevel(self.root); self.preview_win.wm_overrideredirect(True)
            self.preview_win.geometry(f"+{x+20}+{y+10}"); self.preview_win.attributes("-topmost", True)
            img = Image.open(path); img.thumbnail((300, 200)); photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(self.preview_win, image=photo, bg="#ff8c00", bd=2); lbl.image = photo; lbl.pack()
        except: pass

    def hide_preview(self):
        if self.preview_win: self.preview_win.destroy(); self.preview_win = None
        self.last_idx = -1

    def open_settings_window(self, is_initial=False):
        l = LANGS[self.config['lang']]
        settings_win = tk.Toplevel(self.root)
        settings_win.title(l['settings'])
        
        # --- ИСПРАВЛЕНИЕ: Логика размера и скролла ---
        settings_win.resizable(False, True)
        settings_win.geometry("500x890")
        settings_win.minsize(500, 400) # Минимально допустимая высота окна
        settings_win.configure(bg="#1e1e1e")
        settings_win.grab_set()
        
        if is_initial: 
            settings_win.protocol("WM_DELETE_WINDOW", self.root.quit)

        # Создаем Canvas и Scrollbar для прокрутки
        canvas = tk.Canvas(settings_win, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1e1e1e")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=480)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Упаковка скролла
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
        scrollbar.pack(side="right", fill="y")

        # Привязка колесика мыши
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        container = tk.Frame(scrollable_frame, bg="#1e1e1e")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        # --- Дальше идет твой существующий код полей внутри container ---
        s_entry = self.create_field(container, l['screen_dir'], self.config.get('screen_dir', ""))
        t_entry = self.create_field(container, l['target_dir'], self.config.get('target_dir', "")) 
        l_entry = self.create_field(container, l['logs_dir'], self.config.get('logs_dir', ""))

        tk.Label(container, text=l['lang_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        lang_var = tk.StringVar(value=self.config.get('lang', 'RU'))
        tk.OptionMenu(container, lang_var, "RU", "EN").pack(anchor="w", fill="x", pady=(0, 10))

        tk.Label(container, text=l['time_mode_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        time_mode_var = tk.StringVar(value=self.config.get('time_mode', 'local'))
        tm_frame = tk.Frame(container, bg="#1e1e1e")
        tm_frame.pack(anchor="w", fill="x")
        tk.Radiobutton(tm_frame, text=l['time_local'], variable=time_mode_var, value='local', bg="#1e1e1e", fg="white", selectcolor="#333").pack(side="left", padx=5)
        tk.Radiobutton(tm_frame, text=l['time_utc'], variable=time_mode_var, value='utc', bg="#1e1e1e", fg="white", selectcolor="#333").pack(side="left", padx=5)
        
        tk.Label(container, text=l['naming_format'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        
        vars = {
            "show_date": tk.BooleanVar(value=self.config.get('show_date', True)),
            "show_time": tk.BooleanVar(value=self.config.get('show_time', True)),
            "show_body": tk.BooleanVar(value=self.config.get('show_body', True)),
            "show_coords": tk.BooleanVar(value=self.config.get('show_coords', True)),
            "show_cmdr": tk.BooleanVar(value=self.config.get('show_cmdr', False)),
            "use_folders": tk.BooleanVar(value=self.config.get('use_folders', False)),
            "load_history": tk.BooleanVar(value=self.config.get('load_history', False))
        }
        
        for text, key in [(l['add_date'], "show_date"), (l['add_time'], "show_time"), (l['add_body'], "show_body"), (l['add_coords'], "show_coords"), (l['add_cmdr'], "show_cmdr")]:
            tk.Checkbutton(container, text=text, variable=vars[key], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333").pack(anchor="w")
        
        tk.Label(container, text=l['folders_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 5))
        tk.Checkbutton(container, text=l['sort_folders'], variable=vars["use_folders"], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333").pack(anchor="w")
        tk.Checkbutton(container, text=l['load_history'], variable=vars["load_history"], bg="#1e1e1e", fg="#e0e0e0", selectcolor="#333", wraplength=400, justify="left").pack(anchor="w", pady=5)

        conv_frame = tk.Frame(container, bg="#1e1e1e")
        conv_frame.pack(anchor="w", fill="x", pady=5)
        tk.Label(conv_frame, text=l['convert_label'], fg="#aaa", bg="#1e1e1e").pack(side="left")
        
        conv_options = {"none": l['none'], "png": "PNG", "jpg": "JPG"}
        conv_var = tk.StringVar(value=self.config.get('convert_to', 'none'))
        opt_menu = tk.OptionMenu(conv_frame, conv_var, *conv_options.keys())
        opt_menu.config(bg="#333", fg="white", width=10)
        opt_menu.pack(side="left", padx=10)

        tk.Label(container, text=l['sound_label'], fg="#ff8c00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 5))
        sounds_path = get_sounds_dir()
        wav_files = [f for f in os.listdir(sounds_path) if f.endswith('.wav')]
        sound_options = ["none", "Windows Default"] + wav_files
        sound_var = tk.StringVar(value=self.config.get('success_sound', 'none'))
        sound_menu = tk.OptionMenu(container, sound_var, *sound_options)
        sound_menu.config(bg="#333", fg="white")
        sound_menu.pack(anchor="w", fill="x")

        tk.Button(container, text=l['check_updates'], bg="#333", fg="#ff8c00", command=lambda: self.check_for_updates(False)).pack(pady=(20, 10))

        def save():
            new_conf = {
                "screen_dir": s_entry.get(), "target_dir": t_entry.get(), "logs_dir": l_entry.get(), "lang": lang_var.get(),
                "show_date": vars["show_date"].get(), "show_time": vars["show_time"].get(),
                "show_body": vars["show_body"].get(), "show_coords": vars["show_coords"].get(),
                "use_folders": vars["use_folders"].get(), "load_history": vars["load_history"].get(),
                "time_mode": time_mode_var.get(), "show_cmdr": vars["show_cmdr"].get(),
                "success_sound": sound_var.get(), "convert_to": conv_var.get()
            }
            if os.path.exists(new_conf['screen_dir']) and os.path.exists(new_conf['logs_dir']):
                self.save_config(new_conf)
                # Отвязываем события мыши перед закрытием
                canvas.unbind_all("<MouseWheel>")
                settings_win.destroy()
                self.apply_theme_and_start()
            else: 
                messagebox.showerror("Error", l['path_error'])
        
        tk.Button(container, text=l['save_btn'], bg="#ff8c00", command=save, font=("Segoe UI", 10, "bold"), width=20).pack(pady=(0, 25))
    def create_field(self, parent, label, val):
        tk.Label(parent, text=label, bg="#1e1e1e", fg="#aaa").pack(anchor="w")
        f = tk.Frame(parent, bg="#1e1e1e"); f.pack(fill="x", pady=(0, 10))
        e = tk.Entry(f, bg="#333", fg="white", relief="flat"); e.insert(0, val); e.pack(side="left", fill="x", expand=True, padx=(0,5), ipady=3)
        tk.Button(f, text="...", bg="#444", fg="white", command=lambda: self.browse(e)).pack(side="right")
        return e

    def browse(self, e):
        p = filedialog.askdirectory()
        if p: e.delete(0, tk.END); e.insert(0, p)

    def show_context_menu(self, event):
        idx = self.log_box.nearest(event.y); self.log_box.selection_clear(0, tk.END); self.log_box.selection_set(idx)
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
                img = Image.open(p); out = io.BytesIO(); img.convert("RGB").save(out, "BMP")
                data = out.getvalue()[14:]
                win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data); win32clipboard.CloseClipboard()
            except: pass

    def copy_location_to_clipboard(self):
        p = self.get_selected_path()
        if not p: return
        fn = os.path.basename(p)
        coords = re.search(r'\[-?\d+\.\d+,\s*-?\d+\.\d+\]', fn)
        system = re.search(r'\((.*?)\)', fn)
        res = system.group(1) if system else (coords.group(0) if coords else os.path.splitext(fn)[0])
        if res and win32clipboard:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(res, win32clipboard.CF_UNICODETEXT); win32clipboard.CloseClipboard()

    def delete_file(self):
        l = LANGS[self.config['lang']]; p = self.get_selected_path()
        if p and os.path.exists(p):
            if CustomConfirm(self.root, l['delete'], l['delete_confirm'], l).result:
                try: os.remove(p); self.remove_log_by_path(p)
                except Exception as e: messagebox.showerror("Error", str(e))

class Handler(FileSystemEventHandler):
    def __init__(self, app): 
        self.app = app

    def on_created(self, event):

        if event.is_directory or not event.src_path.lower().endswith(('.png', '.jpg', '.bmp', '.jpeg')): 
            return
        
        src_path = os.path.normpath(os.path.abspath(event.src_path))

        config_dir = os.path.normpath(os.path.abspath(self.app.config['screen_dir']))
        
        if os.path.dirname(src_path).lower() != config_dir.lower(): 
            return

        time.sleep(1.5) 
        if not os.path.exists(src_path): 
            return

        info = self.app.reader.get_info(time_mode=self.app.config.get('time_mode', 'local'))

        prefix_parts = []
        if self.app.config.get("show_date"): prefix_parts.append(info['date'])
        if self.app.config.get("show_time"): prefix_parts.append(info['time'])
        prefix = " ".join(filter(None, prefix_parts))

        inner_parts = [info['system']]
        if self.app.config.get("show_body") and info['body']:
            inner_parts.append(f"— {info['body']}")
        if self.app.config.get("show_coords") and info['coords']:
            inner_parts.append(f"— {info['coords']}")
            
        inner_content = " ".join(filter(None, inner_parts))
        new_fn = f"{prefix} ({inner_content})" if prefix else f"({inner_content})"
        
        if self.app.config.get("show_cmdr") and info.get('cmdr'):
            new_fn = f"{new_fn} {info['cmdr']}"

        conv_to = self.app.config.get('convert_to', 'none')
        ext = f".{conv_to}" if conv_to != 'none' else os.path.splitext(src_path)[1]
        
        target_base = self.app.config.get('target_dir') or self.app.config['screen_dir']
        target_path = os.path.join(target_base, info['system'] if self.app.config['use_folders'] else "")
        
        try:
            if not os.path.exists(target_path): 
                os.makedirs(target_path)
            
            final_path = os.path.join(target_path, new_fn + ext)

            if os.path.exists(final_path): 
                new_fn = f"{new_fn}_{int(time.time())}"
                final_path = os.path.join(target_path, new_fn + ext)

            if conv_to != 'none':
                with Image.open(src_path) as img:
                    if conv_to.lower() == 'jpg':
                        img.convert("RGB").save(final_path, "JPEG", quality=95)
                    else:
                        img.save(final_path, conv_to.upper())
                os.remove(src_path)
            else:
                shutil.move(src_path, final_path)

            sound_name = self.app.config.get('success_sound', 'none')
            if sound_name == "Windows Default":

                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound_name != 'none':
                sound_path = os.path.join(get_sounds_dir(), sound_name)
                if os.path.exists(sound_path):
                    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

            self.app.root.after(100, lambda: self.app.add_log(new_fn, final_path))
            
        except Exception as e:
            print(f"Ошибка при обработке скриншота: {e}")

    def on_deleted(self, event): 
        if event.is_directory: return
        deleted_path = os.path.abspath(event.src_path)
        self.app.root.after(100, lambda: self.app.remove_log_by_path(deleted_path))

if __name__ == "__main__":
    instance = SingleInstance()
    if instance.is_already_running():
        tk.Tk().withdraw(); messagebox.showwarning("Warning", "Application is already running!")
    else:
        root = tk.Tk(); app = App(root); root.mainloop()