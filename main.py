import argparse
import threading
from logic import load_config, save_config, ascolta_seriale, seleziona_pulsante, get_pulsante_selezionato, deseleziona_pulsante, validate_button_config, write_log
from gui import init_pygame, disegna_pulsanti, trova_pulsante_click
import pygame
import pyperclip

import gui


def save_selected_config(config, selezionato):
    if not selezionato:
        return False

    current = config.get(selezionato, {"type": "none", "value": ""})
    new_type = gui.temp_config_type if gui.temp_config_type is not None else current.get("type", "none")
    new_value = gui.temp_config_value if gui.temp_config_value is not None else current.get("value", "")

    if new_type == "none":
        new_value = ""

    current_label = current.get("label", selezionato.replace("BUTTON_", "Button "))
    config[selezionato] = {"type": new_type, "value": new_value, "label": current_label}
    is_valid, reason = validate_button_config(config[selezionato])
    if not is_valid:
        write_log(f"Save blocked for {selezionato}: {reason}", level="ERROR")
        return False
    gui.temp_config_type = None
    gui.temp_config_value = None
    gui.save_enabled = False
    gui.save_clicked = True
    save_config(config)
    gui.save_clicked = False
    return True


def apply_type_shortcut(config, selezionato, tipo):
    if not selezionato:
        return
    gui.temp_config_type = tipo
    if tipo == "none":
        gui.temp_config_value = ""
    elif gui.temp_config_value is None:
        gui.temp_config_value = config[selezionato].get("value", "")
    gui.save_enabled = gui.is_dirty(selezionato, config)


