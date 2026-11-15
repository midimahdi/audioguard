"""
AudioGuard - Robust Lossless Audio Engine
- FLAC 48000 Hz 24-bit (PCM_24)
- 1-Second Continuous Flush + fsync for Zero-Data-Loss Power Cuts
- Always-On Live Input Stream with Real-time Mono-Sum DSP
- Live Peak/RMS dBFS Stereo Level Meter with Clip Detection
- Low-Latency Headphone Monitoring Output Stream
- Device-by-Name Matching & Auto-Reconnect
"""

import os
import sys
import time
import math
import queue
import logging
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger("AudioGuard.AudioEngine")

# Audio Constants
SAMPLE_RATE = 48000
BLOCK_SIZE = 4096       # ~85.3 ms per buffer (approx 11.7 blocks/sec)
CHANNELS = 2
DTYPE = "float32"
SILENCE_THRESHOLD_RMS = 0.000316  # Approx -70 dBFS
CLIP_THRESHOLD = 0.999            # Approx -0.01 dBFS

class AudioEngine:
    def __init__(self, config_manager):
        self.config = config_manager
        
        # Audio stream state
        self.input_stream: Optional[sd.InputStream] = None
        self.monitor_stream: Optional[sd.OutputStream] = None
        self.current_input_device_id: Optional[int] = None
        self.current_monitor_device_id: Optional[int] = None
        self.is_stream_active = False
        self.device_error_state = False
        self.device_error_message = ""
        
        # DSP settings
        self.mono_sum: bool = self.config.get("mono_sum", True)
        self.monitoring_enabled: bool = False  # Always auto-muted on startup for feedback safety
        
        # Metering state (Thread-safe)
        self._levels_lock = threading.Lock()
        self.left_peak_db = -60.0
        self.right_peak_db = -60.0
        self.left_rms_db = -60.0
        self.right_rms_db = -60.0
        self.left_clipped = False
        self.right_clipped = False
        
        # Recording state
        self.is_recording = False
        self.recording_start_time: Optional[float] = None
        self.recording_file_path: Optional[str] = None
        self.is_manual_recording = False
        self._record_queue: queue.Queue = queue.Queue(maxsize=200)
        self._writer_thread: Optional[threading.Thread] = None
        self._stop_writer_event = threading.Event()
        
        # Monitoring queue (small non-blocking queue)
        self._monitor_queue: queue.Queue = queue.Queue(maxsize=10)
        
        # Auto-reconnect watchdog thread
        self._watchdog_thread = threading.Thread(target=self._device_watchdog_worker, daemon=True)
        self._watchdog_thread.start()

        # Low-disk safety state
        self.low_disk_state = False
        self.low_disk_message = ""

        # Voice Activity Tracking
        self._last_voice_time: float = 0.0

    # -------------------------------------------------------------
    # Device Enumeration & Name-Matching
    # -------------------------------------------------------------
    # Hardware Device Enumeration & Matching
    # -------------------------------------------------------------
    @staticmethod
    def get_audio_devices() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Enumerates hardware audio devices, deduplicating multiple host APIs
        (WASAPI, DirectSound, MME, WDM-KS) per physical hardware device.
        Each physical microphone/input or speaker/output appears exactly once.
        Prioritizes Windows WASAPI for lowest latency and bit-perfect audio.
        """
        api_priority = {
            "Windows WASAPI": 1,
            "Windows DirectSound": 2,
            "Core Audio": 1,
            "ALSA": 1,
            "MME": 3,
            "Windows WDM-KS": 4
        }
        virtual_ignore = (
            "microsoft sound mapper",
            "primary sound capture",
            "primary sound driver"
        )

        def deduplicate(is_input: bool) -> List[Dict[str, Any]]:
            grouped: Dict[str, Dict[str, Any]] = {}
            try:
                devices = sd.query_devices()
                hostapis = sd.query_hostapis()
            except Exception as e:
                logger.error("Failed to query audio devices: %s", e)
                return []

            for idx, dev in enumerate(devices):
                ch = dev["max_input_channels"] if is_input else dev["max_output_channels"]
                if ch <= 0:
                    continue
                
                raw_name = dev["name"].strip()
                lower_name = raw_name.lower()
                
                # Skip virtual loopback / OS mapper aliases
                if any(lower_name.startswith(v) for v in virtual_ignore):
                    continue
                
                api_name = hostapis[dev["hostapi"]]["name"] if dev["hostapi"] < len(hostapis) else "Unknown"
                prio = api_priority.get(api_name, 99)

                # Match against existing hardware entries (exact, substring, or first 24 chars)
                matched_key = None
                for key in grouped:
                    if key in lower_name or lower_name in key or key[:24] == lower_name[:24]:
                        matched_key = key
                        break
                
                item = {
                    "id": idx,
                    "name": raw_name,
                    "display_name": raw_name,
                    "hostapi": api_name,
                    "channels": ch,
                    "default_samplerate": dev.get("default_samplerate", 48000),
                    "priority": prio
                }

                if matched_key is None:
                    grouped[lower_name] = item
                else:
                    existing = grouped[matched_key]
                    # Prefer higher priority API (e.g. WASAPI beats DirectSound/MME/WDM-KS)
                    # or longer/more descriptive name when priority is equal
                    if prio < existing["priority"] or (prio == existing["priority"] and len(raw_name) > len(existing["name"])):
                        item["display_name"] = raw_name if len(raw_name) >= len(existing["display_name"]) else existing["display_name"]
                        del grouped[matched_key]
                        grouped[lower_name] = item

            result = list(grouped.values())
            result.sort(key=lambda x: x["display_name"].lower())
            return result

        inputs = deduplicate(is_input=True)
        outputs = deduplicate(is_input=False)
        return inputs, outputs

    def find_device_by_name(self, name_substr: str, is_input: bool = True, hostapi_hint: str = "") -> Optional[int]:
        """
        Finds a device index matching substring and optional host API (e.g. WASAPI).
        Falls back to default system device if not found.
        """
        inputs, outputs = self.get_audio_devices()
        target_list = inputs if is_input else outputs
        
        if not target_list:
            return None
            
        if not name_substr:
            # Return first clean hardware device or system default
            try:
                default_idx = sd.default.device[0 if is_input else 1]
                if default_idx is not None and default_idx >= 0:
                    return default_idx
            except Exception:
                pass
            return target_list[0]["id"]

        name_lower = name_substr.lower().strip()
        hostapi_lower = hostapi_hint.lower().strip()

        # Pass 1: Match both name and hostapi
        if hostapi_lower:
            for dev in target_list:
                if (name_lower in dev["name"].lower() or dev["name"].lower() in name_lower) and hostapi_lower in dev["hostapi"].lower():
                    return dev["id"]

        # Pass 2: Match name only
        for dev in target_list:
            if name_lower in dev["name"].lower() or dev["name"].lower() in name_lower:
                return dev["id"]

        # Pass 3: Return first available clean device
        logger.warning("Device '%s' not found, falling back to: %s", name_substr, target_list[0]["display_name"])
        return target_list[0]["id"]

    # -------------------------------------------------------------
    # Stream Initialization & Reconnection
    # -------------------------------------------------------------
    def start_input_stream(self) -> bool:
        """Starts or restarts the always-on input stream."""
        self.stop_input_stream()
        
        saved_name = self.config.get("input_device_name", "")
        saved_hostapi = self.config.get("input_host_api", "")
        dev_id = self.find_device_by_name(saved_name, is_input=True, hostapi_hint=saved_hostapi)
        
        if dev_id is None:
            self.device_error_state = True
            self.device_error_message = "No audio input device available on system."
            logger.error(self.device_error_message)
            return False

        try:
            dev_info = sd.query_devices(dev_id)
            input_channels = min(2, dev_info["max_input_channels"])
            if input_channels < 1:
                raise ValueError("Selected device has 0 input channels.")
                
            self.current_input_device_id = dev_id
            self.input_stream = sd.InputStream(
                device=dev_id,
                channels=input_channels,
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype=DTYPE,
                callback=self._audio_input_callback
            )
            self.input_stream.start()
            self.is_stream_active = True
            self.device_error_state = False
            self.device_error_message = ""
            logger.info("Always-On Input Stream started on device #%d: '%s' (HostAPI: %s)",
                        dev_id, dev_info["name"], dev_info.get("hostapi", "Unknown"))
            return True
        except Exception as e:
            self.device_error_state = True
            self.device_error_message = f"Audio Input Error: {str(e)}"
            logger.error("Failed to start audio input stream on device #%s: %s", dev_id, e)
            self.input_stream = None
            self.is_stream_active = False
            return False

    def stop_input_stream(self):
        """Stops the input stream cleanly."""
        if self.input_stream:
            try:
                self.input_stream.stop()
                self.input_stream.close()
            except Exception as e:
                logger.debug("Error stopping input stream: %s", e)
            self.input_stream = None
        self.is_stream_active = False

    def start_monitor_stream(self) -> bool:
        """Starts or restarts the headphone monitor output stream."""
        self.stop_monitor_stream()
        if not self.monitoring_enabled:
            return False
            
        saved_name = self.config.get("monitor_device_name", "")
        dev_id = self.find_device_by_name(saved_name, is_input=False)
        
        if dev_id is None:
            logger.warning("No audio output device found for monitoring.")
            return False

        try:
            self.current_monitor_device_id = dev_id
            self.monitor_stream = sd.OutputStream(
                device=dev_id,
                channels=2,
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype=DTYPE,
                callback=self._audio_output_callback
            )
            self.monitor_stream.start()
            logger.info("Monitor Output Stream started on device #%d", dev_id)
            return True
        except Exception as e:
            logger.error("Failed to start monitor stream: %s", e)
            self.monitor_stream = None
            return False

    def stop_monitor_stream(self):
        """Stops the headphone monitor output stream."""
        if self.monitor_stream:
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except Exception as e:
                logger.debug("Error stopping monitor stream: %s", e)
            self.monitor_stream = None

    def set_monitoring(self, enabled: bool):
        """Toggles the headphone monitor stream safely."""
        self.monitoring_enabled = enabled
        if enabled:
            self.start_monitor_stream()
        else:
            self.stop_monitor_stream()

    def set_mono_sum(self, enabled: bool):
        """Toggles the Mono-Sum / Dual Mono real-time DSP mode."""
        self.mono_sum = enabled
        self.config.set("mono_sum", enabled)
        logger.info("DSP Mode switched: %s", "Mono-Sum (Dual Mono)" if enabled else "True Stereo")

    # -------------------------------------------------------------
    # Real-Time Audio Callbacks & DSP
    # -------------------------------------------------------------
    def _audio_input_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """
        Called by PortAudio for every 4096-sample buffer (~85ms).
        Executes DSP, level metering, monitoring queueing, and recording queueing.
        """
        if status:
            logger.debug("PortAudio input callback status: %s", status)

        # Ensure float32 stereo buffer shape (frames, 2)
        if indata.shape[1] == 1:
            buffer = np.repeat(indata, 2, axis=1)
        else:
            buffer = indata.copy()

        # --- Real-Time DSP Pipeline ---
        if self.mono_sum:
            left_rms = np.sqrt(np.mean(buffer[:, 0] ** 2))
            right_rms = np.sqrt(np.mean(buffer[:, 1] ** 2))
            
            # Mosque Mixer Feed Logic:
            # If one channel is dead/silent (< -70 dBFS) while the other has signal,
            # duplicate the active channel to both ears without losing 6 dB of gain.
            if left_rms > SILENCE_THRESHOLD_RMS and right_rms <= SILENCE_THRESHOLD_RMS:
                buffer[:, 1] = buffer[:, 0]
            elif right_rms > SILENCE_THRESHOLD_RMS and left_rms <= SILENCE_THRESHOLD_RMS:
                buffer[:, 0] = buffer[:, 1]
            else:
                # Both channels have signal (or both silent) -> Standard Dual Mono sum
                mono = (buffer[:, 0] + buffer[:, 1]) * 0.5
                buffer[:, 0] = mono
                buffer[:, 1] = mono

        # --- Live dBFS Peak & RMS Level Metering ---
        l_peak = np.max(np.abs(buffer[:, 0]))
        r_peak = np.max(np.abs(buffer[:, 1]))
        l_rms = np.sqrt(np.mean(buffer[:, 0] ** 2))
        r_rms = np.sqrt(np.mean(buffer[:, 1] ** 2))

        # Convert to dBFS (clamped -60.0 dB to 0.0 dB)
        l_peak_db = 20.0 * math.log10(max(float(l_peak), 1e-3))
        r_peak_db = 20.0 * math.log10(max(float(r_peak), 1e-3))
        l_rms_db = 20.0 * math.log10(max(float(l_rms), 1e-3))
        r_rms_db = 20.0 * math.log10(max(float(r_rms), 1e-3))

        with self._levels_lock:
            self.left_peak_db = max(-60.0, min(0.0, l_peak_db))
            self.right_peak_db = max(-60.0, min(0.0, r_peak_db))
            self.left_rms_db = max(-60.0, min(0.0, l_rms_db))
            self.right_rms_db = max(-60.0, min(0.0, r_rms_db))
            
            if l_peak >= CLIP_THRESHOLD:
                self.left_clipped = True
            if r_peak >= CLIP_THRESHOLD:
                self.right_clipped = True

        # --- Voice Activity Detection ---
        # Speech threshold: RMS > -50 dBFS (0.00316) or Peak > -42 dBFS (0.00794)
        if max(l_rms, r_rms) > 0.00316 or max(l_peak, r_peak) > 0.00794:
            self._last_voice_time = time.time()

        # --- Route to Monitor Queue ---
        if self.monitoring_enabled:
            try:
                self._monitor_queue.put_nowait(buffer)
            except queue.Full:
                try:
                    self._monitor_queue.get_nowait()
                    self._monitor_queue.put_nowait(buffer)
                except Exception:
                    pass

        # --- Route to Recording Queue ---
        if self.is_recording:
            try:
                self._record_queue.put_nowait(buffer)
            except queue.Full:
                logger.error("Recording queue full! Audio frame dropped.")

    def _audio_output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """Called by PortAudio to output audio to headphones."""
        try:
            data = self._monitor_queue.get_nowait()
            if len(data) == len(outdata):
                outdata[:] = data
            else:
                outdata.fill(0)
        except queue.Empty:
            outdata.fill(0)

    def get_levels(self) -> Tuple[float, float, float, float, bool, bool]:
        """Returns (l_peak_db, r_peak_db, l_rms_db, r_rms_db, l_clipped, r_clipped)."""
        with self._levels_lock:
            return (
                self.left_peak_db,
                self.right_peak_db,
                self.left_rms_db,
                self.right_rms_db,
                self.left_clipped,
                self.right_clipped
            )

    def reset_clip_indicators(self):
        """Resets persistent CLIP flags."""
        with self._levels_lock:
            self.left_clipped = False
            self.right_clipped = False

    def is_voice_active(self, within_seconds: float = 60.0) -> bool:
        """
        Returns True if voice activity (above -50 dBFS) was detected within the last X seconds.
        Used by the scheduler for smart overtime extension.
        """
        if self._last_voice_time <= 0.0:
            return False
        return (time.time() - self._last_voice_time) < within_seconds

    # -------------------------------------------------------------
    # Cross-Platform Sleep Prevention (Windows SetThreadExecutionState & macOS caffeinate)
    # -------------------------------------------------------------
    _caffeinate_proc: Optional[subprocess.Popen] = None

    @classmethod
    def _set_sleep_prevention(cls, enable: bool):
        """
        Prevents OS from entering sleep or idle suspend while recording.
        - Windows: Uses SetThreadExecutionState with ES_SYSTEM_REQUIRED and ES_AWAYMODE_REQUIRED.
        - macOS: Uses /usr/bin/caffeinate -dimu.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                ES_CONTINUOUS = 0x80000000
                ES_SYSTEM_REQUIRED = 0x00000001
                ES_AWAYMODE_REQUIRED = 0x00000040

                if enable:
                    res = ctypes.windll.kernel32.SetThreadExecutionState(
                        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                    )
                    if res == 0:
                        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                    logger.info("Windows Sleep Prevention: ACTIVE (ES_SYSTEM_REQUIRED)")
                else:
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    logger.info("Windows Sleep Prevention: RELEASED (Normal idle restored)")
            except Exception as e:
                logger.warning("Failed to configure Windows thread execution state: %s", e)
        elif sys.platform == "darwin":
            if enable:
                try:
                    if cls._caffeinate_proc is None or cls._caffeinate_proc.poll() is not None:
                        cls._caffeinate_proc = subprocess.Popen(
                            ["/usr/bin/caffeinate", "-d", "-i", "-m", "-u"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        logger.info("macOS Sleep Prevention: ACTIVE (caffeinate PID %s)", cls._caffeinate_proc.pid)
                except Exception as e:
                    logger.warning("Failed to launch macOS caffeinate: %s", e)
            else:
                try:
                    if cls._caffeinate_proc is not None:
                        cls._caffeinate_proc.terminate()
                        cls._caffeinate_proc = None
                        logger.info("macOS Sleep Prevention: RELEASED")
                except Exception as e:
                    logger.warning("Failed to terminate macOS caffeinate: %s", e)

    # -------------------------------------------------------------
    # Recording Session Control (Single-File Crash-Proof FLAC)
    # -------------------------------------------------------------
    def start_recording(self, manual: bool = False, is_manual: Optional[bool] = None) -> Optional[str]:
        """
        Starts a continuous recording session to FLAC.
        Returns the created file path on success, or None on failure.
        """
        if is_manual is not None:
            manual = is_manual
        if self.is_recording:
            logger.warning("Recording is already in progress.")
            return self.recording_file_path

        from config_manager import (
            get_free_disk_space_gb, cleanup_old_backups,
            format_recording_filename, get_default_backup_folder,
            get_recording_subfolder
        )

        backup_folder_str = self.config.get("backup_folder", "")
        backup_folder = Path(backup_folder_str) if backup_folder_str else Path(get_default_backup_folder())
        try:
            backup_folder.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = backup_folder / ".write_test"
            test_file.touch()
            test_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Selected backup directory '%s' is inaccessible (%s). Falling back to safe local storage...", backup_folder, e)
            backup_folder = Path(get_default_backup_folder())
            backup_folder.mkdir(parents=True, exist_ok=True)

        pattern = self.config.get("filename_pattern", "Audio_Backup_{date}_{time}")
        folder_grouping = self.config.get("folder_grouping", "monthly")
        retention_days = int(self.config.get("retention_days", 30))

        # Low-Disk Space Pre-Flight Check
        free_gb = get_free_disk_space_gb(str(backup_folder))
        if free_gb < 1.0:
            logger.warning("Low disk space before recording (%.2f GB free). Running retention cleanup...", free_gb)
            try:
                cleanup_old_backups(str(backup_folder), retention_days, pattern=pattern)
                free_gb = get_free_disk_space_gb(str(backup_folder))
            except Exception as ex:
                logger.error("Retention cleanup error: %s", ex)

        if free_gb < 0.5:
            self.low_disk_state = True
            self.low_disk_message = f"Disk Space Critical ({free_gb * 1024:.0f} MB free). Recording blocked."
            logger.error("CANNOT START RECORDING: %s", self.low_disk_message)
            return None

        # Reset low disk state when space is healthy
        self.low_disk_state = False
        self.low_disk_message = ""

        now = datetime.now()
        # Resolve target directory based on grouping (e.g. C:\AudioBackups\2026-11\)
        target_dir = get_recording_subfolder(str(backup_folder), folder_grouping=folder_grouping, dt=now)

        candidate_name = format_recording_filename(pattern, is_manual=manual, dt=now)
        target_path = target_dir / candidate_name

        # Collision avoidance: append _1, _2 if file with exact name already exists
        if target_path.exists():
            stem = target_path.stem
            counter = 1
            while (target_dir / f"{stem}_{counter}.flac").exists():
                counter += 1
            target_path = target_dir / f"{stem}_{counter}.flac"

        file_path = str(target_path)

        # Clear recording queue
        while not self._record_queue.empty():
            try:
                self._record_queue.get_nowait()
            except Exception:
                break

        self.recording_file_path = file_path
        self.is_manual_recording = manual
        self.recording_start_time = time.time()
        self._stop_writer_event.clear()

        # Start dedicated FLAC writer thread
        self._writer_thread = threading.Thread(
            target=self._flac_writer_worker,
            args=(file_path,),
            daemon=True
        )
        self._writer_thread.start()

        self.is_recording = True
        self._set_sleep_prevention(True)
        logger.info("RECORDING STARTED -> File: %s (Manual: %s)", file_path, manual)
        return file_path

    def stop_recording(self) -> Optional[str]:
        """Stops the active recording session and cleanly finalizes the FLAC file."""
        if not self.is_recording:
            return None

        logger.info("Stopping recording session...")
        self.is_recording = False
        self._stop_writer_event.set()

        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=3.0)
            self._writer_thread = None

        self._set_sleep_prevention(False)
        finished_path = self.recording_file_path
        elapsed = time.time() - (self.recording_start_time or time.time())
        self.recording_file_path = None
        self.recording_start_time = None

        logger.info("RECORDING FINISHED -> Duration: %.1fs, File: %s", elapsed, finished_path)
        
        # Trigger background MP3 conversion if enabled
        if finished_path and self.config.get("auto_export_mp3", True):
            from config_manager import convert_flac_to_mp3
            def _async_convert(src):
                logger.info("Auto-exporting MP3 copy for %s...", Path(src).name)
                convert_flac_to_mp3(src)

            t = threading.Thread(target=_async_convert, args=(finished_path,), daemon=True)
            t.start()

        # Trigger automatic retention cleanup post-recording
        try:
            from config_manager import cleanup_old_backups
            retention_days = int(self.config.get("retention_days", 30))
            folder = self.config.get("backup_folder", "")
            pattern = self.config.get("filename_pattern", "")
            cleanup_old_backups(folder, retention_days, pattern=pattern)
        except Exception as e:
            logger.error("Failed to run post-recording retention cleanup: %s", e)

        return finished_path

    def _flac_writer_worker(self, file_path: str):
        """
        Dedicated FLAC disk writer thread.
        CRITICAL POWER-LOSS SAFETY:
        Writes 48kHz 24-bit FLAC blocks and executes sf_file.flush()
        followed by os.fsync() every 1.0 second.
        Monitors free disk space every 30s to prevent ENOSPC crashes.
        """
        logger.info("FLAC Writer thread started for '%s'", file_path)
        sf_file = None
        raw_file = None
        backup_folder_str = str(Path(file_path).parent)
        
        try:
            from config_manager import get_free_disk_space_gb, cleanup_old_backups
            
            raw_file = open(file_path, "wb")
            sf_file = sf.SoundFile(
                raw_file,
                mode="w",
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                format="FLAC",
                subtype="PCM_24"
            )
            
            last_flush_time = time.time()
            last_disk_check_time = time.time()
            blocks_since_flush = 0

            while not self._stop_writer_event.is_set():
                try:
                    block = self._record_queue.get(timeout=0.25)
                except queue.Empty:
                    block = None

                if block is not None:
                    sf_file.write(block)
                    blocks_since_flush += 1

                now = time.time()
                # Continuous flush & fsync every 1.0s or ~12 blocks
                if (now - last_flush_time >= 1.0) or (blocks_since_flush >= 12):
                    sf_file.flush()
                    try:
                        raw_file.flush()
                        os.fsync(raw_file.fileno())
                    except Exception as fsync_err:
                        logger.debug("fsync warning: %s", fsync_err)
                    last_flush_time = now
                    blocks_since_flush = 0

                # Periodic disk health check every 30 seconds during active recording
                if now - last_disk_check_time >= 30.0:
                    last_disk_check_time = now
                    free_gb = get_free_disk_space_gb(backup_folder_str)
                    if free_gb < 1.0:
                        logger.warning("Low disk space mid-recording (%.2f GB). Triggering retention scan...", free_gb)
                        try:
                            retention_days = int(self.config.get("retention_days", 30))
                            cleanup_old_backups(backup_folder_str, retention_days)
                            free_gb = get_free_disk_space_gb(backup_folder_str)
                        except Exception:
                            pass
                    if free_gb < 0.5:
                        logger.critical("EMERGENCY: Disk space dropped below 500 MB (%.2f GB). Finalizing recording cleanly.", free_gb)
                        self.low_disk_state = True
                        self.low_disk_message = f"Recording stopped automatically: Low disk space (< 500 MB)."
                        break

            # Drain any remaining frames left in the queue before exit
            while not self._record_queue.empty():
                try:
                    block = self._record_queue.get_nowait()
                    sf_file.write(block)
                except queue.Empty:
                    break

            sf_file.flush()
            try:
                raw_file.flush()
                os.fsync(raw_file.fileno())
            except Exception:
                pass

        except Exception as e:
            logger.critical("FLAC Writer encountered an unhandled exception: %s", e, exc_info=True)
        finally:
            if sf_file is not None:
                try:
                    sf_file.close()
                except Exception:
                    pass
            if raw_file is not None:
                try:
                    raw_file.close()
                except Exception:
                    pass
            if self.low_disk_state:
                self.is_recording = False
                self._set_sleep_prevention(False)
                logger.warning("Low-disk emergency stop finalized safely for '%s'", file_path)
            logger.info("FLAC Writer worker finished cleanly for '%s'", file_path)

    # -------------------------------------------------------------
    # Device Disconnect Watchdog
    # -------------------------------------------------------------
    def _device_watchdog_worker(self):
        """Monitors stream health and retries disconnected devices every 5 seconds."""
        while True:
            time.sleep(5.0)
            if not self.is_stream_active or self.device_error_state:
                logger.info("Device Watchdog: Attempting audio stream reconnect...")
                success = self.start_input_stream()
                if success:
                    logger.info("Device Watchdog: Successfully reconnected audio input!")
