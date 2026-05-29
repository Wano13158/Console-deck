import pygame
import os
import io
import tkinter as tk
from tkinter import simpledialog, filedialog
import webbrowser
import tempfile
import subprocess
from urllib.parse import urlparse
from urllib.request import urlopen
from logic import esegui_azione, PORTA_ARDUINO

# Глобальні константи
FONT = None
SMALL_FONT = None
SCREEN = None

BTN_SIZE = 100
SPACING_X = 140
SPACING_Y = 120
MARGIN_Y = 20
BASE_SCREEN_WIDTH = 1024
BASE_SCREEN_HEIGHT = 860
SCREEN_WIDTH = BASE_SCREEN_WIDTH
SCREEN_HEIGHT = BASE_SCREEN_HEIGHT
MIN_SCREEN_WIDTH = 640
MIN_SCREEN_HEIGHT = 520
UI_SCALE = 1.0

BUTTON_RADIUS = 14
PANEL_RADIUS = 8

cancel_button_rect = None
browse_button_rect = None
save_button_rect = None
tipo_button_rects = {}

temp_config_type = None
temp_config_value = None

save_enabled = False
save_clicked = False

input_active = False
input_rect = None
label_input_rect = None
active_field = None
icon_cache = {}
button_rects = {}


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _scaled(value):
    return max(1, int(round(value * UI_SCALE)))


def _font(size, bold=False):
    return pygame.font.SysFont("Segoe UI", _scaled(size), bold=bold)


def update_responsive_metrics(width=None, height=None):
    global SCREEN_WIDTH, SCREEN_HEIGHT, UI_SCALE, FONT, SMALL_FONT

    if width is None or height is None:
        if SCREEN:
            width, height = SCREEN.get_size()
        else:
            width, height = SCREEN_WIDTH, SCREEN_HEIGHT

    SCREEN_WIDTH = max(MIN_SCREEN_WIDTH, int(width))
    SCREEN_HEIGHT = max(MIN_SCREEN_HEIGHT, int(height))
    UI_SCALE = _clamp(
        min(SCREEN_WIDTH / BASE_SCREEN_WIDTH, SCREEN_HEIGHT / BASE_SCREEN_HEIGHT),
        0.62,
        1.35,
    )

    if pygame.font.get_init():
        FONT = _font(30, bold=True)
        SMALL_FONT = _font(18)


