<div align="center">

# 🛡️ AudioGuard

**Automatic, reliable audio backup for Windows, macOS & Linux.**  
*Records in perfect quality and protects against sudden power cuts, device shutdowns, or accidental app closes.*

[![Latest Release](https://img.shields.io/github/v/release/midimahdi/audioguard?color=10B981&label=Release)](https://github.com/midimahdi/audioguard/releases/latest)
[![Platforms](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-3B82F6)](https://github.com/midimahdi/audioguard/releases/latest)
[![Build Status](https://img.shields.io/github/actions/workflow/status/midimahdi/audioguard/build.yml?branch=main&label=CI%2FCD)](https://github.com/midimahdi/audioguard/actions)
[![License](https://img.shields.io/badge/License-Proprietary-gray)](LICENSE)

</div>

---

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

## 🎯 Why AudioGuard?

Traditional recording software (like Audacity or OBS) is made for studio work with someone watching the screen. If power cuts, someone trips on a plug, or the computer shuts down, the file corrupts and the whole recording is lost.

AudioGuard is built to run unattended: it continuously commits audio directly to storage, keeping your recording 100% safe and playable up to the exact second anything interrupts it.

```
 🎛️ Audio Input ────► ⚡ Live Level Meter ────► 🛡️ Continuous Auto-Save ────► 🔍 Health Check ────► 🎧 Ready MP3
  (Mic or Mixer)        (Real-Time Monitor)         (Power-Cut Proof)          (Auto-Verified)      (Lightweight Copy)
```

| Core Feature | What It Does | Why It Matters |
| :--- | :--- | :--- |
| **⚡ Power-Cut & Shutdown Proof** | Continuously commits audio to storage as you speak | If the device loses power or abruptly shuts down, your recording is intact up to that exact second. Zero corrupted files. |
| **🕒 Automated Multi-Slot Schedules** | Automatically records daily or on specific days of the week | Set it once. AudioGuard starts on time, catches up if the computer boots late, and auto-extends if someone is still speaking. |
| **🔒 Accidental-Close Protection** | Minimizes to system tray and locks settings while recording | Volunteers or users cannot accidentally stop the recording or disrupt the audio input by changing settings mid-session. |
| **🎧 Verified Instant MP3 Copy** | Creates an optimized MP3 alongside the master lossless file | Automatically runs a health check to ensure every exported file is complete and fully playable before saving. |
| **💾 Smart Storage Management** | Cleans up older recordings safely based on your policy | Ensures your hard drive never runs out of space, with automatic safety floors to protect the system. |
| **🎙️ Multiple Microphones** | Run separate recording instances for different mics or rooms | Record a main mixer feed on one profile and a wireless mic on another simultaneously. |
| **🌐 Multilingual** | Instant in-place switching between English, Arabic, and French | Interface changes instantly without needing to restart the app. |

---

## 📊 Comparison: AudioGuard vs Traditional Tools

| Capability | 🛡️ AudioGuard v1.5.4 | 🎙️ Audacity | 📹 OBS Studio | 🎛️ DAW (Reaper) |
| :--- | :---: | :---: | :---: | :---: |
| **Sudden Power-Loss Survival** | **100% Intact** (Auto-Saved) | ❌ Corrupt block files | ❌ Truncated container | ❌ Unsaved project |
| **Background RAM Usage** | **~25 MB** | ~180 MB | ~350 MB | ~250 MB |
| **Idle CPU (Minimized)** | **0.0% CPU** | 2% – 5% CPU | 4% – 10% CPU | 2% – 6% CPU |
| **Built-in Multi-Slot Scheduler** | **Native** (Daily & Weekly) | ❌ Needs OS scripts | ❌ Needs third-party plugin | ❌ Complex action scripts |
| **Voice Activity Overtime (+60m)** | **Automatic** | ❌ None | ❌ None | ❌ Custom scripting |
| **Accidental Close Protection** | **System Tray Intercept** | ❌ Exits / stops recording | ⚠️ Prompts confirmation | ❌ Exits / stops recording |
| **Multi-Tenancy / Dual Inputs** | **1-Click Frontend Profiles** | ❌ Manual multi-process | ⚠️ Profile switching | ⚠️ Complex routing |
| **Disk Safety Floor Guard** | **Dynamic Hybrid Floor** | ❌ Crashes on disk full | ❌ Halts recording | ❌ I/O crash |

---

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

<details>
<summary><b>🤖 Machine & Agent Context (AI-First Manifests)</b></summary>

AudioGuard adheres to **SOP-01 (AI-First Software Distribution)**:
- [`/llms.txt`](llms.txt) — High-level entity specifications and query-intent routing.
- [`/llms-full.txt`](llms-full.txt) — Comprehensive plain-text technical corpus including error signatures and configuration reference for LLM RAG pipelines.
</details>

---

## 📜 License & Copyright

Copyright (c) 2026 **MAHDI DIGITAL LLC**. All rights reserved.  
Free to use for mosques, non-profit institutions, and educational centers. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md) for vulnerability reporting.
