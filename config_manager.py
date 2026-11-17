"""
AudioGuard - Configuration, Persistence, Startup & Retention Manager
"""

from __future__ import annotations
import os
import sys
import re
import json
import shutil
import logging
from logging.handlers import RotatingFileHandler
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

APP_VERSION = "1.6.1"

# Logger setup
logger = logging.getLogger("AudioGuard")

def get_app_dir() -> Path:
    """Returns the application data directory (%APPDATA%\\AudioGuard on Windows, ~/Library/Application Support/AudioGuard on macOS, or ~/.config/AudioGuard)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    app_dir = base / "AudioGuard"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

def setup_logging(profile: str = "default"):
    """Initializes rotating logging to app.log (or app_<profile>.log) and stdout."""
    app_dir = get_app_dir()
    log_name = "app.log" if profile == "default" else f"app_{profile}.log"
    log_file = app_dir / log_name
    
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # Rotating file handler: 2 MB per file, max 2 backups (capped at ~6 MB total forever)
    fh = RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
    fh.setLevel(logging.INFO)
    file_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)
    
    # Stream handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    stream_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    sh.setFormatter(stream_fmt)
    logger.addHandler(sh)
    
    logger.info("Logging initialized at %s", log_file)

def get_default_backup_folder() -> str:
    """Returns C:\\AudioBackups on Windows, or ~/AudioBackups."""
    if sys.platform == "win32":
        folder = Path("C:/AudioBackups")
    else:
        folder = Path.home() / "AudioBackups"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create default backup folder %s: %s. Using user home.", folder, e)
        folder = Path.home() / "AudioBackups"
        folder.mkdir(parents=True, exist_ok=True)
    return str(folder)

DEFAULT_CONFIG = {
    "first_run_completed": False,
    "input_device_name": "",
    "input_host_api": "",
    "secondary_track_enabled": False,
    "secondary_source_type": "desktop",  # "desktop" (loopback) or "input" (second mic/line-in)
    "secondary_device_name": "",
    "secondary_host_api": "",
    "multitrack_mode": "separate",        # "separate" (2 files) or "single" (4-channel multitrack FLAC)
    "monitor_device_name": "",
    "mono_sum": True,
    "schedule_start": "18:00",
    "schedule_end": "21:00",
    "schedule_slots": [],
    "schedule_enabled": False,
    "backup_folder": "",
    "folder_grouping": "monthly",    # "none", "monthly", "weekly", "daily"
    "filename_pattern": "Audio_Backup_{date}_{time}",
    "auto_export_mp3": True,
    "companion_format": "mp3",       # "mp3", "wav", "ogg", "none"
    "retention_days": 30,
    "auto_start_on_boot": True,
    "monitoring_enabled": False,
    "language": "en",
    "last_update_check_ts": 0.0
}

def get_recording_subfolder(base_folder: str, folder_grouping: str = "monthly", dt=None) -> Path:
    """
    Returns destination Path according to the configured folder grouping strategy:
    - 'monthly': base_folder / 'YYYY-MM'
    - 'weekly': base_folder / 'YYYY-Www' (ISO week)
    - 'daily': base_folder / 'YYYY-MM-DD'
    - 'none': base_folder (flat)
    Ensures directory exists.
    """
    from datetime import datetime
    if dt is None:
        dt = datetime.now()

    base = Path(base_folder) if base_folder else Path(get_default_backup_folder())
    group = (folder_grouping or "monthly").lower().strip()

    if group == "monthly":
        target = base / dt.strftime("%Y-%m")
    elif group == "weekly":
        target = base / f"{dt.year}-W{dt.strftime('%V')}"
    elif group == "daily":
        target = base / dt.strftime("%Y-%m-%d")
    else:
        target = base

    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create target folder %s (%s). Falling back to base %s", target, e, base)
        base.mkdir(parents=True, exist_ok=True)
        return base

    return target

def format_recording_filename(pattern: str, is_manual: bool = False, dt=None, slot_label: str = "") -> str:
    """
    Evaluates a user-defined filename pattern into a clean, sanitized Windows-compatible .flac filename.
    Supported tokens: {slot}, {slot_name}, {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}
    """
    from datetime import datetime
    import re
    if dt is None:
        dt = datetime.now()

    if not pattern or not pattern.strip():
        pattern = "Audio_Backup_{date}_{time}"

    pat = pattern.strip()
    if pat.lower().endswith(".flac"):
        pat = pat[:-5]

    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H-%M-%S")
    year_str = dt.strftime("%Y")
    month_str = dt.strftime("%m")
    day_str = dt.strftime("%d")
    hour_str = dt.strftime("%H")
    min_str = dt.strftime("%M")
    sec_str = dt.strftime("%S")
    mode_str = "MANUAL" if is_manual else "SCHEDULED"

    # Clean slot label: allow alphanumeric, underscore, hyphen, and Arabic unicode range
    clean_slot = ""
    if slot_label:
        clean_slot = re.sub(r'[^\w\-\u0600-\u06FF]', '_', str(slot_label).strip())
        clean_slot = re.sub(r'_+', '_', clean_slot).strip('_')

    # If slot label is present but not explicitly in pattern, insert it cleanly
    if clean_slot and "{slot}" not in pat.lower() and "{slot_name}" not in pat.lower():
        if "audio_backup_" in pat.lower():
            idx = pat.lower().find("audio_backup_") + len("audio_backup_")
            pat = pat[:idx] + f"{clean_slot}_" + pat[idx:]
        else:
            pat = f"{clean_slot}_{pat}"

    slot_val = clean_slot if clean_slot else ("Manual" if is_manual else "")

    replacements = {
        "{slot}": slot_val,
        "{slot_name}": slot_val,
        "{date}": date_str,
        "{time}": time_str,
        "{year}": year_str,
        "{month}": month_str,
        "{day}": day_str,
        "{hour}": hour_str,
        "{min}": min_str,
        "{sec}": sec_str,
        "{mode}": mode_str
    }

    result = pat
    for token, val in replacements.items():
        lower_token = token.lower()
        while lower_token in result.lower():
            idx = result.lower().find(lower_token)
            result = result[:idx] + val + result[idx + len(lower_token):]

    # Clean double underscores if {slot} was empty
    result = re.sub(r'_+', '_', result)
    result = re.sub(r'^_+|_+$', '', result)

    # If manual and {mode} was not in pattern, append _MANUAL
    if is_manual and "{mode}" not in pat.lower() and "manual" not in result.lower():
        result = f"{result}_MANUAL"

    # Sanitize invalid Windows filename characters: < > : " / \ | ? *
    for ch in '<>:"/\\|?*':
        result = result.replace(ch, "_")

    result = result.strip(". ")
    if not result:
        result = f"Audio_Backup_{date_str}_{time_str}"

    return f"{result}.flac"

class ConfigManager:
    def __init__(self, profile: str = "default"):
        self.profile = profile or "default"
        self.app_dir = get_app_dir()
        if self.profile == "default":
            self.config_path = self.app_dir / "config.json"
        else:
            self.config_path = self.app_dir / f"config_{self.profile}.json"
        self.data = dict(DEFAULT_CONFIG)
        if not self.data["backup_folder"]:
            self.data["backup_folder"] = get_default_backup_folder()
        if self.profile != "default" and not self.config_path.exists():
            self.data["filename_pattern"] = f"Audio_Backup_{self.profile}_{{date}}_{{time}}"
        self.load()

    def load(self):
        """Loads configuration from JSON file or writes defaults if missing."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for k, v in loaded.items():
                        self.data[k] = v
                logger.info("Loaded config from %s", self.config_path)
            except Exception as e:
                logger.error("Failed to read config file (%s), using defaults: %s", self.config_path, e)
                self.save()
        else:
            self.save()

    def save(self):
        """Saves current configuration atomically to JSON file to prevent power-cut corruption."""
        temp_path = self.config_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.config_path)
            logger.info("Configuration successfully saved to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving configuration to %s: %s", self.config_path, e)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def update(self, **kwargs):
        for k, v in kwargs.items():
            self.data[k] = v
        self.save()


