import os
import json
import subprocess
import webbrowser
import serial
import serial.tools.list_ports
import time
import ctypes
from datetime import datetime

BAUDRATE = 9600

ARDUINO_KEYWORDS = ["arduino", "ch340", "ch341", "ftdi", "usb serial", "usb-serial"]

MACRO_KEY_MAP = {
    "CTRL": 0x11, "CONTROL": 0x11,
    "SHIFT": 0x10,
    "ALT": 0x12,
    "WIN": 0x5B, "WINDOWS": 0x5B,
    "TAB": 0x09, "SPACE": 0x20, "ENTER": 0x0D, "ESC": 0x1B,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
    "DELETE": 0x2E, "DEL": 0x2E, "BACKSPACE": 0x08
}
for i in range(1, 13):
    MACRO_KEY_MAP[f"F{i}"] = 0x6F + i
for i in range(10):
    MACRO_KEY_MAP[str(i)] = 0x30 + i
for i in range(26):
    MACRO_KEY_MAP[chr(65 + i)] = 0x41 + i


def trova_porta_arduino():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if any(kw in description or kw in manufacturer for kw in ARDUINO_KEYWORDS):
            print(f"[DEBUG] Arduino found on {port.device}: {port.description}")
            return port.device
    if ports:
        print(f"[DEBUG] No Arduino signature found, defaulting to first port: {ports[0].device}")
        return ports[0].device
    print("[ERROR] No serial ports found.")
    return None

PORTA_ARDUINO = trova_porta_arduino()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "consoledeck.log")

# Стан вибраної кнопки
pulsante_selezionato = None

# Внутрішній стан для ГУЧНОСТІ
last_volume_value = 0
volume_step_accumulator = 0
is_muted = False
last_exe_launch_time = 0.0
IS_WINDOWS = os.name == "nt"


LINUX_KEY_MAP = {
    "CTRL": "ctrl", "CONTROL": "ctrl",
    "SHIFT": "shift",
    "ALT": "alt",
    "WIN": "super", "WINDOWS": "super",
    "TAB": "Tab", "SPACE": "space", "ENTER": "Return", "ESC": "Escape",
    "UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right",
    "HOME": "Home", "END": "End", "PGUP": "Page_Up", "PGDN": "Page_Down",
    "DELETE": "Delete", "DEL": "Delete", "BACKSPACE": "BackSpace"
}
for i in range(1, 13):
    LINUX_KEY_MAP[f"F{i}"] = f"F{i}"
for i in range(10):
    LINUX_KEY_MAP[str(i)] = str(i)
for i in range(26):
    LINUX_KEY_MAP[chr(65 + i)] = chr(97 + i)


def default_config():
    config = {}
    for i in range(1, 10):
        config[f"BUTTON_{i}"] = {"type": "none", "value": "", "label": f"Button {i}"}
    config["BUTTON_1"] = {"type": "link", "value": "https://www.youtube.com", "label": "YouTube"}
    return config


def normalize_config(config):
    if not isinstance(config, dict):
        return default_config()

    normalized = default_config()
    for i in range(1, 10):
        key = f"BUTTON_{i}"
        raw = config.get(key, {})
        if not isinstance(raw, dict):
            continue

        action_type = str(raw.get("type", "none")).lower()
        value = str(raw.get("value", "")) if raw.get("value") is not None else ""

        if action_type not in {"none", "link", "exe", "macro"}:
            action_type = "none"
            value = ""

        if action_type == "none":
            value = ""

        label = str(raw.get("label", f"Button {i}")).strip()
        if not label:
            label = f"Button {i}"
        normalized[key] = {"type": action_type, "value": value, "label": label[:24]}

    return normalized


def load_config():
    print(f"[DEBUG] Loading config from: {CONFIG_FILE}")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            config = normalize_config(config)
            print("[DEBUG] Config loaded:", json.dumps(config, indent=2))
            return config
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid config.json format: {e}")
            broken_backup = CONFIG_FILE + ".broken"
            try:
                os.replace(CONFIG_FILE, broken_backup)
                print(f"[DEBUG] Corrupted config moved to: {broken_backup}")
            except OSError as move_error:
                print(f"[ERROR] Failed to backup corrupted config: {move_error}")
        except OSError as e:
            print(f"[ERROR] Cannot read config file: {e}")

    print("[DEBUG] Creating default config.")
    config = default_config()
    save_config(config)
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def write_log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def validate_button_config(action):
    action_type = action.get("type", "none")
    value = (action.get("value") or "").strip()
    if action_type == "link" and value:
        return value.startswith("http://") or value.startswith("https://"), "URL must start with http:// or https://"
    if action_type == "exe" and value:
        return os.path.isfile(value), "Executable path does not exist"
    return True, ""