def main(gui_mode):
    config = load_config()

    if gui_mode:
        serial_thread = threading.Thread(target=ascolta_seriale, args=(config,), daemon=True)
        serial_thread.start()

        init_pygame()
        pygame.key.set_repeat(300, 30)

        running = True
        while running:
            selezionato = get_pulsante_selezionato()
            disegna_pulsanti(config, selezionato)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    new_width = max(event.w, gui.MIN_SCREEN_WIDTH)
                    new_height = max(event.h, gui.MIN_SCREEN_HEIGHT)
                    gui.SCREEN_WIDTH = new_width
                    gui.SCREEN_HEIGHT = new_height
                    gui.SCREEN = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    selezionato = get_pulsante_selezionato()
                    click_consumed = False

                    # Клік всередині поля введення URL
                    if selezionato and gui.input_rect and gui.input_rect.collidepoint(mx, my):
                        gui.input_active = True
                        gui.active_field = "value"
                        click_consumed = True
                    elif selezionato and gui.label_input_rect and gui.label_input_rect.collidepoint(mx, my):
                        gui.input_active = True
                        gui.active_field = "label"
                        click_consumed = True
                    else:
                        gui.input_active = False
                        gui.active_field = None

                    # Клік по "Cancel"
                    if selezionato and gui.cancel_button_rect and gui.cancel_button_rect.collidepoint(mx, my):
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        deseleziona_pulsante()
                        click_consumed = True
                    
                    # Клік по "Save"
                    if (
                        not click_consumed
                        and selezionato
                        and hasattr(gui, "save_button_rect")
                        and gui.save_button_rect
                        and gui.save_button_rect.collidepoint(mx, my)
                    ):
                        save_selected_config(config, selezionato)

                    # Клік по одній із 4 взаємовиключних кнопок (LINK, EXE, MACRO, NONE)
                    if not click_consumed and selezionato and hasattr(gui, "tipo_button_rects"):
                        for nome, rect in gui.tipo_button_rects.items():
                            if rect.collidepoint(mx, my):
                                tipo = nome.lower()
                                apply_type_shortcut(config, selezionato, tipo)
                                click_consumed = True
                                break
                            
                    # Клік по "Browse"
                    current_type = gui.temp_config_type or (config.get(selezionato, {}).get("type") if selezionato else None)
                    if (
                        not click_consumed
                        and selezionato
                        and current_type == "exe"
                        and hasattr(gui, "browse_button_rect")
                        and gui.browse_button_rect
                        and gui.browse_button_rect.collidepoint(mx, my)
                    ):
                            from tkinter import filedialog
                            import tkinter as tk
                            import os

                            root = tk.Tk()
                            root.withdraw()  # Приховує головне вікно
                            file_types = [("All files", "*")]
                            if os.name == "nt":
                                file_types.insert(0, ("Executable files", "*.exe"))
                            path = filedialog.askopenfilename(
                                title="Select executable",
                                filetypes=file_types,
                                initialdir=os.path.expanduser("~")
                            )
                            if path:
                                gui.temp_config_value = path
                                gui.save_enabled = gui.is_dirty(selezionato, config)
                            root.destroy()
                            click_consumed = True

                    if click_consumed:
                        continue

                    # Клік по одній із кнопок 1-9
                    btn = trova_pulsante_click(mx, my)
                    if btn:
                        seleziona_pulsante(btn)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                
                elif event.type == pygame.KEYDOWN and not gui.input_active:
                    selezionato = get_pulsante_selezionato()

                    if event.key in (pygame.K_1, pygame.K_KP1):
                        seleziona_pulsante("BUTTON_1")
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        seleziona_pulsante("BUTTON_2")
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        seleziona_pulsante("BUTTON_3")
                    elif event.key in (pygame.K_4, pygame.K_KP4):
                        seleziona_pulsante("BUTTON_4")
                    elif event.key in (pygame.K_5, pygame.K_KP5):
                        seleziona_pulsante("BUTTON_5")
                    elif event.key in (pygame.K_6, pygame.K_KP6):
                        seleziona_pulsante("BUTTON_6")
                    elif event.key in (pygame.K_7, pygame.K_KP7):
                        seleziona_pulsante("BUTTON_7")
                    elif event.key in (pygame.K_8, pygame.K_KP8):
                        seleziona_pulsante("BUTTON_8")
                    elif event.key in (pygame.K_9, pygame.K_KP9):
                        seleziona_pulsante("BUTTON_9")
                    elif event.key == pygame.K_ESCAPE:
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        deseleziona_pulsante()
                    elif event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        save_selected_config(config, selezionato)
                    elif event.key == pygame.K_l:
                        apply_type_shortcut(config, selezionato, "link")
                    elif event.key == pygame.K_e:
                        apply_type_shortcut(config, selezionato, "exe")
                    elif event.key == pygame.K_m:
                        apply_type_shortcut(config, selezionato, "macro")
                    elif event.key == pygame.K_n:
                        apply_type_shortcut(config, selezionato, "none")

                    if get_pulsante_selezionato() != selezionato:
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False

                # Обробка текстового поля для введення URL
                elif event.type == pygame.KEYDOWN and gui.input_active:
                    selezionato = get_pulsante_selezionato()
                    if not selezionato:
                        gui.input_active = False
                        continue

                    active_type = gui.temp_config_type if gui.temp_config_type is not None else config[selezionato].get("type", "none")
                    if gui.active_field == "value" and active_type not in ("link", "macro"):
                        gui.input_active = False
                        continue

                    if event.key == pygame.K_BACKSPACE:
                        if gui.active_field == "label":
                            config[selezionato]["label"] = config[selezionato].get("label", "")[:-1]
                        else:
                            gui.temp_config_value = (gui.temp_config_value or "")[:-1]
                    elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Ctrl+V: вставити з буфера обміну
                        clipboard_text = pyperclip.paste()
                        if clipboard_text:
                            gui.temp_config_value = (gui.temp_config_value or "") + clipboard_text
                    elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Ctrl+A → Seleziona tutto (simbolico, nessuna azione visiva)
                        pass  # niente da fare qui (è tutto già "selezionato")

                    elif event.key == pygame.K_c and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Ctrl+C → Copia tutto il campo
                        if gui.temp_config_value:
                            pyperclip.copy(gui.temp_config_value)

                    elif event.key == pygame.K_x and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Ctrl+X → Taglia tutto
                        if gui.temp_config_value:
                            pyperclip.copy(gui.temp_config_value)
                            gui.temp_config_value = ""
                            gui.save_enabled = gui.is_dirty(selezionato, config)        
                    else:
                        char = event.unicode
                        if char.isprintable():
                            if gui.active_field == "label":
                                config[selezionato]["label"] = (config[selezionato].get("label", "") + char)[:24]
                            else:
                                gui.temp_config_value = (gui.temp_config_value or "") + char

                    gui.save_enabled = gui.is_dirty(selezionato, config)

        pygame.quit()
    else:
        ascolta_seriale(config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui', action='store_true', help="Avvia la GUI di configurazione")
    args = parser.parse_args()
    main(args.gui)