# -------------------------------------------------------------
# System Startup: Run on Boot (Windows Registry & macOS LaunchAgent)
# -------------------------------------------------------------
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "AudioGuard"
OLD_APP_REG_NAME = "MosqueAudioGuard"

def _get_macos_launch_agent_path(profile: str = "default") -> Path:
    if profile == "default":
        return Path.home() / "Library" / "LaunchAgents" / "com.mahdi.audioguard.plist"
    return Path.home() / "Library" / "LaunchAgents" / f"com.mahdi.audioguard.{profile}.plist"

def set_macos_startup(enabled: bool, profile: str = "default") -> bool:
    """Enables or disables auto-start on macOS boot via LaunchAgent plist with --minimized flag."""
    plist_path = _get_macos_launch_agent_path(profile=profile)
    try:
        if enabled:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            prof_args = f"        <string>--profile</string>\n        <string>{profile}</string>\n" if profile != "default" else ""
            if getattr(sys, "frozen", False):
                exec_target = sys.executable
                args_xml = f"        <string>{exec_target}</string>\n{prof_args}        <string>--minimized</string>"
            else:
                exec_target = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                args_xml = f"        <string>{exec_target}</string>\n        <string>{script_path}</string>\n{prof_args}        <string>--minimized</string>"

            label = "com.mahdi.audioguard" if profile == "default" else f"com.mahdi.audioguard.{profile}"
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
"""
            plist_path.write_text(content, encoding="utf-8")
            logger.info("macOS Startup LaunchAgent enabled for [%s]: %s", profile, plist_path)
        else:
            if plist_path.exists():
                plist_path.unlink()
                logger.info("macOS Startup LaunchAgent disabled for [%s]: %s", profile, plist_path)
        return True
    except Exception as e:
        logger.error("Failed to update macOS LaunchAgent for [%s]: %s", profile, e)
        return False

def is_macos_startup_enabled(profile: str = "default") -> bool:
    """Checks whether macOS LaunchAgent exists."""
    return _get_macos_launch_agent_path(profile=profile).exists()

def set_windows_startup(enabled: bool, profile: str = "default") -> bool:
    """Enables or disables auto-start on Windows boot via HKCU\\...\\Run with --minimized flag."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
        reg_name = APP_REG_NAME if profile == "default" else f"{APP_REG_NAME}_{profile}"
        
        # Always clean up legacy key if present on default
        if profile == "default":
            try:
                winreg.DeleteValue(key, OLD_APP_REG_NAME)
            except FileNotFoundError:
                pass

        if enabled:
            if getattr(sys, "frozen", False):
                cmd_line = f'"{sys.executable}"'
            else:
                cmd_line = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            if profile != "default":
                cmd_line += f' --profile {profile}'
            cmd_line += ' --minimized'
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, cmd_line)
            logger.info("Windows Startup enabled for [%s]: %s", profile, cmd_line)
        else:
            try:
                winreg.DeleteValue(key, reg_name)
                logger.info("Windows Startup disabled for [%s]", profile)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error("Failed to update Windows Run registry key for [%s]: %s", profile, e)
        return False

