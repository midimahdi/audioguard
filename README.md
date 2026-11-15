# AudioGuard

> **Bulletproof, crash-resistant lossless audio backup system for Windows.**  
> Designed for mosque mixers, lectures, and live venues to survive sudden power cuts without file corruption.

---

## Key Features

- **Crash-Proof Lossless FLAC Engine:**  
  Records at 48,000 Hz, 24-bit stereo. Performs an explicit `sf_file.flush()` and `os.fsync()` every 1.0 second. If power cuts mid-sentence, the recording is 100% loss-free and playable right up to the exact moment power was lost.
- **Automatic MP3 Export with Power-Cut Recovery:**  
  Generates a lightweight, WhatsApp- and phone-friendly `.mp3` copy alongside the master `.flac` file upon session completion. If power was cut while recording, AudioGuard's stream-chunk recovery engine automatically detects the unclosed FLAC file upon Windows reboot, safely decodes all flushed frames, and exports the MP3 copy.
- **Smart Multi-Slot Daily Scheduler:**  
  Supports arbitrary daily time frames (e.g. `09:00–10:00`, `12:00–14:00`, `18:00–21:00`) with a master toggle protected by accidental-click confirmation prompts.
  - **Late-Boot Catch-Up:** If the PC boots mid-window, recording starts immediately.
  - **Speech Overtime Extension:** If voice activity is still detected when the scheduled end time is reached, recording automatically extends for up to an extra 1 hour (+60 min cap) and finalizes once 90 seconds of silence occurs.
  - **Intelligent Pause Reset:** Stopping a scheduled recording suppresses auto-restart only for that active window; suppression automatically resets as soon as that slot passes.
- **Fail-Safe Storage Guard:**  
  If the chosen backup path (e.g. external USB drive `G:\`) is detached or inaccessible, AudioGuard automatically redirects recording to `C:\AudioBackups\` so audio is never dropped.
- **Customizable File Naming:**  
  Configure custom naming patterns using dynamic tokens (`{date}`, `{time}`, `{year}`, `{month}`, `{day}`, `{hour}`, `{min}`, `{sec}`, `{mode}`) with real-time live preview and Windows character sanitization.
- **Volunteer-Proof Dark UI & System Tray:**  
  - Dedicated Dashboard (Status Card, Level Meter, Summary, Action Button) and separate scrollable Settings panel.
  - Closing the window minimizes to the Windows System Tray (`WM_DELETE_WINDOW` intercepted).
  - Dedicated 1-second elapsed recording clock (`[HH:MM:SS]`).
  - Zero-CPU idle when minimized in the tray (`winfo_viewable()`).
  - Single-instance lock via `Local\` Mutex and localhost IPC (`127.0.0.1:54983`) that brings existing tray window to the front without error popups.
  - 1-click **"Open Diagnostic Log File"** shortcut to open `%APPDATA%\AudioGuard\app.log` in Notepad.
- **Modern Windows Compatibility:**  
  Tested and hardened for Windows 10 (all versions) and Windows 11 (21H2 through 24H2) with Modern Standby (S0ix) prevention (`ES_AWAYMODE_REQUIRED`), WASAPI Shared audio, and native DWM dark title bars.

---

## Downloads (Windows 10 & 11)

Both **64-bit (x64)** and **32-bit (x86)** versions are available:

| Type | 64-bit (x64) | 32-bit (x86) | Description |
| :--- | :--- | :--- | :--- |
| **1-Click Setup Installer** | `AudioGuard-Setup-x64.exe` | `AudioGuard-Setup-x86.exe` | Standard Windows installer. Installs to user directory (no admin UAC required) and creates Desktop/Start Menu shortcuts. |
| **Portable Single-File** | `AudioGuard-Portable-x64.exe` | `AudioGuard-Portable-x86.exe` | Standalone `.exe` requiring zero installation. Run anywhere directly from a USB stick or Desktop. |
| **Directory Bundle** | `AudioGuard-Bundle-x64.zip` | `AudioGuard-Bundle-x86.zip` | Full unpacked portable folder. |

---

## Local Development & Building

### Requirements
- Python 3.11+
- Windows 10 or 11 (recommended for Win32 testing)

### Setup & Run
```bash
git clone https://github.com/midimahdi/audioguard.git
cd audioguard

python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat

pip install -r requirements.txt
python main.py
```

### Automated Engine & Crash Simulation Verification
To verify the crash-resilience engine and FLAC power-loss decoding:
```bash
python verify_engine.py
```

### Local PyInstaller Build
```bat
build_exe.bat
```

---

## Architecture Overview

- `audio_engine.py` — PortAudio stream handling, always-on DSP, dBFS metering, headphone output, and FLAC writer with 1s `fsync`.
- `config_manager.py` — Atomic JSON configuration (`.tmp` + `os.replace`), MP3 stream converter, power-cut recovery scanner, and dual-format retention cleanup.
- `scheduler.py` — Multi-slot watchdog engine, late-boot catch-up, overtime extension, and per-slot suppression reset.
- `tray_manager.py` — `pystray` system tray integration with dynamic Pillow icons and admin quit confirmation.
- `main.py` — CustomTkinter dark dashboard, scrollable settings view, single-instance mutex & IPC, and timer updates.
- `installer/AudioGuard-Setup.iss` — Inno Setup script for building the 1-click installer.
- `.github/workflows/build.yml` — Multi-architecture GitHub Actions CI/CD matrix building x64 and x86 releases.

---

## License

Proprietary / Private — MAHDI DIGITAL LLC. All rights reserved.
