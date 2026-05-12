import pygame
import os
import io
import tkinter as tk
from tkinter import simpledialog, filedialog
import webbrowser
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
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 860
MIN_SCREEN_WIDTH = 960
MIN_SCREEN_HEIGHT = 760

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
    global FONT, SMALL_FONT, SCREEN
    pygame.init()
    FONT = pygame.font.SysFont("Segoe UI", 30, bold=True)
    SMALL_FONT = pygame.font.SysFont("Segoe UI", 18)
    SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("ConsoleDeck V2")


def disegna_pulsanti(config, selezionato=None):
    SCREEN.fill((25, 27, 49))

    header = FONT.render("ConsoleDeck v2", True, (236, 156, 46))
    SCREEN.blit(header, (24, 20))

    status_color = (72, 196, 116) if PORTA_ARDUINO else (220, 96, 96)
    status_text = f"Connected -> {PORTA_ARDUINO}" if PORTA_ARDUINO else "ConsoleDeck not connected"
    SCREEN.blit(SMALL_FONT.render(status_text, True, status_color), (640, 34))


    start_x = 180
    start_y = 150
    for i in range(9):
        key = f"BUTTON_{i+1}"
        x = start_x + (i % 3) * 140
        y = start_y + (i // 3) * 120

        base = pygame.Rect(x, y, 110, 100)
        pygame.draw.rect(SCREEN, (58, 62, 95), base, border_radius=BUTTON_RADIUS)

        if selezionato == key:
            pygame.draw.rect(SCREEN, (109, 153, 255), base, width=3, border_radius=BUTTON_RADIUS)

        num_text = FONT.render(str(i + 1), True, (235, 235, 242))
        SCREEN.blit(num_text, num_text.get_rect(center=(x + 55, y + 42)))

        cfg = config.get(key, {"type": "none"})
        label_text = cfg.get("label", f"Button {i+1}")[:12]
        subtitle = cfg.get("type", "none").upper()
        if subtitle == "MACRO":
            subtitle = "macro"
        sub = SMALL_FONT.render(subtitle, True, (148, 152, 185))
        SCREEN.blit(sub, sub.get_rect(center=(x + 55, y + 76)))
        icon = _load_icon_for_button(cfg)
        if icon:
            SCREEN.blit(icon, (x + 80, y + 6))
        label = pygame.font.SysFont("Segoe UI", 14)
        SCREEN.blit(label.render(label_text, True, (210, 214, 240)), (x + 8, y + 6))

    hint = "Select a button" if not selezionato else f"Select a button: {selezionato}"
    SCREEN.blit(SMALL_FONT.render(hint, True, (220, 220, 235)), (22, 548))

    if selezionato:
        disegna_configuratore_avanzato(selezionato, config)

    pygame.display.flip()


def disegna_configuratore_avanzato(selezionato, config):
    global tipo_button_rects, cancel_button_rect, input_rect, browse_button_rect, label_input_rect
    small_font = pygame.font.SysFont("Segoe UI", 16)

    data = config.get(selezionato, {"type": "none", "value": ""})

    global temp_config_type, temp_config_value

    tipo = temp_config_type if temp_config_type is not None else data.get("type", "none")
    valore = temp_config_value if temp_config_value is not None else data.get("value", "")
    label_value = data.get("label", selezionato.replace("BUTTON_", "Button "))

    opzioni = ["LINK", "EXE", "MACRO", "NONE"]
    btn_width = 120
    btn_height = 38
    spazio = 14
    start_x = 22
    base_y = 588
    tipo_button_rects = {}
    input_rect = None
    browse_button_rect = None

    SCREEN.blit(small_font.render("Action type:", True, (160, 164, 200)), (22, base_y + 8))
    start_x += 100

    for i, nome in enumerate(opzioni):
        x = start_x + i * (btn_width + spazio)
        y = base_y
        attivo = (nome.lower() == tipo)
        colore = (72, 96, 168) if attivo else (55, 57, 82)

        rect = pygame.Rect(x, y, btn_width, btn_height)
        tipo_button_rects[nome] = rect

        pygame.draw.rect(SCREEN, colore, rect, border_radius=PANEL_RADIUS)
        testo = small_font.render(nome, True, (220, 225, 245))
        SCREEN.blit(testo, testo.get_rect(center=rect.center))

    base_y += btn_height + 12

    section_bottom = base_y

    if tipo in ("link", "macro"):
        label_text = "Enter URL:" if tipo == "link" else "Enter shortcut (example: F12+5):"
        label = small_font.render(label_text, True, (220, 220, 220))
        SCREEN.blit(label, (22, base_y))

        base_y += label.get_height() + 6

        input_rect = pygame.Rect(22, base_y, 610, 32)
        pygame.draw.rect(SCREEN, (245, 245, 250), input_rect, border_radius=4)

        render_text = small_font.render(valore if valore else "", True, (16, 16, 16))
        SCREEN.blit(render_text, (input_rect.x + 8, input_rect.y + 8))
        section_bottom = input_rect.bottom

    elif tipo == "exe":
        label = small_font.render("Select executable file:", True, (220, 220, 220))
        SCREEN.blit(label, (22, base_y))

        base_y += label.get_height() + 6
        browse_rect = pygame.Rect(22, base_y, 120, 32)
        pygame.draw.rect(SCREEN, (234, 176, 74), browse_rect, border_radius=6)
        btn_text = small_font.render("BROWSE", True, (16, 16, 20))
        SCREEN.blit(btn_text, btn_text.get_rect(center=browse_rect.center))
        browse_button_rect = browse_rect
        section_bottom = browse_rect.bottom

    base_y = section_bottom + 12
    label_input_rect = pygame.Rect(130, base_y - 4, 260, 32)

    footer_top = SCREEN_HEIGHT - 48
    if label_input_rect.bottom + 12 > footer_top:
        shift_up = (label_input_rect.bottom + 12) - footer_top
        base_y -= shift_up
        label_input_rect = pygame.Rect(130, base_y - 4, 260, 32)
    SCREEN.blit(small_font.render("Button label:", True, (220, 220, 220)), (22, base_y))
    pygame.draw.rect(SCREEN, (245, 245, 250), label_input_rect, border_radius=4)
    label_txt = small_font.render(label_value[:24], True, (16, 16, 16))
    SCREEN.blit(label_txt, (label_input_rect.x + 8, label_input_rect.y + 8))

    button_y = max(label_input_rect.bottom + 10, SCREEN_HEIGHT - 48)

    cancel_button_rect = pygame.Rect(176, button_y, 95, 34)
    pygame.draw.rect(SCREEN, (55, 57, 82), cancel_button_rect, border_radius=PANEL_RADIUS)
    cancel_text = small_font.render("Cancel", True, (190, 195, 230))
    SCREEN.blit(cancel_text, cancel_text.get_rect(center=cancel_button_rect.center))

    save_rect = pygame.Rect(76, button_y, 90, 34)
    colore_save = (234, 176, 74) if (save_clicked or save_enabled) else (90, 90, 100)
    pygame.draw.rect(SCREEN, colore_save, save_rect, border_radius=PANEL_RADIUS)

    save_text = small_font.render("Save", True, (16, 16, 20) if save_enabled else (235, 235, 235))
    SCREEN.blit(save_text, save_text.get_rect(center=save_rect.center))

    global save_button_rect
    save_button_rect = save_rect


def is_dirty(selezionato, config):
    global temp_config_type, temp_config_value
    if not selezionato:
        return False

    current = config.get(selezionato, {"type": "none", "value": ""})
    tipo = temp_config_type if temp_config_type is not None else current["type"]
    valore = temp_config_value if temp_config_value is not None else current["value"]

    return tipo != current["type"] or valore != current["value"]


def trova_pulsante_click(mx, my):
    start_x = 180
    start_y = 150

    for i in range(9):
        x = start_x + (i % 3) * 140
        y = start_y + (i // 3) * 120
        if x <= mx <= x + 110 and y <= my <= y + 100:
            return f"BUTTON_{i+1}"
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