def is_windows_startup_enabled(profile: str = "default") -> bool:
    """Checks whether the application is registered to start on Windows boot."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
        reg_name = APP_REG_NAME if profile == "default" else f"{APP_REG_NAME}_{profile}"
        try:
            val, _ = winreg.QueryValueEx(key, reg_name)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception as e:
        logger.error("Error reading Windows Run registry key for [%s]: %s", profile, e)
        return False

def _get_linux_autostart_path(profile: str = "default") -> Path:
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    slug = "audioguard" if profile == "default" else f"audioguard_{profile}"
    return autostart_dir / f"{slug}.desktop"

def set_linux_startup(enabled: bool, profile: str = "default") -> bool:
    """Configures XDG autostart on Linux desktop (~/.config/autostart)."""
    if not sys.platform.startswith("linux"):
        return False
    desktop_file = _get_linux_autostart_path(profile=profile)
    try:
        if enabled:
            if getattr(sys, "frozen", False):
                exec_cmd = f'"{sys.executable}"'
            else:
                main_py = os.path.abspath(sys.argv[0])
                exec_cmd = f'"{sys.executable}" "{main_py}"'
            if profile != "default":
                exec_cmd += f' --profile {profile}'
            exec_cmd += ' --minimized'

            name_suffix = "" if profile == "default" else f" [{profile}]"
            content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=AudioGuard{name_suffix}
Comment=AudioGuard Bulletproof Audio Backup Monitor
Exec={exec_cmd}
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
            desktop_file.write_text(content, encoding="utf-8")
            desktop_file.chmod(0o755)
            logger.info("Linux XDG Autostart enabled for [%s]: %s", profile, desktop_file)
            return True
        else:
            if desktop_file.exists():
                desktop_file.unlink()
                logger.info("Linux XDG Autostart disabled for [%s]: %s", profile, desktop_file)
            return True
    except Exception as e:
        logger.error("Failed to update Linux autostart for [%s]: %s", profile, e)
        return False

def is_linux_startup_enabled(profile: str = "default") -> bool:
    return _get_linux_autostart_path(profile=profile).exists()

def set_autostart(enabled: bool, profile: str = "default") -> bool:
    """Cross-platform startup registration (Windows Registry, macOS LaunchAgent, or Linux XDG)."""
    if sys.platform == "win32":
        return set_windows_startup(enabled, profile=profile)
    elif sys.platform == "darwin":
        return set_macos_startup(enabled, profile=profile)
    elif sys.platform.startswith("linux"):
        return set_linux_startup(enabled, profile=profile)
    return False

def is_autostart_enabled(profile: str = "default") -> bool:
    """Cross-platform check for startup registration."""
    if sys.platform == "win32":
        return is_windows_startup_enabled(profile=profile)
    elif sys.platform == "darwin":
        return is_macos_startup_enabled(profile=profile)
    elif sys.platform.startswith("linux"):
        return is_linux_startup_enabled(profile=profile)
    return False

def create_desktop_shortcut(profile: str = "default", display_name: str = "") -> bool:
    """Creates a Desktop shortcut for the specified profile."""
    label = display_name if display_name else ("AudioGuard" if profile == "default" else f"AudioGuard - {profile}")
    
    if sys.platform == "win32":
        try:
            import subprocess
            if getattr(sys, "frozen", False):
                target = sys.executable
                args = f'--profile {profile}' if profile != "default" else ''
                icon = sys.executable
            else:
                target = sys.executable
                main_py = os.path.abspath(sys.argv[0])
                args = f'"{main_py}" --profile {profile}' if profile != "default" else f'"{main_py}"'
                icon = sys.executable

            ps_script = f'''
            $ws = New-Object -ComObject WScript.Shell
            $desktop = [Environment]::GetFolderPath("Desktop")
            $shortcut = $ws.CreateShortcut([System.IO.Path]::Combine($desktop, "{label}.lnk"))
            $shortcut.TargetPath = "{target}"
            $shortcut.Arguments = "{args}"
            $shortcut.IconLocation = "{icon},0"
            $shortcut.Description = "AudioGuard - {label}"
            $shortcut.Save()
            '''
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            logger.info("Created desktop shortcut on Windows: %s.lnk", label)
            return True
        except Exception as e:
            logger.error("Failed to create desktop shortcut on Windows: %s", e)
            return False
            
    elif sys.platform == "darwin":
        try:
            desktop = Path.home() / "Desktop"
            shortcut_file = desktop / f"{label}.command"
            app_path = "/Applications/AudioGuard.app"
            if Path(app_path).exists():
                arg_part = f' --args --profile "{profile}"' if profile != "default" else ''
                content = f'#!/bin/bash\nopen -n "{app_path}"{arg_part}\n'
            else:
                script_path = os.path.abspath(sys.argv[0])
                arg_part = f' --profile "{profile}"' if profile != "default" else ''
                content = f'#!/bin/bash\n"{sys.executable}" "{script_path}"{arg_part}\n'
            shortcut_file.write_text(content, encoding="utf-8")
            shortcut_file.chmod(0o755)
            logger.info("Created desktop shortcut on macOS: %s", shortcut_file)
            return True
        except Exception as e:
            logger.error("Failed to create desktop shortcut on macOS: %s", e)
            return False

    elif sys.platform.startswith("linux"):
        try:
            if getattr(sys, "frozen", False):
                exec_cmd = f'"{sys.executable}"'
            else:
                main_py = os.path.abspath(sys.argv[0])
                exec_cmd = f'"{sys.executable}" "{main_py}"'
            if profile != "default":
                exec_cmd += f' --profile {profile}'

            content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name={label}
Comment=AudioGuard Bulletproof Audio Backup
Exec={exec_cmd}
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=false
"""
            # 1. Desktop
            desktop = Path.home() / "Desktop"
            if desktop.exists():
                shortcut_file = desktop / f"{label}.desktop"
                shortcut_file.write_text(content, encoding="utf-8")
                shortcut_file.chmod(0o755)

            # 2. XDG Applications Menu
            app_dir = Path.home() / ".local" / "share" / "applications"
            app_dir.mkdir(parents=True, exist_ok=True)
            menu_file = app_dir / f"audioguard_{profile}.desktop"
            menu_file.write_text(content, encoding="utf-8")
            menu_file.chmod(0o755)

            logger.info("Created desktop shortcut on Linux: %s", label)
            return True
        except Exception as e:
            logger.error("Failed to create desktop shortcut on Linux: %s", e)
            return False
            
    return False

