# 🚀 Tutorial: Autostart `no_ui.bat` on Windows

Below are two simple ways to set up autostart for:
`C:\cd_v2_script\no_ui.bat`

---

## Method 1 (recommended): Startup folder

1. Press `Win + R`.
2. Enter:
   ```
   shell:startup
   ```
3. The current user's Startup folder will open.
4. In that folder, right-click → **New → Shortcut**.
5. In the location field, paste:
   ```
   C:\cd_v2_script\no_ui.bat
   ```
6. Click **Next** → set a name (for example, `ConsoleDeck No UI`) → **Finish**.
7. Restart your PC and verify the script starts automatically.

> If it does not work, verify the file really exists at `C:\cd_v2_script\no_ui.bat`.

---

## How to verify autostart

- Sign out and sign in again, or reboot your PC.
- Check whether the expected process/script starts.
- If needed, add logging to `no_ui.bat`:
  ```bat
  echo started %date% %time% >> C:\cd_v2_script\startup_log.txt
  ```
  This helps confirm whether the `.bat` file ran after login.

---

## Common issues

- **Path uses `/` instead of `\\`**  
  On Windows, use:
  `C:\cd_v2_script\no_ui.bat`
- **Script does not start on boot**  
  Run `no_ui.bat` manually (double-click) and make sure it works without errors.
- **Console window is distracting**  
  Use the section below: **"Mini guide: hidden launch via VBS"**.

---

## Mini guide: hidden launch via VBScript

- Double-click `run_hidden.vbs`: the console window should not appear.
- If the script does not start, temporarily change parameter `0` to `1`:
  ```vbscript
  WShell.Run Chr(34) & "C:\cd_v2_script\no_ui.bat" & Chr(34), 1
  ```
  This shows the window, making it easier to spot errors.
- After confirming it works, repeat the startup-folder steps above using this `.vbs` file.