def _button_grid_rects():
    button_width = _scaled(110)
    button_height = _scaled(100)
    gap_x = _scaled(30)
    gap_y = _scaled(20)
    total_width = (button_width * 3) + (gap_x * 2)
    header_space = _scaled(112)
    start_x = max(_scaled(16), (SCREEN_WIDTH - total_width) // 2)
    start_y = max(_scaled(88), header_space + _scaled(38))

    rects = {}
    for i in range(9):
        x = start_x + (i % 3) * (button_width + gap_x)
        y = start_y + (i // 3) * (button_height + gap_y)
        rects[f"BUTTON_{i + 1}"] = pygame.Rect(x, y, button_width, button_height)
    return rects


def _fit_text(text, font, max_width):
    text = str(text)
    if font.size(text)[0] <= max_width:
        return text

    ellipsis = "..."
    while text and font.size(text + ellipsis)[0] > max_width:
        text = text[:-1]
    return text + ellipsis if text else ellipsis



def _extract_exe_icon_surface(exe_path):
    if os.name != "nt" or not os.path.isfile(exe_path):
        return None

    ps_script = (
        "Add-Type -AssemblyName System.Drawing; "
        "$icon = [System.Drawing.Icon]::ExtractAssociatedIcon($args[0]); "
        "if ($icon -eq $null) { exit 1 }; "
        "$bmp = $icon.ToBitmap(); "
        "$bmp.Save($args[1], [System.Drawing.Imaging.ImageFormat]::Png)"
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        png_path = tmp.name

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                ps_script,
                exe_path,
                png_path,
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if completed.returncode != 0 or not os.path.isfile(png_path):
            return None

        loaded = pygame.image.load(png_path)
        return pygame.transform.smoothscale(loaded, (24, 24))
    except Exception:
        return None
    finally:
        try:
            os.remove(png_path)
        except OSError:
            pass


def _build_exe_fallback_icon():
    icon = pygame.Surface((24, 24), pygame.SRCALPHA)
    pygame.draw.rect(icon, (82, 138, 255), (0, 0, 24, 24), border_radius=5)
    mini = pygame.font.SysFont("Segoe UI", 11, bold=True)
    icon.blit(mini.render("EXE", True, (245, 247, 255)), (2, 6))
    return icon


def _load_icon_for_button(cfg):
    action_type = cfg.get("type", "none")
    value = (cfg.get("value") or "").strip()
    cache_key = f"{action_type}:{value}"
    if cache_key in icon_cache:
        return icon_cache[cache_key]

    icon_surface = None
    if action_type == "link" and value:
        try:
            host = urlparse(value).netloc
            if host:
                fav_url = f"https://www.google.com/s2/favicons?domain={host}&sz=64"
                with urlopen(fav_url, timeout=1.5) as response:
                    raw = response.read()
                loaded = pygame.image.load(io.BytesIO(raw))
                icon_surface = pygame.transform.smoothscale(loaded, (24, 24))
        except Exception:
            icon_surface = None
    elif action_type == "exe" and value:
        icon_surface = _extract_exe_icon_surface(value)
        if icon_surface is None:
            ico_candidate = os.path.splitext(value)[0] + ".ico"
            if os.path.isfile(ico_candidate):
                try:
                    loaded = pygame.image.load(ico_candidate)
                    icon_surface = pygame.transform.smoothscale(loaded, (24, 24))
                except Exception:
                    icon_surface = None
        if icon_surface is None:
            icon_surface = _build_exe_fallback_icon()

    icon_cache[cache_key] = icon_surface
    return icon_surface


def init_pygame():
    global SCREEN
    pygame.init()
    update_responsive_metrics(SCREEN_WIDTH, SCREEN_HEIGHT)
    SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("ConsoleDeck V2")


def disegna_pulsanti(config, selezionato=None):
    global button_rects

    update_responsive_metrics()
    SCREEN.fill((25, 27, 49))

    padding_x = _scaled(24)
    header = FONT.render("ConsoleDeck v2", True, (236, 156, 46))
    SCREEN.blit(header, (padding_x, _scaled(20)))

    status_color = (72, 196, 116) if PORTA_ARDUINO else (220, 96, 96)
    status_text = f"Connected -> {PORTA_ARDUINO}" if PORTA_ARDUINO else "ConsoleDeck not connected"
    status_surface = SMALL_FONT.render(status_text, True, status_color)
    status_x = max(padding_x, SCREEN_WIDTH - status_surface.get_width() - padding_x)
    status_y = _scaled(34) if SCREEN_WIDTH >= _scaled(760) else _scaled(62)
    SCREEN.blit(status_surface, (status_x, status_y))

    button_rects = _button_grid_rects()
    number_font = FONT
    label_font = _font(14)
    for i in range(9):
        key = f"BUTTON_{i+1}"
        base = button_rects[key]
        pygame.draw.rect(SCREEN, (58, 62, 95), base, border_radius=_scaled(BUTTON_RADIUS))

        if selezionato == key:
            pygame.draw.rect(
                SCREEN,
                (109, 153, 255),
                base,
                width=max(2, _scaled(3)),
                border_radius=_scaled(BUTTON_RADIUS),
            )

        num_text = number_font.render(str(i + 1), True, (235, 235, 242))
        SCREEN.blit(num_text, num_text.get_rect(center=(base.centerx, base.y + int(base.height * 0.42))))

        cfg = config.get(key, {"type": "none"})
        label_text = _fit_text(cfg.get("label", f"Button {i+1}"), label_font, base.width - _scaled(16))
        subtitle = cfg.get("type", "none").upper()
        if subtitle == "MACRO":
            subtitle = "macro"
        sub = SMALL_FONT.render(subtitle, True, (148, 152, 185))
        SCREEN.blit(sub, sub.get_rect(center=(base.centerx, base.y + int(base.height * 0.76))))
        icon = _load_icon_for_button(cfg)
        if icon:
            icon_size = _scaled(24)
            scaled_icon = (
                pygame.transform.smoothscale(icon, (icon_size, icon_size))
                if icon.get_size() != (icon_size, icon_size)
                else icon
            )
            SCREEN.blit(scaled_icon, (base.right - icon_size - _scaled(6), base.y + _scaled(6)))
        SCREEN.blit(
            label_font.render(label_text, True, (210, 214, 240)),
            (base.x + _scaled(8), base.y + _scaled(6)),
        )

    hint = "Select a button" if not selezionato else f"Select a button: {selezionato}"
    last_button_bottom = max(rect.bottom for rect in button_rects.values())
    hint_y = min(last_button_bottom + _scaled(28), SCREEN_HEIGHT - _scaled(60))
    if selezionato:
        hint_y = min(hint_y, _config_panel_top() - _scaled(30))
    SCREEN.blit(SMALL_FONT.render(hint, True, (220, 220, 235)), (padding_x, hint_y))

    if selezionato:
        disegna_configuratore_avanzato(selezionato, config)

    pygame.display.flip()


def _config_panel_top():
    panel_height = _scaled(272)
    min_top = (
        max(rect.bottom for rect in button_rects.values()) + _scaled(36)
        if button_rects
        else _scaled(520)
    )
    return max(min_top, SCREEN_HEIGHT - panel_height)


def disegna_configuratore_avanzato(selezionato, config):
    global tipo_button_rects, cancel_button_rect, input_rect, browse_button_rect
    global label_input_rect, save_button_rect

    small_font = _font(16)
    data = config.get(selezionato, {"type": "none", "value": ""})

    global temp_config_type, temp_config_value

    tipo = temp_config_type if temp_config_type is not None else data.get("type", "none")
    valore = temp_config_value if temp_config_value is not None else data.get("value", "")
    label_value = data.get("label", selezionato.replace("BUTTON_", "Button "))

    panel_x = _scaled(18)
    panel_right = SCREEN_WIDTH - _scaled(18)
    max_width = panel_right - panel_x
    base_y = _config_panel_top()
    tipo_button_rects = {}
    input_rect = None
    browse_button_rect = None

    opzioni = ["LINK", "EXE", "MACRO", "NONE"]
    btn_width = _scaled(120)
    btn_height = _scaled(38)
    space = _scaled(12)
    type_label = small_font.render("Action type:", True, (160, 164, 200))
    SCREEN.blit(type_label, (panel_x, base_y + _scaled(8)))

    row_x = panel_x + type_label.get_width() + _scaled(14)
    y = base_y
    for nome in opzioni:
        if row_x + btn_width > panel_right:
            row_x = panel_x
            y += btn_height + _scaled(8)
        attivo = (nome.lower() == tipo)
        colore = (72, 96, 168) if attivo else (55, 57, 82)
        rect = pygame.Rect(row_x, y, btn_width, btn_height)
        tipo_button_rects[nome] = rect
        pygame.draw.rect(SCREEN, colore, rect, border_radius=_scaled(PANEL_RADIUS))
        testo = small_font.render(nome, True, (220, 225, 245))
        SCREEN.blit(testo, testo.get_rect(center=rect.center))
        row_x += btn_width + space

    base_y = y + btn_height + _scaled(12)
    section_bottom = base_y

    if tipo in ("link", "macro"):
        label_text = "Enter URL:" if tipo == "link" else "Enter shortcut (example: F12+5):"
        label = small_font.render(label_text, True, (220, 220, 220))
        SCREEN.blit(label, (panel_x, base_y))

        base_y += label.get_height() + _scaled(6)
        input_rect = pygame.Rect(panel_x, base_y, min(_scaled(610), max_width), _scaled(32))
        pygame.draw.rect(SCREEN, (245, 245, 250), input_rect, border_radius=_scaled(4))

        render_value = _fit_text(valore if valore else "", small_font, input_rect.width - _scaled(16))
        render_text = small_font.render(render_value, True, (16, 16, 16))
        SCREEN.blit(render_text, (input_rect.x + _scaled(8), input_rect.y + _scaled(8)))
        section_bottom = input_rect.bottom

    elif tipo == "exe":
        label = small_font.render("Select executable file:", True, (220, 220, 220))
        SCREEN.blit(label, (panel_x, base_y))

        base_y += label.get_height() + _scaled(6)
        browse_rect = pygame.Rect(panel_x, base_y, _scaled(120), _scaled(32))
        pygame.draw.rect(SCREEN, (234, 176, 74), browse_rect, border_radius=_scaled(6))
        btn_text = small_font.render("BROWSE", True, (16, 16, 20))
        SCREEN.blit(btn_text, btn_text.get_rect(center=browse_rect.center))
        browse_button_rect = browse_rect
        section_bottom = browse_rect.bottom

    base_y = section_bottom + _scaled(12)
    label_caption = small_font.render("Button label:", True, (220, 220, 220))
    SCREEN.blit(label_caption, (panel_x, base_y))
    label_x = panel_x + label_caption.get_width() + _scaled(12)
    label_width = min(_scaled(260), max(_scaled(180), panel_right - label_x))
    if label_x + label_width > panel_right:
        base_y += label_caption.get_height() + _scaled(8)
        label_x = panel_x
        label_width = min(max_width, _scaled(320))
    label_input_rect = pygame.Rect(label_x, base_y - _scaled(4), label_width, _scaled(32))
    pygame.draw.rect(SCREEN, (245, 245, 250), label_input_rect, border_radius=_scaled(4))
    label_txt = small_font.render(
        _fit_text(label_value[:24], small_font, label_input_rect.width - _scaled(16)),
        True,
        (16, 16, 16),
    )
    SCREEN.blit(label_txt, (label_input_rect.x + _scaled(8), label_input_rect.y + _scaled(8)))

    button_y = min(label_input_rect.bottom + _scaled(10), SCREEN_HEIGHT - _scaled(42))
    save_rect = pygame.Rect(panel_x + _scaled(54), button_y, _scaled(90), _scaled(34))
    cancel_button_rect = pygame.Rect(save_rect.right + _scaled(10), button_y, _scaled(95), _scaled(34))

    colore_save = (234, 176, 74) if (save_clicked or save_enabled) else (90, 90, 100)
    pygame.draw.rect(SCREEN, colore_save, save_rect, border_radius=_scaled(PANEL_RADIUS))
    save_text = small_font.render("Save", True, (16, 16, 20) if save_enabled else (235, 235, 235))
    SCREEN.blit(save_text, save_text.get_rect(center=save_rect.center))
    save_button_rect = save_rect

    pygame.draw.rect(SCREEN, (55, 57, 82), cancel_button_rect, border_radius=_scaled(PANEL_RADIUS))
    cancel_text = small_font.render("Cancel", True, (190, 195, 230))
    SCREEN.blit(cancel_text, cancel_text.get_rect(center=cancel_button_rect.center))


def is_dirty(selezionato, config):
    global temp_config_type, temp_config_value
    if not selezionato:
        return False

    current = config.get(selezionato, {"type": "none", "value": ""})
    tipo = temp_config_type if temp_config_type is not None else current["type"]
    valore = temp_config_value if temp_config_value is not None else current["value"]

    return tipo != current["type"] or valore != current["value"]


def trova_pulsante_click(mx, my):
    active_rects = button_rects or _button_grid_rects()

    for key, rect in active_rects.items():
        if rect.collidepoint(mx, my):
            return key
    return None


def config_pulsante(button_key, config):
    root = tk.Tk()
    root.title(f"Configura {button_key}")

    scelta_var = tk.StringVar(root)
    scelta_var.set(config[button_key]["type"])

    valore_var = tk.StringVar(root)
    valore_var.set(config[button_key].get("value", ""))

    def aggiorna_valore_widget(tipo):
        for widget in root.pack_slaves():
            if getattr(widget, "is_value_widget", False):
                widget.destroy()

        if tipo == "link":
            tk.Label(root, text="Inserisci URL:").pack()
            entry = tk.Entry(root, width=50, textvariable=valore_var)
            entry.pack()
            entry.is_value_widget = True

            tk.Button(root, text="Testa Azione", command=lambda: webbrowser.open(valore_var.get())).pack()
            tk.Button(root, text="Salva", command=salva).pack()

        elif tipo == "exe":
            def apri_file():
                path = filedialog.askopenfilename(title="Seleziona file eseguibile")
                if path:
                    valore_var.set(path)

            tk.Button(root, text="Scegli file .exe", command=apri_file).pack()
            lbl_file = tk.Label(root, textvariable=valore_var)
            lbl_file.pack()
            lbl_file.is_value_widget = True

            tk.Button(root, text="Testa Azione", command=lambda: esegui_azione({"type": "exe", "value": valore_var.get()})).pack()
            tk.Button(root, text="Salva", command=salva).pack()

    def salva():
        tipo = scelta_var.get()
        val = valore_var.get()
        config[button_key] = {"type": tipo, "value": val} if tipo != "none" else {"type": "none", "value": ""}
        root.destroy()

    tk.Label(root, text="Seleziona tipo azione:").pack()
    tk.OptionMenu(root, scelta_var, "link", "exe", "none", command=aggiorna_valore_widget).pack()
    aggiorna_valore_widget(scelta_var.get())

    root.mainloop()