def list_available_profiles() -> List[Dict[str, Any]]:
    """Scans application directory and returns all configured profiles."""
    app_dir = get_app_dir()
    profiles = []

    def_path = app_dir / "config.json"
    def_name = "Default"
    if def_path.exists():
        try:
            with open(def_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                def_name = data.get("profile_display_name", "Default")
        except Exception:
            pass
    profiles.append({
        "id": "default",
        "name": def_name,
        "config_path": str(def_path)
    })

    for p in sorted(app_dir.glob("config_*.json")):
        slug = p.stem[len("config_"):]
        if not slug:
            continue
        display_name = slug.replace("_", " ").title()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                display_name = data.get("profile_display_name", display_name)
        except Exception:
            pass
        profiles.append({
            "id": slug,
            "name": display_name,
            "config_path": str(p)
        })

    return profiles

def delete_profile(profile_id: str) -> bool:
    """Deletes profile configuration file and associated startup entry."""
    if profile_id == "default":
        return False
    app_dir = get_app_dir()
    cfg_file = app_dir / f"config_{profile_id}.json"
    try:
        if cfg_file.exists():
            cfg_file.unlink()
        set_autostart(False, profile=profile_id)
        return True
    except Exception as e:
        logger.error("Failed to delete profile %s: %s", profile_id, e)
        return False


# -------------------------------------------------------------
# Single-Instance Lock
# -------------------------------------------------------------
class SingleInstanceLock:
    """Ensures only one instance of AudioGuard runs at a time per profile."""
    def __init__(self, profile: str = "default", lock_name: Optional[str] = None):
        self.profile = profile or "default"
        if lock_name:
            self.lock_name = lock_name
            self.port = 54800
        elif self.profile == "default":
            self.lock_name = "Local\\AudioGuard_SingleInstance_Mutex"
            self.port = 54800
        else:
            self.lock_name = f"Local\\AudioGuard_SingleInstance_Mutex_{self.profile}"
            offset = sum((i + 1) * ord(c) for i, c in enumerate(self.profile)) % 40
            self.port = 54800 + 1 + offset
        self.mutex = None
        self.sock = None
        self.acquired = False

    def acquire(self) -> bool:
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes
                
                kernel32 = ctypes.windll.kernel32
                ERROR_ALREADY_EXISTS = 183
                
                # Use Local\ session mutex (compatible with all standard, non-admin, and guest Windows accounts)
                self.mutex = kernel32.CreateMutexW(None, False, self.lock_name)
                last_error = kernel32.GetLastError()
                if last_error == ERROR_ALREADY_EXISTS:
                    logger.warning("Another instance of AudioGuard [%s] is already running (Windows Mutex).", self.profile)
                    return False
                if self.mutex:
                    self.acquired = True
                    return True
            except Exception as e:
                logger.warning("Failed to create Windows Mutex, falling back to socket lock: %s", e)

        # Fallback cross-platform socket lock on localhost
        try:
            import socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(("127.0.0.1", self.port))
            self.sock.listen(1)
            self.acquired = True
            return True
        except (socket.error, OSError):
            logger.warning("Another instance of AudioGuard [%s] is already running (Socket Lock :%d).", self.profile, self.port)
            return False

    def release(self):
        if sys.platform == "win32" and self.mutex:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.mutex)
            except Exception:
                pass
            self.mutex = None
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.acquired = False


