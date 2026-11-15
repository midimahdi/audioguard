"""
AudioGuard - Configuration, Persistence, Startup & Retention Manager
"""

import os
import sys
import json
import shutil
import logging
import time
from pathlib import Path

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

def setup_logging():
    """Initializes logging to both app.log and stdout."""
    app_dir = get_app_dir()
    log_file = app_dir / "app.log"
    
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
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
    "input_device_name": "",
    "input_host_api": "",
    "monitor_device_name": "",
    "mono_sum": True,
    "schedule_start": "18:00",
    "schedule_end": "21:00",
    "schedule_slots": [{"start": "18:00", "end": "21:00"}],
    "schedule_enabled": True,
    "backup_folder": "",
    "filename_pattern": "Audio_Backup_{date}_{time}",
    "auto_export_mp3": True,
    "retention_days": 30,
    "auto_start_on_boot": True,
    "monitoring_enabled": False
}

def format_recording_filename(pattern: str, is_manual: bool = False, dt=None) -> str:
    """
    Evaluates a user-defined filename pattern into a clean, sanitized Windows-compatible .flac filename.
    Supported tokens: {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}
    """
    from datetime import datetime
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

    replacements = {
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
    def __init__(self):
        self.app_dir = get_app_dir()
        self.config_path = self.app_dir / "config.json"
        self.data = dict(DEFAULT_CONFIG)
        if not self.data["backup_folder"]:
            self.data["backup_folder"] = get_default_backup_folder()
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

def _get_macos_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.mahdi.audioguard.plist"

def set_macos_startup(enabled: bool) -> bool:
    """Enables or disables auto-start on macOS boot via LaunchAgent plist with --minimized flag."""
    plist_path = _get_macos_launch_agent_path()
    try:
        if enabled:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            if getattr(sys, "frozen", False):
                exec_target = sys.executable
                args_xml = f"        <string>{exec_target}</string>\n        <string>--minimized</string>"
            else:
                exec_target = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                args_xml = f"        <string>{exec_target}</string>\n        <string>{script_path}</string>\n        <string>--minimized</string>"

            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mahdi.audioguard</string>
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
            logger.info("macOS Startup LaunchAgent enabled: %s", plist_path)
        else:
            if plist_path.exists():
                plist_path.unlink()
                logger.info("macOS Startup LaunchAgent disabled: %s", plist_path)
        return True
    except Exception as e:
        logger.error("Failed to update macOS LaunchAgent: %s", e)
        return False

def is_macos_startup_enabled() -> bool:
    """Checks whether macOS LaunchAgent exists."""
    return _get_macos_launch_agent_path().exists()

def set_windows_startup(enabled: bool) -> bool:
    """Enables or disables auto-start on Windows boot via HKCU\\...\\Run with --minimized flag."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
        # Always clean up legacy key if present
        try:
            winreg.DeleteValue(key, OLD_APP_REG_NAME)
        except FileNotFoundError:
            pass

        if enabled:
            # Determine executable path and include --minimized flag so it starts in system tray
            if getattr(sys, "frozen", False):
                cmd_line = f'"{sys.executable}" --minimized'
            else:
                cmd_line = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}" --minimized'
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd_line)
            logger.info("Windows Startup enabled with --minimized: %s", cmd_line)
        else:
            try:
                winreg.DeleteValue(key, APP_REG_NAME)
                logger.info("Windows Startup disabled")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error("Failed to update Windows Run registry key: %s", e)
        return False

def is_windows_startup_enabled() -> bool:
    """Checks whether the application is registered to start on Windows boot."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception as e:
        logger.error("Error reading Windows Run registry key: %s", e)
        return False

def set_autostart(enabled: bool) -> bool:
    """Cross-platform startup registration (Windows Registry or macOS LaunchAgent)."""
    if sys.platform == "win32":
        return set_windows_startup(enabled)
    elif sys.platform == "darwin":
        return set_macos_startup(enabled)
    return False

def is_autostart_enabled() -> bool:
    """Cross-platform check for startup registration."""
    if sys.platform == "win32":
        return is_windows_startup_enabled()
    elif sys.platform == "darwin":
        return is_macos_startup_enabled()
    return False


# -------------------------------------------------------------
# Single-Instance Lock
# -------------------------------------------------------------
class SingleInstanceLock:
    """Ensures only one instance of AudioGuard runs at a time."""
    def __init__(self, lock_name="Local\\AudioGuard_SingleInstance_Mutex"):
        self.lock_name = lock_name
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
                    logger.warning("Another instance of AudioGuard is already running (Windows Mutex).")
                    return False
                if self.mutex:
                    self.acquired = True
                    return True
            except Exception as e:
                logger.warning("Failed to create Windows Mutex, falling back to socket lock: %s", e)

        # Fallback cross-platform socket lock on 127.0.0.1:54982
        try:
            import socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(("127.0.0.1", 54982))
            self.sock.listen(1)
            self.acquired = True
            return True
        except (socket.error, OSError):
            logger.warning("Another instance of AudioGuard is already running (Socket Lock :54982).")
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
# MP3 Conversion & Power-Cut Recovery
# -------------------------------------------------------------
def convert_flac_to_mp3(flac_path: str, mp3_path=None) -> bool:
    """
    Converts a FLAC file to MP3 in a memory-safe, stream-friendly way.
    Handles both clean recordings and power-cut truncated FLAC files flawlessly.
    """
    import soundfile as sf

    flac_p = Path(flac_path)
    if not flac_p.exists():
        return False

    if mp3_path is None:
        mp3_p = flac_p.with_suffix(".mp3")
    else:
        mp3_p = Path(mp3_path)

    # If MP3 already exists and is not empty (> 1 KB), consider it done
    if mp3_p.exists() and mp3_p.stat().st_size > 1024:
        return True

    temp_mp3 = mp3_p.with_suffix(".mp3.tmp")

    try:
        with sf.SoundFile(str(flac_p), mode="r") as src:
            with sf.SoundFile(str(temp_mp3), mode="w", samplerate=src.samplerate, channels=src.channels, format="MP3") as dst:
                chunk_size = 8192
                while True:
                    try:
                        data = src.read(chunk_size, dtype="float32")
                        if len(data) == 0:
                            break
                        dst.write(data)
                    except Exception:
                        # Reached truncated power-loss EOF cleanly
                        break

        # Atomically replace final file
        if temp_mp3.exists() and temp_mp3.stat().st_size > 1024:
            temp_mp3.replace(mp3_p)
            logger.info("FLAC to MP3 conversion complete: %s -> %s", flac_p.name, mp3_p.name)
            return True
        else:
            if temp_mp3.exists():
                temp_mp3.unlink()
            return False
    except Exception as e:
        logger.error("Failed to convert %s to MP3: %s", flac_path, e)
        if temp_mp3.exists():
            try:
                temp_mp3.unlink()
            except Exception:
                pass
        return False


def recover_missing_mp3_exports(folder_path: str, active_recording_file=None) -> int:
    """
    Scans the backup directory for any .flac files that do not have a matching .mp3 file.
    Converts them in order (oldest to newest), ensuring power-cut recordings get converted on boot.
    Returns the count of successfully recovered/converted files.
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return 0

    active_p = Path(active_recording_file).resolve() if active_recording_file else None
    recovered = 0

    try:
        flac_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".flac"]
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

            mp3_companion = f.with_suffix(".mp3")
            if not mp3_companion.exists() or mp3_companion.stat().st_size < 1024:
                logger.info("Power-cut recovery / Auto-export: Converting missing MP3 for %s...", f.name)
                res = convert_flac_to_mp3(str(f))
                if res:
                    recovered += 1
    except Exception as e:
        logger.error("Error during MP3 recovery scan of %s: %s", folder, e)

    return recovered


# -------------------------------------------------------------
# Retention Cleaner & Disk Space
# -------------------------------------------------------------
def cleanup_old_backups(folder_path: str, retention_days: int, pattern: str = "") -> int:
    """
    Deletes backup .flac and .mp3 files older than retention_days.
    Matches standard 'Audio_Backup_*', legacy 'Mosque_Backup_*',
    or files matching the user's custom naming prefix.
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

    cutoff_time = time.time() - (retention_days * 86400)
    deleted_count = 0

    # Extract custom static prefix from pattern if available (e.g. "Mosque_Lesson_" from "Mosque_Lesson_{date}")
    custom_prefix = ""
    if pattern:
        idx = pattern.find("{")
        if idx > 0:
            custom_prefix = pattern[:idx].strip()
        elif idx == -1:
            custom_prefix = pattern.strip()

    logger.info("Running retention cleanup on '%s' (Older than %d days)...", folder, retention_days)

    try:
        for file in folder.iterdir():
            if not file.is_file():
                continue
            name = file.name
            name_lower = name.lower()
            if not (name_lower.endswith(".flac") or name_lower.endswith(".mp3")):
                continue

            # Strict pattern check so unrelated files are NEVER touched
            stem = file.stem
            matches = (
                stem.startswith("Audio_Backup_") or
                stem.startswith("Mosque_Backup_") or
                (bool(custom_prefix) and stem.startswith(custom_prefix))
            )

            if matches:
                try:
                    mtime = file.stat().st_mtime
                    if mtime < cutoff_time:
                        file.unlink()
                        deleted_count += 1
                        logger.info("Retention: Deleted old backup file: %s (age: %.1f days)", name, (time.time() - mtime) / 86400)
                except Exception as ex:
                    logger.error("Failed to delete expired backup %s: %s", name, ex)
    except Exception as e:
        logger.error("Error during retention scan of %s: %s", folder, e)

    logger.info("Retention cleanup completed. Total deleted: %d files.", deleted_count)
    return deleted_count

def get_free_disk_space_gb(path_str: str) -> float:
    """Returns the free disk space in Gigabytes for the specified path."""
    try:
        p = Path(path_str)
        # Find closest existing parent if path doesn't exist yet
        while not p.exists() and p != p.parent:
            p = p.parent
        usage = shutil.disk_usage(p)
        return usage.free / (1024 ** 3)
    except Exception as e:
        logger.error("Error reading disk usage for %s: %s", path_str, e)
        return 0.0