def parse_macro_keys(macro_value):
    parts = [part.strip().upper() for part in str(macro_value).split("+") if part.strip()]
    vk_codes = []
    for part in parts:
        vk_code = MACRO_KEY_MAP.get(part)
        if vk_code is None:
            raise ValueError(f"Unsupported key in macro: {part}")
        vk_codes.append(vk_code)
    return vk_codes

def esegui_macro(macro_value):
    if not macro_value:
        return
    try:
        vk_codes = parse_macro_keys(macro_value)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    if IS_WINDOWS:
        KEYEVENTF_KEYUP = 0x0002
        for vk_code in vk_codes:
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        for vk_code in reversed(vk_codes):
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        return

    keys = []
    for part in [part.strip().upper() for part in str(macro_value).split("+") if part.strip()]:
        key = LINUX_KEY_MAP.get(part)
        if not key:
            print(f"[ERROR] Unsupported Linux macro key: {part}")
            return
        keys.append(key)
    try:
        subprocess.run(["xdotool", "key", "+".join(keys)], check=True, capture_output=True)
    except FileNotFoundError:
        print("[ERROR] xdotool is required on Linux for macro execution")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Linux macro execution failed: {e}")

def esegui_azione(azione):
    global last_exe_launch_time
    if azione["type"] == "link" and azione["value"]:
        write_log(f"Opening link: {azione['value']}")
        webbrowser.open(azione["value"])
    elif azione["type"] == "exe" and azione["value"]:
        now = time.time()
        if now - last_exe_launch_time < 2:
            print("[DEBUG] EXE launch blocked: wait 2 seconds between launches")
            return
        try:
            if IS_WINDOWS:
                subprocess.Popen(azione["value"])
            else:
                subprocess.Popen([azione["value"]])
            last_exe_launch_time = now
            write_log(f"Launched executable: {azione['value']}")
        except Exception as e:
            write_log(f"Executable launch error: {e}", level="ERROR")
    elif azione["type"] == "macro" and azione["value"]:
        write_log(f"Executing macro: {azione['value']}")
        esegui_macro(azione["value"])
    else:
        print("Nessuna azione definita")

def ascolta_seriale(config):
    try:
        with serial.Serial(PORTA_ARDUINO, BAUDRATE, timeout=1) as ser:
            print(f"Connesso a {PORTA_ARDUINO}")
            while True:
                linea = ser.readline().decode('utf-8').strip()
                if linea:
                    print("Ricevuto:", linea)
                    if linea.startswith("VOLUME_"):
                        valore = linea.replace("VOLUME_", "")
                        gestisci_volume(valore)
                    elif linea == "MUTE":
                        gestisci_mute()
                    elif linea == "MEDIA":
                        gestisci_media()
                    elif linea in config:
                        esegui_azione(config[linea])
    except Exception as e:
        print(f"[ERRORE] Porta seriale: {e}")
        time.sleep(5)
        ascolta_seriale(config)

def simulate_keypress(vk_code):
    if not IS_WINDOWS:
        return
    ctypes.windll.user32.keybd_event(vk_code, 0, 0x0001, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, 0x0001 | 0x0002, 0)

def gestisci_volume(value):
    global last_volume_value, volume_step_accumulator
    try:
        valore = int(value)
        delta = valore - last_volume_value
        if delta != 0:
            # Many rotary encoders emit 2 state changes per tactile detent.
            # Accumulate transitions and apply one OS volume step every 2 changes.
            volume_step_accumulator += delta

            while volume_step_accumulator >= 2:
                simulate_keypress(0xAF)  # VK_VOLUME_UP
                volume_step_accumulator -= 2

            while volume_step_accumulator <= -2:
                simulate_keypress(0xAE)  # VK_VOLUME_DOWN
                volume_step_accumulator += 2

            print(f"[DEBUG] Raw encoder delta: {delta}, accumulator: {volume_step_accumulator}")

        last_volume_value = valore
    except ValueError:
        print("[ERROR] Invalid volume value:", value)

def gestisci_mute():
    global is_muted
    simulate_keypress(0xAD)  # VK_VOLUME_MUTE
    is_muted = not is_muted
    print(f"[DEBUG] Mute toggled -> {'ON' if is_muted else 'OFF'}")

def gestisci_media():
    simulate_keypress(0xB3)  # VK_MEDIA_PLAY_PAUSE
    print("[DEBUG] Media play/pause triggered")

def seleziona_pulsante(btn):
    global pulsante_selezionato
    pulsante_selezionato = btn
    print(f"[DEBUG] Pulsante selezionato: BUTTON_{btn}")

def deseleziona_pulsante():
    global pulsante_selezionato
    pulsante_selezionato = None    

def get_pulsante_selezionato():
    return pulsante_selezionato