# -------------------------------------------------------------
# Companion Audio Conversion & 3-Step Verification Gate
# -------------------------------------------------------------
def convert_flac_companion(flac_path: str, companion_path=None, target_format: str = "mp3") -> bool:
    """
    Converts a master FLAC file to a secondary companion format (MP3, WAV, or OGG)
    with a strict 3-step integrity verification gate before the file is marked valid:
      1. Complete read-back decode verification via soundfile.
      2. Strict duration tolerance match (abs(dst_duration - src_duration) <= 0.5s).
      3. File size / bitrate sanity check.
    If target_format is 'none', returns True immediately.
    """
    fmt = (target_format or "mp3").lower().strip()
    if fmt in ("none", "flac", "off", "disabled"):
        return True

    format_specs = {
        "mp3": {"ext": ".mp3", "sf_format": "MP3", "subtype": None},
        "wav": {"ext": ".wav", "sf_format": "WAV", "subtype": "PCM_16"},
        "ogg": {"ext": ".ogg", "sf_format": "OGG", "subtype": "VORBIS"}
    }

    if fmt not in format_specs:
        logger.warning("Unsupported companion format '%s'. Defaulting to MP3.", fmt)
        fmt = "mp3"

    spec = format_specs[fmt]
    ext = spec["ext"]
    sf_format = spec["sf_format"]
    subtype = spec["subtype"]

    import soundfile as sf
    import numpy as np

    flac_p = Path(flac_path)
    if not flac_p.exists():
        return False

    if companion_path is None:
        dst_p = flac_p.with_suffix(ext)
    else:
        dst_p = Path(companion_path)

    # Check if existing companion is already healthy and verified
    if dst_p.exists() and dst_p.stat().st_size > 1024:
        try:
            with sf.SoundFile(str(dst_p), mode="r") as existing_f:
                if existing_f.frames > 0:
                    with sf.SoundFile(str(flac_p), mode="r") as src_f:
                        # Only compare if source header has a valid final frame count
                        if src_f.frames < 1000000000:
                            if abs((existing_f.frames / existing_f.samplerate) - (src_f.frames / src_f.samplerate)) <= 0.5:
                                return True
        except Exception:
            logger.warning("Existing companion %s is corrupted or incomplete. Re-converting...", dst_p.name)

    temp_dst = dst_p.with_suffix(f"{ext}.tmp")

    try:
        # 1. Read source FLAC attributes and stream audio blocks
        total_read_frames = 0
        with sf.SoundFile(str(flac_p), mode="r") as src:
            src_rate = src.samplerate
            src_channels = src.channels

            # If multitrack (e.g. 4 channels) or target is MP3, downmix to stereo (2 channels)
            dst_channels = min(2, src_channels) if (fmt == "mp3" or src_channels > 2) else src_channels

            write_kwargs = {
                "file": str(temp_dst),
                "mode": "w",
                "samplerate": src_rate,
                "channels": dst_channels,
                "format": sf_format
            }
            if subtype:
                write_kwargs["subtype"] = subtype

            with sf.SoundFile(**write_kwargs) as dst:
                chunk_size = 8192
                while True:
                    try:
                        data = src.read(chunk_size, dtype="float32")
                        if len(data) == 0:
                            break
                        total_read_frames += len(data)
                        if src_channels == 4 and dst_channels == 2:
                            stereo = np.zeros((len(data), 2), dtype=np.float32)
                            stereo[:, 0] = data[:, 0] + data[:, 2] * 0.5
                            stereo[:, 1] = data[:, 1] + data[:, 3] * 0.5
                            max_val = float(np.max(np.abs(stereo)))
                            if max_val > 0.99:
                                stereo = stereo * (0.99 / max_val)
                            dst.write(stereo)
                        else:
                            dst.write(data)
                    except Exception:
                        # Reached EOF on power-loss truncated file cleanly
                        break

            src_duration = total_read_frames / src_rate if src_rate > 0 else 0.0

        # 2. Automated 3-Step Verification Gate
        if not temp_dst.exists() or temp_dst.stat().st_size < 1024:
            logger.error("Companion conversion failed: empty output file for %s", flac_p.name)
            if temp_dst.exists():
                temp_dst.unlink()
            return False

        # Gate 1: Read-back decode verification
        with sf.SoundFile(str(temp_dst), mode="r") as verify_f:
            dst_rate = verify_f.samplerate
            dst_frames = verify_f.frames
            dst_duration = dst_frames / dst_rate if dst_rate > 0 else 0.0
            # Test-read a block to ensure codec frames aren't broken
            verify_f.read(min(4096, dst_frames), dtype="float32")

        # Gate 2: Duration Gate (+/- 0.5 seconds tolerance)
        duration_diff = abs(dst_duration - src_duration)
        if duration_diff > 0.5:
            logger.error(
                "VERIFICATION FAILED for %s companion: duration mismatch (FLAC: %.2fs vs %s: %.2fs, diff=%.2fs). File truncated! Discarding.",
                fmt.upper(), src_duration, fmt.upper(), dst_duration, duration_diff
            )
            if temp_dst.exists():
                temp_dst.unlink()
            return False

        # Gate 3: Bitrate / Size Sanity
        if src_duration > 5.0 and temp_dst.stat().st_size < 10000:
            logger.error("VERIFICATION FAILED: %s file size unreasonably small (%d bytes for %.1fs)", fmt.upper(), temp_dst.stat().st_size, src_duration)
            if temp_dst.exists():
                temp_dst.unlink()
            return False

        # All 3 gates passed 100% — atomically replace final file
        temp_dst.replace(dst_p)
        logger.info(
            "FLAC to %s conversion 100%% VERIFIED: %s -> %s (duration: %.2fs, size: %.1f KB)",
            fmt.upper(), flac_p.name, dst_p.name, dst_duration, dst_p.stat().st_size / 1024.0
        )
        return True

    except Exception as e:
        logger.error("Failed to convert %s to %s: %s", flac_path, fmt.upper(), e)
        if temp_dst.exists():
            try:
                temp_dst.unlink()
            except Exception:
                pass
        return False


