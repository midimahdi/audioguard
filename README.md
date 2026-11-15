<div align="center">

# 🛡️ AudioGuard

**Automatic, reliable audio backup for Windows, macOS & Linux.**  
*Records in perfect quality and protects against sudden power cuts, device shutdowns, or accidental app closes.*

[![Latest Release](https://img.shields.io/github/v/release/midimahdi/audioguard?color=10B981&label=Release)](https://github.com/midimahdi/audioguard/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/midimahdi/audioguard/total?color=blue&label=Downloads)](https://github.com/midimahdi/audioguard/releases)
[![Platforms](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-3B82F6)](https://github.com/midimahdi/audioguard/releases/latest)
[![Build Status](https://img.shields.io/github/actions/workflow/status/midimahdi/audioguard/build.yml?branch=main&label=CI%2FCD)](https://github.com/midimahdi/audioguard/actions)
[![License](https://img.shields.io/badge/License-Proprietary-gray)](LICENSE)

<br/>

[**📥 Direct Downloads**](#downloads) &nbsp;•&nbsp; [**🎯 Why AudioGuard**](#why) &nbsp;•&nbsp; [**🛠️ Developer Guide**](#developer-guide) &nbsp;•&nbsp; [**🔬 Architecture**](#architecture)

</div>

---

<a id="downloads"></a>
## ⚡ Direct Downloads (Latest Release: v1.5.4)

Choose your operating system to start downloading immediately:

### 🪟 Windows (10 & 11)
| Edition | Direct Download Link | Description |
| :--- | :--- | :--- |
| **64-bit Installer (Recommended)** | [📥 **AudioGuard-Setup-x64.exe**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-Setup-x64.exe) | 1-click install (no admin rights needed), creates Desktop/Start Menu shortcuts |
| **Portable (Zero-Install)** | [⚡ **AudioGuard-Portable-x64.exe**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-Portable-x64.exe) | Single-file `.exe`. Run directly from Desktop or USB drive |
| **32-bit Legacy Installer** | [📥 **AudioGuard-Setup-x86.exe**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-Setup-x86.exe) | For older 32-bit Windows systems |
| **Full Unpacked Zip** | [📦 **AudioGuard-Bundle-x64.zip**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-Bundle-x64.zip) | Portable directory archive |

### 🍎 macOS (12 Monterey through 15 Sequoia)
| Chipset | Direct Download Link | Description |
| :--- | :--- | :--- |
| **Apple Silicon (M1/M2/M3/M4)** | [📥 **AudioGuard-macOS-AppleSilicon.dmg**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-macOS-AppleSilicon.dmg) | Drag-and-drop disk image for modern Apple Silicon Macs |
| **Intel Core (x86_64)** | [📥 **AudioGuard-macOS-Intel.dmg**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-macOS-Intel.dmg) | Drag-and-drop disk image for Intel-based Macs |
| **App Bundle (.zip)** | [📦 **AudioGuard-macOS-AppleSilicon.zip**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-macOS-AppleSilicon.zip) \| [**Intel.zip**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-macOS-Intel.zip) | Standalone `.app` bundle archive |

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, Linux Mint)
| Architecture | Direct Download Link | Description |
| :--- | :--- | :--- |
| **Linux (x86_64)** | [📥 **AudioGuard-Linux-x86_64.tar.gz**](https://github.com/midimahdi/audioguard/releases/latest/download/AudioGuard-Linux-x86_64.tar.gz) | Standalone portable bundle. Extract and run `./AudioGuard` directly |

> [!TIP]
> **First-Launch Notes:**
> - **Windows:** If Windows Defender SmartScreen shows *"Unrecognized app"*, click **More info** $\rightarrow$ **Run anyway**.
> - **macOS:** If Gatekeeper blocks opening due to quarantine, run once in Terminal:  
>   `xattr -cr /Applications/AudioGuard.app` *(or right-click `AudioGuard.app` and choose **Open**)*.
> - **Linux:** If running on minimal distros, ensure audio runtimes exist:  
>   `sudo apt-get install -y libportaudio2 libsndfile1`

---

<a id="why"></a>
## 🎯 Why AudioGuard?

Traditional recording software (like Audacity or OBS) is made for studio work with someone watching the screen. If power cuts, someone trips on a plug, or the computer shuts down, the file corrupts and the whole recording is lost.

AudioGuard is built to run unattended: it continuously commits audio directly to storage, keeping your recording 100% safe and playable up to the exact second anything interrupts it.

```
Audio Input ────► Continuous Auto-Save ────► Raw Audio File
```

| Core Feature | What It Does | Why It Matters |
| :--- | :--- | :--- |
| **⚡ Power-Cut & Shutdown Proof** | Continuously commits audio to storage as audio is received | If the device loses power or abruptly shuts down, the recording is intact up to that exact second. Zero corrupted files. |
| **🕒 Automated Multi-Slot Schedules** | Automatically records daily or on specific days of the week | Set it once. AudioGuard starts on time, catches up if the computer boots late, and auto-extends if incoming audio continues. |
| **🔒 Accidental-Close Protection** | Minimizes to system tray and locks settings while recording | Users cannot accidentally stop the recording or disrupt the audio input by changing settings mid-session. |
| **🎧 Verified Instant Audio Copy** | Creates an optimized MP3 alongside the master lossless file | Automatically runs a health check to ensure every exported file is complete and fully playable before saving. |
| **💾 Smart Storage Management** | Cleans up older recordings safely based on your policy | Ensures storage never runs out of space, with automatic safety floors to protect the system. |
| **🎙️ Multiple Audio Inputs** | Run separate recording instances for different inputs or rooms | Record different audio sources or devices simultaneously on the same computer. |
| **🌐 Multilingual** | Instant in-place switching between English, Arabic, and French | Interface changes instantly without needing to restart the app. |

---

<a id="developer-guide"></a>
<details>
<summary><b>🛠️ Developer Guide: Building from Source</b></summary>

### Prerequisites
- Python 3.11+
- Windows 10/11, macOS 12+, or Linux (Ubuntu 22.04+)

### Quick Start
```bash
# Clone the repository
git clone https://github.com/midimahdi/audioguard.git
cd audioguard

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py
```

### Running the Crash-Resilience Engine Verification
To test abrupt power-cut simulation and full audio decodability:
```bash
python verify_engine.py
```

### Packaging Binaries
- **Windows:** Run `build_exe.bat`
- **macOS:** Run `bash build_mac.sh`
- **Linux:** Run `bash build_linux.sh`
</details>

---

<a id="architecture"></a>
<details>
<summary><b>🔬 Technical Architecture & Safety Mechanisms</b></summary>

### Continuous Disk Sync (Zero-Trust Storage)
AudioGuard uses a dedicated FLAC disk writer worker thread that receives 48,000 Hz, 24-bit stereo audio blocks (`PCM_24`) through a thread-safe queue. Every 1.0 second (or ~12 buffer blocks), the worker issues:
1. `sf_file.flush()`: Flushes Python and user-space library stream buffers.
2. `os.fsync(raw_file.fileno())`: Issues an OS-level kernel cache commit instruction (`FlushFileBuffers` on Windows, `fsync` on POSIX). This forces NAND/controller caches to persist data immediately to physical storage.

### 3-Step Verification Gate for Companion Files
When generating secondary `.mp3`, `.wav`, or `.ogg` exports:
1. **Decode Verification:** Opens the generated file and decodes audio frames to prove codec integrity.
2. **Duration Verification:** Ensures the companion file duration matches the master FLAC file within a strict tolerance of $\pm 0.5\text{ seconds}$.
3. **Size Sanity Gate:** Rejects files under 10 KB for recordings longer than 5 seconds, preventing 0-byte corrupt files from ever replacing valid recordings.

### Cross-Platform Sleep Prevention
- **Windows:** Calls Win32 `kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)` to prevent sleep or Modern Standby (S0ix) throttling.
- **macOS:** Spawns a dedicated background `/usr/bin/caffeinate -dimu` subprocess during recording.
- **Linux:** Spawns `/usr/bin/systemd-inhibit --what=idle:sleep:handle-lid-switch` to prevent system and lid-close suspension.

### Command-Line Arguments
```bash
AudioGuard [OPTIONS]

Options:
  --profile, -p TEXT   Configuration profile for multi-instance recording (e.g. "mic2")
  --minimized, -m      Start minimized directly to the system tray / dock
  --help               Show this message and exit
```
</details>

---

## 📜 License & Copyright

Copyright (c) 2026 **MAHDI DIGITAL LLC**. All rights reserved.  
See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md) for licensing details and vulnerability reporting.
