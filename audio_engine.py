"""
AudioGuard - Robust Lossless Audio Engine
- FLAC 48000 Hz 24-bit (PCM_24)
- 1-Second Continuous Flush + fsync for Zero-Data-Loss Power Cuts
- Always-On Live Input Stream with Real-time Mono-Sum DSP
- Live Peak/RMS dBFS Stereo Level Meter with Clip Detection
- Low-Latency Headphone Monitoring Output Stream
- Device-by-Name Matching & Auto-Reconnect
"""

from __future__ import annotations
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

# Known virtual/dummy devices that must be deprioritized during auto-fallback
VIRTUAL_DUMMY_KEYWORDS = (
    "camo",
    "steam streaming",
    "virtual cable",
    "vb-audio",
    "droidcam",
    "iriun",
    "obs-camera",
    "obs virtual",
    "ndi audio"
)

def is_virtual_dummy(name: str) -> bool:
    """Returns True if the device name indicates a dummy or third-party virtual bridge."""
    if not name:
        return False
    n = name.lower()
    return any(kw in n for kw in VIRTUAL_DUMMY_KEYWORDS)

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

        # Stream Sample Rates (Dynamic adaptive resampling)
        self.input_stream_rate: int = SAMPLE_RATE
        self.secondary_stream_rate: int = SAMPLE_RATE
        
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
        
        # Secondary Audio Stream State (Track 2 - Desktop Loopback / Second Mic)
        self.secondary_input_stream: Optional[sd.InputStream] = None
        self.current_secondary_device_id: Optional[int] = None
        self.is_secondary_stream_active: bool = False
        self.secondary_device_error_state: bool = False
        self.secondary_device_error_message: str = ""

        # Secondary Metering State (Thread-safe)
        self.sec_left_peak_db: float = -60.0
        self.sec_right_peak_db: float = -60.0
        self.sec_left_rms_db: float = -60.0
        self.sec_right_rms_db: float = -60.0
        self.sec_left_clipped: bool = False
        self.sec_right_clipped: bool = False

        # Recording state
        self.is_recording = False
        self.recording_start_time: Optional[float] = None
        self.recording_file_path: Optional[str] = None
        self.recording_secondary_file_path: Optional[str] = None
        self.is_manual_recording = False
        self._record_queue: queue.Queue = queue.Queue(maxsize=200)
        self._secondary_record_queue: queue.Queue = queue.Queue(maxsize=200)
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

    @staticmethod
    def get_input_devices() -> List[Dict[str, Any]]:
        """Returns list of clean hardware input devices."""
        inputs, _ = AudioEngine.get_audio_devices()
        return inputs

    @staticmethod
    def get_unified_audio_sources() -> List[Dict[str, Any]]:
        """
        Enumerates all available audio sources into a single unified list:
        - Physical & virtual hardware inputs (Microphones, Mixers, Camo, etc.)
        - Desktop Audio (Loopback from System / Speakers)
        """
        inputs, outputs = AudioEngine.get_audio_devices()
        sources: List[Dict[str, Any]] = []

        loopback_keywords = (
            "blackhole", "soundflower", "loopback", "stereo mix",
            "wave out", "what u hear", "voicemeeter", "wavelink"
        )

        # 1. Add all physical & virtual inputs
        for dev in inputs:
            d_copy = dict(dev)
            lower = d_copy["name"].lower()
            if any(k in lower for k in loopback_keywords):
                d_copy["display_name"] = f"Desktop Audio ({d_copy['name']})"
                d_copy["is_desktop_audio"] = True
            sources.append(d_copy)

        # 2. Check if desktop audio is already represented
        has_loopback = any(d.get("is_desktop_audio", False) for d in sources)

        import platform
        os_name = platform.system()

        if not has_loopback:
            if os_name == "Darwin":
                # macOS without virtual loopback driver installed
                sources.append({
                    "id": -99,
                    "name": "Desktop Audio (Setup BlackHole...)",
                    "display_name": "Desktop Audio (Setup BlackHole...)",
                    "hostapi": "Core Audio",
                    "channels": 2,
                    "default_samplerate": 48000,
                    "is_desktop_audio": True,
                    "is_setup_needed": True
                })
            elif os_name == "Windows":
                # Windows WASAPI loopback on default output / speakers
                out_id = None
                try:
                    out_id = sd.default.device[1]
                except Exception:
                    pass
                if out_id is None and outputs:
                    out_id = outputs[0]["id"]
                
                sources.append({
                    "id": out_id if out_id is not None else -100,
                    "name": "Desktop Audio (System Output)",
                    "display_name": "Desktop Audio (System Output)",
                    "hostapi": "Windows WASAPI",
                    "channels": 2,
                    "default_samplerate": 48000,
                    "is_desktop_audio": True,
                    "is_wasapi_loopback": True
                })
            else:
                sources.append({
                    "id": -101,
                    "name": "Desktop Audio (Monitor)",
                    "display_name": "Desktop Audio (Monitor)",
                    "hostapi": "ALSA",
                    "channels": 2,
                    "default_samplerate": 48000,
                    "is_desktop_audio": True
                })

        return sources

    @staticmethod
    def get_secondary_audio_devices(source_type: str = "desktop") -> List[Dict[str, Any]]:
        """Backwards-compatible wrapper returning unified audio sources."""
        return AudioEngine.get_unified_audio_sources()

    def find_source_by_name(self, name_substr: str, hostapi_hint: str = "") -> Optional[Dict[str, Any]]:
        """
        Finds a unified source entry matching name or substring.
        Falls back to OS default recording device and filters out dummy virtual drivers.
        """
        sources = self.get_unified_audio_sources()
        if not sources:
            return None

        name_lower = name_substr.lower().strip() if name_substr else ""
        hostapi_lower = hostapi_hint.lower().strip() if hostapi_hint else ""

        # Pass 1: exact / substring match on name or display_name and hostapi
        if name_lower and hostapi_lower:
            for s in sources:
                s_name = s["name"].lower()
                s_disp = s.get("display_name", "").lower()
                if (name_lower in s_name or s_name in name_lower or name_lower in s_disp or s_disp in name_lower) and hostapi_lower in s.get("hostapi", "").lower():
                    return s

        # Pass 2: match on name or display_name only
        if name_lower:
            for s in sources:
                s_name = s["name"].lower()
                s_disp = s.get("display_name", "").lower()
                if name_lower in s_name or s_name in name_lower or name_lower in s_disp or s_disp in name_lower:
                    return s

        # Pass 3: Fallback to OS Default Recording Device (filtering virtual dummies)
        try:
            default_in_idx = sd.default.device[0]
            if default_in_idx is not None and default_in_idx >= 0:
                for s in sources:
                    if s.get("id") == default_in_idx and not s.get("is_setup_needed", False):
                        if not is_virtual_dummy(s.get("name", "")):
                            logger.info("Device fallback: selected OS Default Recording Device: %s", s.get("display_name"))
                            return s
        except Exception:
            pass

        # Pass 4: Fallback to first non-virtual physical source
        for s in sources:
            if not s.get("is_setup_needed", False) and not is_virtual_dummy(s.get("name", "")):
                return s

        # Pass 5: Fallback to any non-setup source
        for s in sources:
            if not s.get("is_setup_needed", False):
                return s

        return sources[0]

    def find_device_by_name(self, name_substr: str, is_input: bool = True, hostapi_hint: str = "") -> Optional[int]:
        """
        Finds a device index matching substring and optional host API (e.g. WASAPI).
        Falls back to default system device if not found.
        """
        inputs, outputs = self.get_audio_devices()
        target_list = inputs if is_input else outputs
        
        if not target_list:
            return None
            
        name_lower = name_substr.lower().strip() if name_substr else ""
        hostapi_lower = hostapi_hint.lower().strip() if hostapi_hint else ""

        # Pass 1: Match both name and hostapi
        if name_lower and hostapi_lower:
            for dev in target_list:
                if (name_lower in dev["name"].lower() or dev["name"].lower() in name_lower) and hostapi_lower in dev["hostapi"].lower():
                    return dev["id"]

        # Pass 2: Match name only
        if name_lower:
            for dev in target_list:
                if name_lower in dev["name"].lower() or dev["name"].lower() in name_lower:
                    return dev["id"]

        # Pass 3: System default device
        try:
            default_idx = sd.default.device[0 if is_input else 1]
            if default_idx is not None and default_idx >= 0:
                return default_idx
        except Exception:
            pass

        # Pass 4: First non-virtual clean device
        if is_input:
            for dev in target_list:
                if not is_virtual_dummy(dev.get("name", "")):
                    return dev["id"]

        # Pass 5: Return first available device
        logger.warning("Device '%s' not found, falling back to: %s", name_substr, target_list[0]["display_name"])
        return target_list[0]["id"]

    def rescan_devices(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Forces PortAudio to re-initialize its audio subsystem, discovering newly
        connected USB microphones, mixer inputs, and hardware audio endpoints.
        Safely pauses and restores the background stream if not recording.
        """
        was_active = self.is_stream_active and not self.is_recording
        was_active_sec = self.is_secondary_stream_active and not self.is_recording
        if was_active:
            self.stop_input_stream()
            if self.monitor_stream:
                self.stop_monitor_stream()
        if was_active_sec:
            self.stop_secondary_stream()

        try:
            sd._terminate()
            sd._initialize()
            logger.info("PortAudio audio subsystem re-initialized for hardware rescan.")
        except Exception as e:
            logger.error("PortAudio re-initialization failed: %s", e)

        inputs, outputs = self.get_audio_devices()

        if was_active or self.is_recording:
            self.start_input_stream()
            if self.config.get("monitoring_enabled", False):
                self.start_monitor_stream()
        if was_active_sec or self.config.get("secondary_track_enabled", False):
            self.start_secondary_stream()

        return inputs, outputs

    # -------------------------------------------------------------
    # Stream Initialization & Resilient Connection
    # -------------------------------------------------------------
    def _open_input_stream_resilient(
        self,
        dev_id: int,
        source: Dict[str, Any],
        callback: Any
    ) -> Tuple[Optional[sd.InputStream], int, int, str]:
        """
        Attempts to open an InputStream with 5-tier resilience:
        1. Determines channels and WASAPI loopback settings.
        2. Tries 48,000 Hz primary sample rate.
        3. If sample rate error occurs (-9997), tries device default sample rate
           and standard fallback rates (44100, 96000, 32000, etc.).
        4. On Windows, if WASAPI fails (e.g. OBS locked exclusive mode), searches
           for the same physical hardware name under DirectSound or MME.
        5. If still failing, attempts fallback to the OS default recording device.
        Returns: (stream, actual_device_id, actual_sample_rate, error_message)
        """
        import platform
        is_windows = platform.system() == "Windows"

        try:
            dev_info = sd.query_devices(dev_id)
        except Exception as e:
            return None, dev_id, SAMPLE_RATE, f"Device #{dev_id} query failed: {e}"

        is_wasapi_loopback = False
        if is_windows and (source.get("is_wasapi_loopback") or dev_info.get("max_input_channels", 0) == 0):
            is_wasapi_loopback = True

        if is_wasapi_loopback:
            input_channels = min(2, dev_info.get("max_output_channels", 2))
            extra_settings = sd.WasapiSettings(loopback=True)
        else:
            input_channels = min(2, dev_info.get("max_input_channels", 0))
            extra_settings = None

        if input_channels < 1:
            return None, dev_id, SAMPLE_RATE, f"Device #{dev_id} has 0 input channels."

        rates_to_try = [SAMPLE_RATE]
        default_sr = int(dev_info.get("default_samplerate", SAMPLE_RATE))
        if default_sr not in rates_to_try and default_sr > 0:
            rates_to_try.append(default_sr)
        for r in (44100, 96000, 32000, 88200, 16000):
            if r not in rates_to_try:
                rates_to_try.append(r)

        def _try_open(target_id: int, channels: int, sr: int, extra: Any) -> Optional[sd.InputStream]:
            try:
                stream = sd.InputStream(
                    device=target_id,
                    channels=channels,
                    samplerate=sr,
                    blocksize=BLOCK_SIZE,
                    dtype=DTYPE,
                    callback=callback,
                    extra_settings=extra
                )
                stream.start()
                return stream
            except Exception as ex:
                logger.debug("Failed opening stream (dev=%s, sr=%d, ch=%d): %s", target_id, sr, channels, ex)
                return None

        # Tier 1: Try requested device with candidate sample rates
        for sr in rates_to_try:
            stream = _try_open(dev_id, input_channels, sr, extra_settings)
            if stream is not None:
                if sr != SAMPLE_RATE:
                    logger.warning("Adaptive sample rate active on device #%d '%s': hardware is %d Hz (resampling in real time to 48,000 Hz)",
                                   dev_id, dev_info.get("name"), sr)
                else:
                    logger.info("Resilient Stream opened on device #%d '%s' at 48,000 Hz", dev_id, dev_info.get("name"))
                return stream, dev_id, sr, ""

        # Tier 2: Multi-Tier Host API Fallback (Windows only)
        if is_windows and not is_wasapi_loopback:
            try:
                all_inputs, _ = self.get_audio_devices()
                base_name = dev_info.get("name", "").split("(")[0].strip().lower()
                for alt_dev in all_inputs:
                    if alt_dev["id"] == dev_id:
                        continue
                    alt_name = alt_dev.get("name", "").split("(")[0].strip().lower()
                    if base_name in alt_name or alt_name in base_name:
                        alt_id = alt_dev["id"]
                        alt_ch = min(2, alt_dev.get("channels", 1))
                        if alt_ch < 1:
                            continue
                        logger.warning("Host API fallback: attempting '%s' (HostAPI: %s, ID: #%d)...",
                                       alt_dev["name"], alt_dev.get("hostapi"), alt_id)
                        for sr in rates_to_try:
                            stream = _try_open(alt_id, alt_ch, sr, None)
                            if stream is not None:
                                logger.warning("Host API fallback SUCCESS on #%d '%s' at %d Hz",
                                               alt_id, alt_dev.get("name"), sr)
                                return stream, alt_id, sr, ""
            except Exception as fb_err:
                logger.debug("Host API fallback error: %s", fb_err)

        # Tier 3: Fallback to System Default Recording Device
        try:
            default_id = sd.default.device[0]
            if default_id is not None and default_id >= 0 and default_id != dev_id:
                def_info = sd.query_devices(default_id)
                def_ch = min(2, def_info.get("max_input_channels", 0))
                if def_ch >= 1:
                    logger.warning("Default device fallback: attempting OS Default #%d '%s'...",
                                   default_id, def_info.get("name"))
                    for sr in rates_to_try:
                        stream = _try_open(default_id, def_ch, sr, None)
                        if stream is not None:
                            logger.warning("OS Default fallback SUCCESS on #%d '%s' at %d Hz",
                                           default_id, def_info.get("name"), sr)
                            return stream, default_id, sr, ""
        except Exception as def_err:
            logger.debug("Default device fallback error: %s", def_err)

        return None, dev_id, SAMPLE_RATE, f"Unable to open audio stream on device '{dev_info.get('name')}' or any fallback."

    def start_input_stream(self) -> bool:
        """Starts or restarts the always-on input stream with multi-tier resilience."""
        self.stop_input_stream()
        
        saved_name = self.config.get("input_device_name", "")
        saved_hostapi = self.config.get("input_host_api", "")
        source = self.find_source_by_name(saved_name, hostapi_hint=saved_hostapi)
        
        if source is None or source.get("is_setup_needed", False):
            self.device_error_state = True
            self.device_error_message = "Desktop audio setup required." if (source and source.get("is_setup_needed")) else "No audio input device available on system."
            logger.warning(self.device_error_message)
            return False

        dev_id = source["id"]
        stream, actual_id, actual_rate, err_msg = self._open_input_stream_resilient(
            dev_id=dev_id,
            source=source,
            callback=self._audio_input_callback
        )
        if stream is not None:
            self.input_stream = stream
            self.current_input_device_id = actual_id
            self.input_stream_rate = actual_rate
            self.is_stream_active = True
            self.device_error_state = False
            self.device_error_message = ""
            return True
        else:
            self.device_error_state = True
            self.device_error_message = err_msg or "Failed to start audio input stream."
            logger.error("Failed to start audio input stream on device #%s: %s", dev_id, self.device_error_message)
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

    def start_secondary_stream(self) -> bool:
        """Starts or restarts the secondary input stream if enabled."""
        self.stop_secondary_stream()
        if not self.config.get("secondary_track_enabled", False):
            return False

        saved_name = self.config.get("secondary_device_name", "")
        saved_hostapi = self.config.get("secondary_host_api", "")

        source = None
        if saved_name:
            source = self.find_source_by_name(saved_name, hostapi_hint=saved_hostapi)

        if source is None or source.get("id") == self.current_input_device_id:
            sources = self.get_unified_audio_sources()
            candidates = [
                s for s in sources 
                if s.get("id") != self.current_input_device_id 
                and not s.get("is_setup_needed", False) 
                and not is_virtual_dummy(s.get("name", ""))
            ]
            if not candidates:
                candidates = [s for s in sources if s.get("id") != self.current_input_device_id and not s.get("is_setup_needed", False)]
            if candidates:
                source = candidates[0]
            elif sources:
                source = sources[0]

        if source is None or source.get("is_setup_needed", False):
            self.secondary_device_error_state = True
            self.secondary_device_error_message = "Desktop audio setup required." if (source and source.get("is_setup_needed")) else "No secondary audio device available."
            logger.warning(self.secondary_device_error_message)
            return False

        dev_id = source["id"]
        stream, actual_id, actual_rate, err_msg = self._open_input_stream_resilient(
            dev_id=dev_id,
            source=source,
            callback=self._secondary_audio_input_callback
        )
        if stream is not None:
            self.secondary_input_stream = stream
            self.current_secondary_device_id = actual_id
            self.secondary_stream_rate = actual_rate
            self.is_secondary_stream_active = True
            self.secondary_device_error_state = False
            self.secondary_device_error_message = ""
            return True
        else:
            self.secondary_device_error_state = True
            self.secondary_device_error_message = err_msg or "Failed to start secondary audio input stream."
            logger.error("Failed to start secondary audio input stream on device #%s: %s", dev_id, self.secondary_device_error_message)
            self.secondary_input_stream = None
            self.is_secondary_stream_active = False
            return False

    def stop_secondary_stream(self):
        """Stops the secondary input stream cleanly."""
        if self.secondary_input_stream:
            try:
                self.secondary_input_stream.stop()
                self.secondary_input_stream.close()
            except Exception as e:
                logger.debug("Error stopping secondary input stream: %s", e)
            self.secondary_input_stream = None
        self.is_secondary_stream_active = False

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

        # Adaptive real-time resampling if primary hardware sample rate != 48,000 Hz
        if self.input_stream_rate != SAMPLE_RATE and self.input_stream_rate > 0:
            orig_len = buffer.shape[0]
            target_len = int(round(orig_len * (SAMPLE_RATE / self.input_stream_rate)))
            if target_len > 0 and target_len != orig_len:
                x_orig = np.linspace(0.0, 1.0, orig_len, endpoint=False)
                x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
                res_l = np.interp(x_new, x_orig, buffer[:, 0]).astype(np.float32)
                res_r = np.interp(x_new, x_orig, buffer[:, 1]).astype(np.float32)
                buffer = np.column_stack((res_l, res_r))

        # --- Real-Time DSP Pipeline ---
        if self.mono_sum:
            left_rms = np.sqrt(np.mean(buffer[:, 0] ** 2))
            right_rms = np.sqrt(np.mean(buffer[:, 1] ** 2))
            
            # Mono Mixer Line-In Feed Logic:
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
            t_now = time.perf_counter()
            try:
                self._record_queue.put_nowait((buffer, t_now))
            except queue.Full:
                logger.error("Recording queue full! Audio frame dropped.")

    def _secondary_audio_input_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """
        Called by PortAudio for every 4096-sample buffer on the secondary audio track.
        Executes level metering and routes to secondary recording queue.
        """
        if status:
            logger.debug("PortAudio secondary input callback status: %s", status)

        t_now = time.perf_counter()

        # Ensure float32 stereo buffer shape (frames, 2)
        if indata.shape[1] == 1:
            buffer = np.repeat(indata, 2, axis=1)
        else:
            buffer = indata.copy()

        # Adaptive real-time resampling if secondary hardware sample rate != 48,000 Hz
        if self.secondary_stream_rate != SAMPLE_RATE and self.secondary_stream_rate > 0:
            orig_len = buffer.shape[0]
            target_len = int(round(orig_len * (SAMPLE_RATE / self.secondary_stream_rate)))
            if target_len > 0 and target_len != orig_len:
                x_orig = np.linspace(0.0, 1.0, orig_len, endpoint=False)
                x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
                res_l = np.interp(x_new, x_orig, buffer[:, 0]).astype(np.float32)
                res_r = np.interp(x_new, x_orig, buffer[:, 1]).astype(np.float32)
                buffer = np.column_stack((res_l, res_r))

        # Live dBFS Peak & RMS Level Metering
        l_peak = np.max(np.abs(buffer[:, 0]))
        r_peak = np.max(np.abs(buffer[:, 1]))
        l_rms = np.sqrt(np.mean(buffer[:, 0] ** 2))
        r_rms = np.sqrt(np.mean(buffer[:, 1] ** 2))

        l_peak_db = 20.0 * math.log10(max(float(l_peak), 1e-3))
        r_peak_db = 20.0 * math.log10(max(float(r_peak), 1e-3))
        l_rms_db = 20.0 * math.log10(max(float(l_rms), 1e-3))
        r_rms_db = 20.0 * math.log10(max(float(r_rms), 1e-3))

        with self._levels_lock:
            self.sec_left_peak_db = max(-60.0, min(0.0, l_peak_db))
            self.sec_right_peak_db = max(-60.0, min(0.0, r_peak_db))
            self.sec_left_rms_db = max(-60.0, min(0.0, l_rms_db))
            self.sec_right_rms_db = max(-60.0, min(0.0, r_rms_db))

            if l_peak >= CLIP_THRESHOLD:
                self.sec_left_clipped = True
            if r_peak >= CLIP_THRESHOLD:
                self.sec_right_clipped = True

        # Route to Secondary Recording Queue
        if self.is_recording:
            try:
                self._secondary_record_queue.put_nowait((buffer, t_now))
            except queue.Full:
                logger.error("Secondary recording queue full! Audio frame dropped.")

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

    def get_secondary_levels(self) -> Tuple[float, float, float, float, bool, bool]:
        """Returns (sec_l_peak_db, sec_r_peak_db, sec_l_rms_db, sec_r_rms_db, sec_l_clipped, sec_r_clipped)."""
        with self._levels_lock:
            return (
                self.sec_left_peak_db,
                self.sec_right_peak_db,
                self.sec_left_rms_db,
                self.sec_right_rms_db,
                self.sec_left_clipped,
                self.sec_right_clipped
            )

    def reset_secondary_clip_indicators(self):
        """Resets secondary persistent CLIP flags."""
        with self._levels_lock:
            self.sec_left_clipped = False
            self.sec_right_clipped = False

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
    _linux_inhibit_proc: Optional[subprocess.Popen] = None

    @classmethod
    def _set_sleep_prevention(cls, enable: bool):
        """
        Prevents OS from entering sleep or idle suspend while recording.
        - Windows: Uses SetThreadExecutionState with ES_SYSTEM_REQUIRED and ES_AWAYMODE_REQUIRED.
        - macOS: Uses /usr/bin/caffeinate -dimu.
        - Linux: Uses /usr/bin/systemd-inhibit.
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
        elif sys.platform.startswith("linux"):
            if enable:
                try:
                    if cls._linux_inhibit_proc is None or cls._linux_inhibit_proc.poll() is not None:
                        cls._linux_inhibit_proc = subprocess.Popen(
                            ["systemd-inhibit", "--what=idle:sleep:handle-lid-switch",
                             "--who=AudioGuard", "--why=Recording Lossless Audio Backup",
                             "sleep", "infinity"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        logger.info("Linux Sleep Prevention: ACTIVE (systemd-inhibit PID %s)", cls._linux_inhibit_proc.pid)
                except Exception as e:
                    logger.debug("Linux systemd-inhibit not available: %s", e)
            else:
                try:
                    if cls._linux_inhibit_proc is not None:
                        cls._linux_inhibit_proc.terminate()
                        cls._linux_inhibit_proc = None
                        logger.info("Linux Sleep Prevention: RELEASED")
                except Exception as e:
                    logger.debug("Failed to release Linux sleep prevention: %s", e)

    # -------------------------------------------------------------
    # Recording Session Control (Single-File Crash-Proof FLAC)
    # -------------------------------------------------------------
    def start_recording(self, manual: bool = False, is_manual: Optional[bool] = None, slot_label: str = "") -> Optional[str]:
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
            get_free_disk_space_gb, get_disk_safety_floors, cleanup_old_backups,
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

        # Low-Disk Space Pre-Flight Check with dynamic safety floors
        safety_floor_gb, warning_floor_gb = get_disk_safety_floors(str(backup_folder))
        free_gb = get_free_disk_space_gb(str(backup_folder))
        if free_gb < warning_floor_gb:
            logger.warning("Low disk space before recording (%.2f GB free < %.2f GB warning floor). Running retention cleanup...", free_gb, warning_floor_gb)
            try:
                cleanup_old_backups(str(backup_folder), retention_days, pattern=pattern, profile=getattr(self.config, "profile", "default"))
                free_gb = get_free_disk_space_gb(str(backup_folder))
            except Exception as ex:
                logger.error("Retention cleanup error: %s", ex)

        if free_gb < safety_floor_gb:
            self.low_disk_state = True
            self.low_disk_message = f"Disk Space Critical ({free_gb:.2f} GB free < {safety_floor_gb:.2f} GB safety floor). Recording blocked."
            logger.error("CANNOT START RECORDING: %s", self.low_disk_message)
            return None

        # Reset low disk state when space is healthy
        self.low_disk_state = False
        self.low_disk_message = ""

        now = datetime.now()
        # Resolve target directory based on grouping (e.g. C:\AudioBackups\2026-11\)
        target_dir = get_recording_subfolder(str(backup_folder), folder_grouping=folder_grouping, dt=now)

        candidate_name = format_recording_filename(pattern, is_manual=manual, dt=now, slot_label=slot_label)
        target_path = target_dir / candidate_name

        # Collision avoidance: append _1, _2 if file with exact name already exists
        if target_path.exists():
            stem = target_path.stem
            counter = 1
            while (target_dir / f"{stem}_{counter}.flac").exists():
                counter += 1
            target_path = target_dir / f"{stem}_{counter}.flac"

        file_path = str(target_path)

        is_dual = bool(self.config.get("secondary_track_enabled", False))
        multitrack_mode = self.config.get("multitrack_mode", "separate")

        # Clear recording queues
        while not self._record_queue.empty():
            try:
                self._record_queue.get_nowait()
            except Exception:
                break
        while not self._secondary_record_queue.empty():
            try:
                self._secondary_record_queue.get_nowait()
            except Exception:
                break

        if is_dual:
            # Ensure secondary stream is running
            if not self.is_secondary_stream_active:
                self.start_secondary_stream()

            stem = candidate_name[:-5] if candidate_name.lower().endswith(".flac") else candidate_name
            if multitrack_mode == "single":
                # Single 4-channel multitrack file
                target_path = target_dir / f"{stem}_multitrack.flac"
                if target_path.exists():
                    counter = 1
                    while (target_dir / f"{stem}_{counter}_multitrack.flac").exists():
                        counter += 1
                    target_path = target_dir / f"{stem}_{counter}_multitrack.flac"
                file_path = str(target_path)
                secondary_file_path = None
            else:
                # Separate files (_track1 & _track2)
                target_path_t1 = target_dir / f"{stem}_track1.flac"
                target_path_t2 = target_dir / f"{stem}_track2.flac"
                if target_path_t1.exists() or target_path_t2.exists():
                    counter = 1
                    while (target_dir / f"{stem}_{counter}_track1.flac").exists() or (target_dir / f"{stem}_{counter}_track2.flac").exists():
                        counter += 1
                    target_path_t1 = target_dir / f"{stem}_{counter}_track1.flac"
                    target_path_t2 = target_dir / f"{stem}_{counter}_track2.flac"
                file_path = str(target_path_t1)
                secondary_file_path = str(target_path_t2)
        else:
            file_path = str(target_path)
            secondary_file_path = None

        self.recording_file_path = file_path
        self.recording_secondary_file_path = secondary_file_path
        self.is_manual_recording = manual
        self.recording_start_time = time.time()
        self._stop_writer_event.clear()

        # Start dedicated FLAC writer thread
        self._writer_thread = threading.Thread(
            target=self._flac_writer_worker,
            args=(file_path, secondary_file_path, multitrack_mode, is_dual),
            daemon=True
        )
        self._writer_thread.start()

        self.is_recording = True
        self._set_sleep_prevention(True)
        if is_dual:
            logger.info("RECORDING STARTED (Multi-Track: %s) -> File: %s %s (Manual: %s)",
                        multitrack_mode, file_path, f"& {secondary_file_path}" if secondary_file_path else "", manual)
        else:
            logger.info("RECORDING STARTED -> File: %s (Manual: %s)", file_path, manual)
        return file_path

    def stop_recording(self) -> Optional[str]:
        """Stops the active recording session and cleanly finalizes the FLAC file(s)."""
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
        finished_secondary_path = self.recording_secondary_file_path
        elapsed = time.time() - (self.recording_start_time or time.time())
        self.recording_file_path = None
        self.recording_secondary_file_path = None
        self.recording_start_time = None

        logger.info("RECORDING FINISHED -> Duration: %.1fs, File: %s %s",
                    elapsed, finished_path, f"& {finished_secondary_path}" if finished_secondary_path else "")
        profile = getattr(self.config, "profile", "default")
        retention_days = int(self.config.get("retention_days", 30))

        # Register finished FLAC(s) in the retention ledger
        paths_to_register = [p for p in (finished_path, finished_secondary_path) if p]
        for p in paths_to_register:
            try:
                from config_manager import record_file_retention
                record_file_retention(p, retention_days, profile=profile)
            except Exception as e:
                logger.error("Failed to record FLAC file retention: %s", e)

        # Trigger background companion format conversion if enabled
        companion_fmt = self.config.get("companion_format")
        if not companion_fmt:
            companion_fmt = "mp3" if self.config.get("auto_export_mp3", True) else "none"

        if companion_fmt != "none" and paths_to_register:
            from config_manager import convert_flac_companion, record_file_retention
            def _async_convert(src_list, fmt):
                for src in src_list:
                    logger.info("Auto-exporting %s copy for %s...", fmt.upper(), Path(src).name)
                    success = convert_flac_companion(src, target_format=fmt)
                    if success:
                        comp_path = Path(src).with_suffix(f".{fmt.lower()}")
                        if comp_path.exists():
                            record_file_retention(str(comp_path), retention_days, profile=profile)

            t = threading.Thread(target=_async_convert, args=(paths_to_register, companion_fmt), daemon=True)
            t.start()

        # Trigger automatic retention cleanup post-recording
        try:
            from config_manager import cleanup_old_backups
            folder = self.config.get("backup_folder", "")
            pattern = self.config.get("filename_pattern", "")
            cleanup_old_backups(folder, retention_days, pattern=pattern, profile=profile)
        except Exception as e:
            logger.error("Failed to run post-recording retention cleanup: %s", e)

        return finished_path

    def _flac_writer_worker(
        self,
        file_path: str,
        secondary_file_path: Optional[str] = None,
        multitrack_mode: str = "separate",
        is_dual_track: bool = False
    ):
        """
        Dedicated FLAC disk writer thread.
        CRITICAL POWER-LOSS SAFETY:
        Writes 48kHz 24-bit FLAC blocks and executes sf_file.flush()
        followed by os.fsync() every 1.0 second.
        Monitors free disk space every 30s to prevent ENOSPC crashes.

        When is_dual_track is True:
        Employs the Zero-Drift Phase-Locked Resynchronizer:
        - Microsecond initial head alignment via arrival timestamps.
        - 1-Second block alignment via continuous np.interp sample-count locking.
        - Mode A: Parallel synchronized writes to *_track1.flac and *_track2.flac.
        - Mode B: Interleaved 4-channel PCM_24 FLAC (*_multitrack.flac).
        """
        logger.info("FLAC Writer thread started (dual=%s, mode=%s) for '%s'",
                    is_dual_track, multitrack_mode, file_path)
        sf_file = None
        raw_file = None
        sf_file_t2 = None
        raw_file_t2 = None
        backup_folder_str = str(Path(file_path).parent)

        try:
            from config_manager import get_free_disk_space_gb, get_disk_safety_floors, cleanup_old_backups

            if not is_dual_track:
                # Standard Single-Track Writer
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
                        item = self._record_queue.get(timeout=0.25)
                    except queue.Empty:
                        item = None

                    if item is not None:
                        block, _ = item if isinstance(item, tuple) else (item, 0.0)
                        sf_file.write(block)
                        blocks_since_flush += 1

                    now = time.time()
                    if (now - last_flush_time >= 1.0) or (blocks_since_flush >= 12):
                        sf_file.flush()
                        try:
                            raw_file.flush()
                            os.fsync(raw_file.fileno())
                        except Exception as fsync_err:
                            logger.debug("fsync warning: %s", fsync_err)
                        last_flush_time = now
                        blocks_since_flush = 0

                    if now - last_disk_check_time >= 30.0:
                        last_disk_check_time = now
                        safety_floor_gb, warning_floor_gb = get_disk_safety_floors(backup_folder_str)
                        free_gb = get_free_disk_space_gb(backup_folder_str)
                        if free_gb < warning_floor_gb:
                            try:
                                retention_days = int(self.config.get("retention_days", 30))
                                cleanup_old_backups(backup_folder_str, retention_days, profile=getattr(self.config, "profile", "default"))
                                free_gb = get_free_disk_space_gb(backup_folder_str)
                            except Exception:
                                pass
                        if free_gb < safety_floor_gb:
                            logger.critical("EMERGENCY: Disk space reached safety floor. Finalizing recording cleanly.")
                            self.low_disk_state = True
                            self.low_disk_message = f"Recording stopped automatically: Free space reached safety floor ({safety_floor_gb:.2f} GB)."
                            break

                # Drain remaining
                while not self._record_queue.empty():
                    try:
                        item = self._record_queue.get_nowait()
                        block, _ = item if isinstance(item, tuple) else (item, 0.0)
                        sf_file.write(block)
                    except queue.Empty:
                        break

                sf_file.flush()
                try:
                    raw_file.flush()
                    os.fsync(raw_file.fileno())
                except Exception:
                    pass

            else:
                # Zero-Drift Dual-Track Writer (Mode A or Mode B)
                if multitrack_mode == "single":
                    raw_file = open(file_path, "wb")
                    sf_file = sf.SoundFile(
                        raw_file,
                        mode="w",
                        samplerate=SAMPLE_RATE,
                        channels=4,
                        format="FLAC",
                        subtype="PCM_24"
                    )
                else:
                    raw_file = open(file_path, "wb")
                    sf_file = sf.SoundFile(
                        raw_file,
                        mode="w",
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        format="FLAC",
                        subtype="PCM_24"
                    )
                    if secondary_file_path:
                        raw_file_t2 = open(secondary_file_path, "wb")
                        sf_file_t2 = sf.SoundFile(
                            raw_file_t2,
                            mode="w",
                            samplerate=SAMPLE_RATE,
                            channels=CHANNELS,
                            format="FLAC",
                            subtype="PCM_24"
                        )

                # Microsecond Initial Head Alignment
                b1, t1 = None, 0.0
                b2, t2 = None, 0.0
                wait_start = time.time()
                while not self._stop_writer_event.is_set() and (b1 is None or b2 is None):
                    if b1 is None:
                        try:
                            item1 = self._record_queue.get(timeout=0.05)
                            b1, t1 = item1 if isinstance(item1, tuple) else (item1, time.perf_counter())
                        except queue.Empty:
                            pass
                    if b2 is None:
                        try:
                            item2 = self._secondary_record_queue.get(timeout=0.05)
                            b2, t2 = item2 if isinstance(item2, tuple) else (item2, time.perf_counter())
                        except queue.Empty:
                            pass
                    if time.time() - wait_start > 1.5:
                        break

                if b1 is None:
                    b1 = np.zeros((BLOCK_SIZE, 2), dtype=np.float32)
                    t1 = time.perf_counter()
                if b2 is None:
                    b2 = np.zeros((BLOCK_SIZE, 2), dtype=np.float32)
                    t2 = time.perf_counter()

                offset_sec = t2 - t1
                offset_samples = int(round(offset_sec * SAMPLE_RATE))
                offset_samples = max(-SAMPLE_RATE, min(SAMPLE_RATE, offset_samples))

                if offset_samples > 0:
                    pad = np.zeros((offset_samples, 2), dtype=np.float32)
                    b2 = np.vstack([pad, b2])
                elif offset_samples < 0:
                    pad = np.zeros((abs(offset_samples), 2), dtype=np.float32)
                    b1 = np.vstack([pad, b1])

                target_backlog = 4096
                init_pad = np.zeros((target_backlog, 2), dtype=np.float32)
                t1_accum = np.vstack([init_pad, b1])
                t2_accum = np.vstack([init_pad, b2])

                last_flush_time = time.time()
                last_disk_check_time = time.time()
                blocks_since_flush = 0

                def write_aligned_pair(chunk1: np.ndarray, chunk2: np.ndarray):
                    nonlocal blocks_since_flush
                    if multitrack_mode == "single":
                        chunk_4ch = np.column_stack((chunk1, chunk2))
                        sf_file.write(chunk_4ch)
                    else:
                        sf_file.write(chunk1)
                        if sf_file_t2 is not None:
                            sf_file_t2.write(chunk2)
                    blocks_since_flush += 1

                while not self._stop_writer_event.is_set():
                    # Drain queue 1
                    while not self._record_queue.empty():
                        try:
                            item = self._record_queue.get_nowait()
                            b, _ = item if isinstance(item, tuple) else (item, 0.0)
                            t1_accum = np.vstack([t1_accum, b])
                        except queue.Empty:
                            break

                    # Drain queue 2
                    while not self._secondary_record_queue.empty():
                        try:
                            item = self._secondary_record_queue.get_nowait()
                            b, _ = item if isinstance(item, tuple) else (item, 0.0)
                            t2_accum = np.vstack([t2_accum, b])
                        except queue.Empty:
                            break

                    # Process in matched blocks of BLOCK_SIZE (4096 samples)
                    while len(t1_accum) >= BLOCK_SIZE:
                        chunk1 = t1_accum[:BLOCK_SIZE]
                        t1_accum = t1_accum[BLOCK_SIZE:]

                        # Zero-Drift Resynchronizer for Track 2
                        err = len(t2_accum) - (BLOCK_SIZE + target_backlog)
                        delta = int(np.clip(round(err * 0.01), -4, 4))
                        m = BLOCK_SIZE + delta
                        m = max(1, min(m, len(t2_accum)))

                        raw2 = t2_accum[:m]
                        t2_accum = t2_accum[m:]

                        if m == BLOCK_SIZE:
                            chunk2 = raw2
                        else:
                            x_old = np.linspace(0, 1, m, endpoint=False)
                            x_new = np.linspace(0, 1, BLOCK_SIZE, endpoint=False)
                            chunk2 = np.zeros((BLOCK_SIZE, 2), dtype=np.float32)
                            chunk2[:, 0] = np.interp(x_new, x_old, raw2[:, 0])
                            chunk2[:, 1] = np.interp(x_new, x_old, raw2[:, 1])

                        # Underflow defense
                        if len(chunk2) < BLOCK_SIZE:
                            pad_zeros = np.zeros((BLOCK_SIZE - len(chunk2), 2), dtype=np.float32)
                            chunk2 = np.vstack([chunk2, pad_zeros])

                        write_aligned_pair(chunk1, chunk2)

                    # Continuous flush & fsync every 1.0s or ~12 blocks
                    now = time.time()
                    if (now - last_flush_time >= 1.0) or (blocks_since_flush >= 12):
                        sf_file.flush()
                        try:
                            raw_file.flush()
                            os.fsync(raw_file.fileno())
                        except Exception:
                            pass
                        if sf_file_t2 and raw_file_t2:
                            sf_file_t2.flush()
                            try:
                                raw_file_t2.flush()
                                os.fsync(raw_file_t2.fileno())
                            except Exception:
                                pass
                        last_flush_time = now
                        blocks_since_flush = 0

                    if now - last_disk_check_time >= 30.0:
                        last_disk_check_time = now
                        safety_floor_gb, warning_floor_gb = get_disk_safety_floors(backup_folder_str)
                        free_gb = get_free_disk_space_gb(backup_folder_str)
                        if free_gb < safety_floor_gb:
                            logger.critical("EMERGENCY: Disk space reached safety floor. Finalizing recording cleanly.")
                            self.low_disk_state = True
                            self.low_disk_message = f"Recording stopped automatically: Free space reached safety floor ({safety_floor_gb:.2f} GB)."
                            break

                    time.sleep(0.04)

                # Final drainage
                while not self._record_queue.empty():
                    try:
                        item = self._record_queue.get_nowait()
                        b, _ = item if isinstance(item, tuple) else (item, 0.0)
                        t1_accum = np.vstack([t1_accum, b])
                    except queue.Empty:
                        break
                while not self._secondary_record_queue.empty():
                    try:
                        item = self._secondary_record_queue.get_nowait()
                        b, _ = item if isinstance(item, tuple) else (item, 0.0)
                        t2_accum = np.vstack([t2_accum, b])
                    except queue.Empty:
                        break

                rem_n = len(t1_accum)
                if rem_n > 0:
                    chunk1 = t1_accum
                    if len(t2_accum) >= rem_n:
                        chunk2 = t2_accum[:rem_n]
                    else:
                        pad_zeros = np.zeros((rem_n - len(t2_accum), 2), dtype=np.float32)
                        chunk2 = np.vstack([t2_accum, pad_zeros]) if len(t2_accum) > 0 else pad_zeros
                    write_aligned_pair(chunk1, chunk2)

                sf_file.flush()
                try:
                    raw_file.flush()
                    os.fsync(raw_file.fileno())
                except Exception:
                    pass
                if sf_file_t2 and raw_file_t2:
                    sf_file_t2.flush()
                    try:
                        raw_file_t2.flush()
                        os.fsync(raw_file_t2.fileno())
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
            if sf_file_t2 is not None:
                try:
                    sf_file_t2.close()
                except Exception:
                    pass
            if raw_file_t2 is not None:
                try:
                    raw_file_t2.close()
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
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception as e:
                    logger.debug("PortAudio watchdog reinit notice: %s", e)
                logger.info("Device Watchdog: Attempting audio stream reconnect...")
                success = self.start_input_stream()
                if success:
                    logger.info("Device Watchdog: Successfully reconnected audio input!")

            # Secondary stream watchdog
            if self.config.get("secondary_track_enabled", False):
                if not self.is_secondary_stream_active or self.secondary_device_error_state:
                    logger.info("Device Watchdog: Attempting secondary audio stream reconnect...")
                    sec_success = self.start_secondary_stream()
                    if sec_success:
                        logger.info("Device Watchdog: Successfully reconnected secondary audio input!")