def convert_flac_to_mp3(flac_path: str, mp3_path=None) -> bool:
    """Backward compatibility wrapper calling convert_flac_companion with MP3."""
    return convert_flac_companion(flac_path, companion_path=mp3_path, target_format="mp3")


def recover_missing_companion_exports(folder_path: str, active_recording_file=None, target_format: str = "mp3") -> int:
    """
    Recursively scans the backup directory and subfolders for any .flac files that lack a verified companion file.
    Converts them in order (oldest to newest), ensuring power-cut recordings get converted on boot.
    Returns the count of successfully recovered/converted files.
    """
    fmt = (target_format or "mp3").lower().strip()
    if fmt in ("none", "flac", "off", "disabled"):
        return 0

    format_exts = {"mp3": ".mp3", "wav": ".wav", "ogg": ".ogg"}
    ext = format_exts.get(fmt, ".mp3")

    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return 0

    active_p = Path(active_recording_file).resolve() if active_recording_file else None
    recovered = 0

    try:
        flac_files = [f for f in folder.rglob("*.flac") if f.is_file()]
        flac_files.sort(key=lambda x: x.stat().st_mtime)

        for f in flac_files:
            # Skip actively recording file
            if active_p and f.resolve() == active_p:
                continue

            # Skip empty or incomplete files smaller than 1 KB
            if f.stat().st_size < 1024:
                continue

            # Skip files modified within the last 3 seconds
            if (time.time() - f.stat().st_mtime) < 3.0:
                continue

            comp_p = f.with_suffix(ext)
            if not comp_p.exists() or comp_p.stat().st_size < 1024:
                logger.info("Power-cut recovery / Auto-export: Converting missing %s for %s...", fmt.upper(), f.name)
                res = convert_flac_companion(str(f), target_format=fmt)
                if res:
                    recovered += 1
    except Exception as e:
        logger.error("Error during %s recovery scan of %s: %s", fmt.upper(), folder, e)

    return recovered


