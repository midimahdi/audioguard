# AudioGuard

> **Bulletproof, crash-resistant lossless audio backup system for Windows & macOS.**  
> Designed for mosque mixers, lectures, and live venues to survive sudden power cuts without file corruption.

---

## Key Features

- **Crash-Proof Lossless FLAC Engine:**  
  Records at 48,000 Hz, 24-bit stereo. Performs an explicit `sf_file.flush()` and `os.fsync()` every 1.0 second. If power cuts mid-sentence, the recording is 100% loss-free and playable right up to the exact moment power was lost.
- **Automatic MP3 Export with Power-Cut Recovery:**  
  Generates a lightweight `.mp3` copy alongside the master `.flac` file upon session completion. If power was cut while recording, AudioGuard's stream-chunk recovery engine automatically detects the unclosed FLAC file upon system reboot, safely decodes all flushed frames, and exports the MP3 copy.
- **Smart Multi-Slot Daily Scheduler:**  
  Supports arbitrary daily time frames (e.g. `09:00–10:00`, `12:00–14:00`, `18:00–21:00`) with a master toggle protected by accidental-click confirmation prompts.
  - **Late-Boot Catch-Up:** If the PC boots mid-window, recording starts immediately.
  - **Speech Overtime Extension:** If voice activity is still detected when the scheduled end time is reached, recording automatically extends for up to an extra 1 hour (+60 min cap) and finalizes once 90 seconds of silence occurs.
  - **Intelligent Pause Reset:** Stopping a scheduled recording suppresses auto-restart only for that active window; suppression automatically resets as soon as that slot passes.
- **Fail-Safe Storage Guard:**  
  If the chosen backup path (e.g. external USB drive) is detached or inaccessible, AudioGuard automatically redirects recording to `C:\AudioBackups\` (Windows) or `~/AudioBackups/` (macOS) so audio is never dropped.
- **Customizable File Naming:**  
  Configure custom naming patterns using dynamic tokens (`{date}`, `{time}`, `{year}`, `{month}`, `{day}`, `{hour}`, `{min}`, `{sec}`, `{mode}`) with real-time live preview and character sanitization.
- **Volunteer-Proof Dark UI & System Integration:**  
  - Dedicated Dashboard (Status Card, Level Meter, Summary, Action Button) and separate scrollable Settings panel.
  - Background protection: Closing the window minimizes to the Windows System Tray or macOS Dock.
  - Dedicated 1-second elapsed recording clock (`[HH:MM:SS]`).
  - Zero-CPU idle when minimized or hidden (`winfo_viewable()`).
  - Single-instance lock via Named Mutex / POSIX lock and localhost IPC (`127.0.0.1:54983`) that brings existing window to the front without error popups.
  - 1-click **"Open Diagnostic Log File"** shortcut to open `app.log` in the system editor.
- **Cross-Platform Sleep Prevention:**  
  - Windows: Win32 `SetThreadExecutionState` (`ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED`).
  - macOS: Integrated `/usr/bin/caffeinate -dimu` process preventing display, system, and disk idle sleep during active recording sessions.

---

## Downloads

### Windows (10 & 11)

| Type | 64-bit (x64) | 32-bit (x86) | Description |
| :--- | :--- | :--- | :--- |
| **1-Click Setup Installer** | `AudioGuard-Setup-x64.exe` | `AudioGuard-Setup-x86.exe` | Standard Windows installer. Installs to user directory (no admin UAC required) and creates Desktop/Start Menu shortcuts. |
| **Portable Single-File** | `AudioGuard-Portable-x64.exe` | `AudioGuard-Portable-x86.exe` | Standalone `.exe` requiring zero installation. Run anywhere directly from a USB stick or Desktop. |
| **Directory Bundle** | `AudioGuard-Bundle-x64.zip` | `AudioGuard-Bundle-x86.zip` | Full unpacked portable folder. |

### macOS (12 Monterey through 15 Sequoia)

| Architecture | Package | File | Description |
| :--- | :--- | :--- | :--- |
| **Apple Silicon (M1/M2/M3/M4)** | Drag-and-Drop DMG | `AudioGuard-macOS-AppleSilicon.dmg` | Native ARM64 disk image for modern Macs. |
| **Apple Silicon (M1/M2/M3/M4)** | App Bundle ZIP | `AudioGuard-macOS-AppleSilicon.zip` | Standalone `.app` bundle (ARM64). |
| **Intel (Core i5/i7/i9 / Xeon)** | Drag-and-Drop DMG | `AudioGuard-macOS-Intel.dmg` | Native x86_64 disk image for older Intel Macs. |
| **Intel (Core i5/i7/i9 / Xeon)** | App Bundle ZIP | `AudioGuard-macOS-Intel.zip` | Standalone `.app` bundle (x86_64). |

---

## Local Development & Building

### Requirements
- Python 3.11+
- Windows 10/11 or macOS 12+

### Setup & Run
```bash
git clone https://github.com/midimahdi/audioguard.git
cd audioguard

python3 -m venv .venv
# On Windows:
.venv\Scripts\activate.bat
# On macOS:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

### Automated Engine & Crash Simulation Verification
To verify the crash-resilience engine and FLAC power-loss decoding:
```bash
python verify_engine.py
```

### Local Packaging
- **Windows:** Run `build_exe.bat`
- **macOS:** Run `bash build_mac.sh`

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