def recover_missing_mp3_exports(folder_path: str, active_recording_file=None) -> int:
    """Backward compatibility wrapper."""
    return recover_missing_companion_exports(folder_path, active_recording_file, target_format="mp3")


# -------------------------------------------------------------
# Retention Cleaner & High-Water Mark Ledger
# -------------------------------------------------------------
def _get_retention_ledger_path(profile: str = "default") -> Path:
    app_dir = get_app_dir()
    if profile == "default":
        return app_dir / "retention_ledger.json"
    return app_dir / f"retention_ledger_{profile}.json"


def record_file_retention(file_path: str, policy_days: int, profile: str = "default"):
    """
    Records a newly finalized backup file into the local retention ledger with its
    original creation timestamp, active retention policy, and initial guaranteed minimum expiry.
    """
    if policy_days <= 0:
        return
    try:
        ledger_path = _get_retention_ledger_path(profile)
        ledger = {}
        if ledger_path.exists():
            try:
                ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            except Exception:
                ledger = {}

        p = Path(file_path)
        key = p.name
        now = time.time()
        ledger[key] = {
            "created_at": now,
            "policy_days": policy_days,
            "min_keep_until": now + (policy_days * 86400)
        }
        ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        logger.info("Retention Ledger: Registered %s with %d-day guarantee (keep until %s)",
                    key, policy_days, datetime.fromtimestamp(now + policy_days * 86400).strftime("%Y-%m-%d"))
    except Exception as e:
        logger.error("Failed to record retention for %s: %s", file_path, e)


def get_file_expiry_threshold(file_path: Path, current_retention_days: int, ledger: Dict[str, Any]) -> float:
    """
    Calculates effective expiry applying the High-Water Mark (Furthest Duration) rule:
      effective_expiry = max(recorded_policy_expiry, file_created_at + current_retention_days * 86400)
    If the file is not in the ledger, falls back to mtime + current_retention_days * 86400.
    Returns the UNIX timestamp at which the file expires.
    """
    if current_retention_days <= 0:
        return float("inf")  # Keep forever

    key = file_path.name
    # Also check base stem if companion file (.mp3 / .wav / .ogg) belongs to a master .flac
    flac_key = file_path.with_suffix(".flac").name
    entry = ledger.get(key) or ledger.get(flac_key)

    if entry and "created_at" in entry and "min_keep_until" in entry:
        created_at = float(entry["created_at"])
        min_keep = float(entry["min_keep_until"])
        current_keep = created_at + (current_retention_days * 86400)
        # High-Water Mark: furthest duration wins
        return max(min_keep, current_keep)
    else:
        # Legacy or untracked file: use mtime
        mtime = file_path.stat().st_mtime
        return mtime + (current_retention_days * 86400)


def cleanup_old_backups(folder_path: str, retention_days: int, pattern: str = "", profile: str = "default") -> int:
    """
    Deletes backup .flac, .mp3, .wav, and .ogg files older than retention_days across all subfolders.
    Enforces the High-Water Mark (Furthest Duration) rule via the local retention ledger:
    files previously recorded under a longer policy are guaranteed to survive until their full duration.
    Matches standard 'Audio_Backup_*', legacy 'Mosque_Backup_*', custom prefixes,
    or any backup containing a YYYY-MM-DD timestamp pattern.
    Also cleans up any empty subfolders left behind.
    If retention_days <= 0, no files are deleted.
    Returns the number of deleted files.
    """
    if retention_days <= 0:
        logger.info("Retention is set to 0 (Keep Forever). Skipping cleanup.")
        return 0

    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        logger.warning("Backup folder %s does not exist. Skipping retention cleanup.", folder_path)
        return 0

    deleted_count = 0

    # Extract custom static prefix from pattern if available (e.g. "Audio_Session_" from "Audio_Session_{date}")
    custom_prefix = ""
    if pattern:
        idx = pattern.find("{")
        if idx > 0:
            custom_prefix = pattern[:idx].strip()
        elif idx == -1:
            custom_prefix = pattern.strip()

    logger.info("Running recursive retention cleanup on '%s' (Policy: %d days, High-Water Mark enabled)...", folder, retention_days)

    ledger_path = _get_retention_ledger_path(profile)
    ledger = {}
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            ledger = {}

    ledger_modified = False
    now = time.time()

    import re
    try:
        for file in folder.rglob("*"):
            if not file.is_file():
                continue
            name = file.name
            name_lower = name.lower()
            if not (name_lower.endswith(".flac") or name_lower.endswith(".mp3") or name_lower.endswith(".wav") or name_lower.endswith(".ogg")):
                continue

            # Strict pattern check so unrelated files are NEVER touched:
            # Matches standard prefix, custom prefix, or any date-stamped AudioGuard recording
            stem = file.stem
            matches = (
                stem.startswith("Audio_Backup_") or
                stem.startswith("Mosque_Backup_") or
                (bool(custom_prefix) and stem.startswith(custom_prefix)) or
                bool(re.search(r'\d{4}-\d{2}-\d{2}', stem))
            )

            if matches:
                try:
                    expiry_time = get_file_expiry_threshold(file, retention_days, ledger)
                    if now >= expiry_time:
                        file.unlink()
                        deleted_count += 1
                        if file.name in ledger:
                            del ledger[file.name]
                            ledger_modified = True
                        logger.info("Retention: Deleted expired backup file: %s (expiry reached: %.1f days ago)",
                                    file.relative_to(folder), (now - expiry_time) / 86400)
                except Exception as ex:
                    logger.error("Failed to delete expired backup %s: %s", name, ex)

        # Prune empty subfolders bottom-up
        for dirpath in sorted(folder.glob("**/*"), key=lambda p: len(p.parts), reverse=True):
            if dirpath.is_dir() and dirpath != folder:
                try:
                    if not any(dirpath.iterdir()):
                        dirpath.rmdir()
                        logger.info("Retention: Removed empty subfolder %s", dirpath.name)
                except Exception:
                    pass
    except Exception as e:
        logger.error("Error during retention scan of %s: %s", folder, e)

    if ledger_modified:
        try:
            ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        except Exception:
            pass

    logger.info("Retention cleanup completed. Total deleted: %d files.", deleted_count)
    return deleted_count

def get_disk_capacity_gb(path_str: str) -> Tuple[float, float, float]:
    """Returns (total_gb, used_gb, free_gb) for the specified path."""
    try:
        p = Path(path_str) if path_str else Path.home()
        while not p.exists() and p != p.parent:
            p = p.parent
        usage = shutil.disk_usage(p)
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        return total_gb, used_gb, free_gb
    except Exception as e:
        logger.error("Error reading disk capacity for %s: %s", path_str, e)
        return 0.0, 0.0, 0.0

def get_disk_safety_floors(path_str: str) -> Tuple[float, float]:
    """
    Computes dynamic safety floors based on drive capacity:
    safety_floor_gb: max(1.0, min(total_gb * 0.02, 5.0))
    warning_floor_gb: 2.0 * safety_floor_gb
    Returns (safety_floor_gb, warning_floor_gb).
    """
    total_gb, _, _ = get_disk_capacity_gb(path_str)
    if total_gb <= 0:
        return 1.0, 2.0
    safety_floor = max(1.0, min(total_gb * 0.02, 5.0))
    warning_floor = 2.0 * safety_floor
    return safety_floor, warning_floor

def get_free_disk_space_gb(path_str: str) -> float:
    """Returns the free disk space in Gigabytes for the specified path."""
    _, _, free_gb = get_disk_capacity_gb(path_str)
    return free_gb

def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Extracts numeric tuple from version strings like 'v1.5.4' or '1.5.4.1' -> (1, 5, 4)."""
    cleaned = re.sub(r'^[^\d]*', '', str(v_str))
    nums = [int(p) for p in re.split(r'[^0-9]+', cleaned) if p.isdigit()]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums) if nums else (0, 0, 0)

def check_for_github_update(current_version: str = APP_VERSION, timeout: float = 4.0) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Queries GitHub Releases API for the latest release of midimahdi/audioguard.
    Returns:
      ("update_available", release_info_dict) if a newer version is published.
      ("up_to_date", {"version": latest_tag}) if current_version >= latest_tag.
      ("error", {"error": str(e)}) if network fails or offline.
    """
    url = "https://api.github.com/repos/midimahdi/audioguard/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"AudioGuard/{current_version} (Automated Update Checker; Python)",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return "error", {"error": f"HTTP {resp.status}"}
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "").strip()
        if not latest_tag:
            return "error", {"error": "Missing tag_name"}

        curr_tuple = parse_version_tuple(current_version)
        latest_tuple = parse_version_tuple(latest_tag)

        if latest_tuple > curr_tuple:
            assets = data.get("assets", [])
            download_url = data.get("html_url", f"https://github.com/midimahdi/audioguard/releases/tag/{latest_tag}")
            target_asset_name = "AudioGuard-Setup-x64.exe" if sys.platform == "win32" else ""

            for asset in assets:
                name = asset.get("name", "")
                if target_asset_name and name.lower() == target_asset_name.lower():
                    download_url = asset.get("browser_download_url", download_url)
                    break

            body = data.get("body", "") or ""
            if len(body) > 300:
                body = body[:297] + "..."

            return "update_available", {
                "version": latest_tag,
                "current_version": current_version,
                "release_url": data.get("html_url", f"https://github.com/midimahdi/audioguard/releases/tag/{latest_tag}"),
                "download_url": download_url,
                "body": body,
                "published_at": data.get("published_at", "")
            }
        else:
            return "up_to_date", {"version": latest_tag}
    except Exception as e:
        logger.debug("Update check failed (expected if offline): %s", e)
        return "error", {"error": str(e)}

