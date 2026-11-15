"""
AudioGuard - Smart Scheduler & Multi-Slot Auto-Recording Engine
- Supports multiple daily time windows (e.g. 09:00-10:00, 12:00-14:00, 18:00-21:00)
- Global Enable / Disable toggle for automatic recording
- Late-Boot Catch-up (starts immediately if PC boots inside an active window)
- Smart Voice-Activity Overtime Extension (+1 hour cap, 90s silence auto-stop)
- Single-session user pause suppression (resets automatically when window passes)
"""

import time
import logging
from datetime import datetime, time as dtime, timedelta
from typing import Callable, Optional, Tuple, List, Dict, Any

logger = logging.getLogger("AudioGuard.Scheduler")

DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class SchedulerEngine:
    def __init__(self,
                 config_manager,
                 on_start_recording: Callable[[bool], None],
                 on_stop_recording: Callable[[], None],
                 is_voice_active_fn: Optional[Callable[[float], bool]] = None):
        """
        :param config_manager: ConfigManager instance
        :param on_start_recording: callback(is_manual: bool)
        :param on_stop_recording: callback()
        :param is_voice_active_fn: optional callback(within_seconds: float) -> bool
        """
        self.config = config_manager
        self.on_start_recording = on_start_recording
        self.on_stop_recording = on_stop_recording
        self.is_voice_active_fn = is_voice_active_fn

        # Schedule configuration
        self.enabled: bool = bool(self.config.get("schedule_enabled", True))
        self.slots: List[Dict[str, Any]] = self._load_slots_from_config()

        # State tracking
        self.is_scheduled_recording_active = False
        self.is_manual_recording_active = False
        self.active_slot: Optional[Dict[str, Any]] = None
        self.suppressed_slot: Optional[Dict[str, Any]] = None
        self.suppressed_for_current_window = False
        self.last_evaluated_window_state = False

        # Smart Overtime Extension State
        self.is_in_overtime = False
        self.overtime_start_time: Optional[float] = None
        self.max_overtime_seconds = 3600.0   # Up to 1 extra hour max
        self.overtime_silence_limit = 90.0   # Stop if silence lasts 90 continuous seconds during overtime

    def _load_slots_from_config(self) -> List[Dict[str, Any]]:
        """Loads schedule slots from config with fallback to legacy single-schedule fields."""
        raw_slots = self.config.get("schedule_slots")
        if isinstance(raw_slots, list) and len(raw_slots) > 0:
            cleaned = []
            for s in raw_slots:
                if isinstance(s, dict) and "start" in s and "end" in s:
                    raw_days = s.get("days", ["All"])
                    if not isinstance(raw_days, list) or not raw_days:
                        raw_days = ["All"]
                    cleaned.append({
                        "start": str(s["start"]).strip(),
                        "end": str(s["end"]).strip(),
                        "days": raw_days
                    })
            if cleaned:
                return cleaned

        # Fallback to legacy single schedule
        s_start = self.config.get("schedule_start", "18:00")
        s_end = self.config.get("schedule_end", "21:00")
        return [{"start": s_start, "end": s_end, "days": ["All"]}]

    @staticmethod
    def _parse_time(time_str: str) -> dtime:
        """Parses 'HH:MM' string to datetime.time."""
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Time '{time_str}' must be in HH:MM format.")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Hour ({hour}) or minute ({minute}) out of valid range.")
        return dtime(hour, minute)

    def update_schedules(self, enabled: bool, slots: List[Dict[str, Any]]) -> bool:
        """
        Validates and updates all schedule slots and enable state.
        """
        try:
            valid_slots = []
            for s in slots:
                st_str = s.get("start", "").strip()
                et_str = s.get("end", "").strip()
                days = s.get("days", ["All"])
                if not isinstance(days, list) or not days:
                    days = ["All"]
                # Validate format
                self._parse_time(st_str)
                self._parse_time(et_str)
                valid_slots.append({"start": st_str, "end": et_str, "days": days})

            self.enabled = enabled
            self.slots = valid_slots
            self.config.set("schedule_enabled", enabled)
            self.config.set("schedule_slots", valid_slots)

            # Update legacy keys for backward compatibility
            if valid_slots:
                self.config.set("schedule_start", valid_slots[0]["start"])
                self.config.set("schedule_end", valid_slots[0]["end"])

            logger.info("Schedules updated: Enabled=%s, %d slots: %s", enabled, len(valid_slots), valid_slots)
            self.evaluate()
            return True
        except Exception as e:
            logger.error("Failed to update schedules: %s", e)
            return False

    def is_inside_schedule_window(self, check_dt: Optional[datetime] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Checks if current time is inside ANY configured schedule window for today.
        Returns (is_inside, matching_slot_dict).
        """
        if not self.enabled or not self.slots:
            return False, None

        if check_dt is None:
            check_dt = datetime.now()
        now_t = check_dt.time()
        current_day = check_dt.strftime("%a")

        for slot in self.slots:
            days = slot.get("days", ["All"])
            if "All" not in days and current_day not in days:
                continue

            try:
                st = self._parse_time(slot["start"])
                et = self._parse_time(slot["end"])
                if st <= et:
                    # Same day window (e.g. 09:00 - 10:00)
                    if st <= now_t < et:
                        return True, slot
                else:
                    # Midnight crossing window (e.g. 22:00 - 02:00)
                    if now_t >= st or now_t < et:
                        return True, slot
            except Exception:
                continue

        return False, None

    def get_next_slot(self, check_dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Returns the next upcoming schedule slot across the next 7 days:
        {"slot": {"start": "...", "end": "...", "days": [...]}, "is_today": bool, "day_name": str}
        """
        if not self.enabled or not self.slots:
            return None

        if check_dt is None:
            check_dt = datetime.now()
        now_t = check_dt.time()

        for day_offset in range(7):
            target_dt = check_dt + timedelta(days=day_offset)
            target_day_name = target_dt.strftime("%a")
            upcoming_for_day = []

            for slot in self.slots:
                days = slot.get("days", ["All"])
                if "All" not in days and target_day_name not in days:
                    continue

                try:
                    st = self._parse_time(slot["start"])
                    if day_offset == 0:
                        if st > now_t:
                            upcoming_for_day.append((st, slot))
                    else:
                        upcoming_for_day.append((st, slot))
                except Exception:
                    continue

            if upcoming_for_day:
                upcoming_for_day.sort(key=lambda x: x[0])
                return {
                    "slot": upcoming_for_day[0][1],
                    "is_today": (day_offset == 0),
                    "day_name": "Today" if day_offset == 0 else target_day_name
                }

        return None

    def evaluate(self):
        """
        Heartbeat watchdog tick called every 2 seconds.
        Handles:
          - Multi-window automatic trigger & late-boot catch-up
          - Smart Voice-Activity Overtime Extension (up to +1 hour)
          - Automatic window exit & suppression reset
        """
        if not self.enabled:
            # If auto-recording was active and schedule was disabled, stop it
            if self.is_scheduled_recording_active:
                logger.info("Schedule disabled while recording. Stopping scheduled backup.")
                self.is_scheduled_recording_active = False
                self.is_in_overtime = False
                self.active_slot = None
                self.on_stop_recording()
            return

        inside_window, matching_slot = self.is_inside_schedule_window()
        now_sec = time.time()

        # If scheduled recording is active:
        if self.is_scheduled_recording_active:
            if not inside_window:
                # We reached or passed the end time of the active slot!
                voice_active = self.is_voice_active_fn(60.0) if self.is_voice_active_fn else False
                end_str = self.active_slot["end"] if self.active_slot else "Scheduled End"

                if not self.is_in_overtime:
                    if voice_active:
                        self.is_in_overtime = True
                        self.overtime_start_time = now_sec
                        logger.info("Schedule end time (%s) reached, but voice is still active! Extending recording for up to 1 extra hour...", end_str)
                    else:
                        logger.info("Schedule window reached end time (%s) with no speech. Stopping recording cleanly.", end_str)
                        self.is_scheduled_recording_active = False
                        self.is_in_overtime = False
                        self.overtime_start_time = None
                        self.active_slot = None
                        self.on_stop_recording()
                else:
                    # Currently in overtime extension
                    overtime_elapsed = now_sec - (self.overtime_start_time or now_sec)
                    voice_recently_active = self.is_voice_active_fn(self.overtime_silence_limit) if self.is_voice_active_fn else False

                    if overtime_elapsed >= self.max_overtime_seconds:
                        logger.info("Overtime extension reached maximum 1-hour cap (%.0f min). Finalizing recording.", overtime_elapsed / 60.0)
                        self.is_scheduled_recording_active = False
                        self.is_in_overtime = False
                        self.overtime_start_time = None
                        self.active_slot = None
                        self.on_stop_recording()
                    elif not voice_recently_active:
                        logger.info("Voice activity ceased during overtime (silence > %.0fs). Finalizing recording after %.1f min extension.",
                                    self.overtime_silence_limit, overtime_elapsed / 60.0)
                        self.is_scheduled_recording_active = False
                        self.is_in_overtime = False
                        self.overtime_start_time = None
                        self.active_slot = None
                        self.on_stop_recording()

        # Outside window and not in overtime: reset suppression if we moved out of the suppressed slot
        if not inside_window and not self.is_in_overtime and self.last_evaluated_window_state:
            if self.suppressed_for_current_window:
                logger.info("Active schedule window passed. Resetting pause/suppression flag for next schedule.")
                self.suppressed_for_current_window = False
                self.suppressed_slot = None

        # Inside active window: start auto-recording if not already running
        elif inside_window:
            # If we moved into a new slot different from suppressed slot, clear suppression
            if self.suppressed_slot != matching_slot:
                self.suppressed_for_current_window = False
                self.suppressed_slot = None

            if not self.is_scheduled_recording_active and not self.is_manual_recording_active:
                if not self.suppressed_for_current_window:
                    logger.info("Inside schedule window (%s — %s). Starting automatic recording...",
                                matching_slot["start"], matching_slot["end"])
                    self.is_scheduled_recording_active = True
                    self.active_slot = matching_slot
                    self.is_in_overtime = False
                    self.overtime_start_time = None
                    self.on_start_recording(False)

        self.last_evaluated_window_state = inside_window

    def trigger_manual_start(self):
        """User clicked 'Start Manual Recording'."""
        logger.info("Manual recording triggered by user.")
        self.is_manual_recording_active = True
        self.suppressed_for_current_window = False
        self.suppressed_slot = None
        self.is_in_overtime = False
        self.overtime_start_time = None
        self.on_start_recording(True)

    def trigger_manual_stop(self):
        """User clicked 'Stop Recording'."""
        inside_window, matching_slot = self.is_inside_schedule_window()
        logger.info("Manual stop requested. Inside window: %s, Scheduled: %s, Manual: %s, Overtime: %s",
                    inside_window, self.is_scheduled_recording_active, self.is_manual_recording_active, self.is_in_overtime)

        if inside_window and self.is_scheduled_recording_active:
            # Stopping during scheduled window -> Suppress until window passes
            self.suppressed_for_current_window = True
            self.suppressed_slot = matching_slot
            logger.info("Scheduled recording stopped early by user. Suppressing auto-restart for current window (%s — %s).",
                        matching_slot["start"], matching_slot["end"])

        self.is_scheduled_recording_active = False
        self.is_manual_recording_active = False
        self.is_in_overtime = False
        self.overtime_start_time = None
        self.active_slot = None
        self.on_stop_recording()

    def resume_suppressed_schedule(self):
        """User clicked 'Resume Scheduled Recording' after pausing it."""
        inside_window, matching_slot = self.is_inside_schedule_window()
        if inside_window:
            logger.info("Resuming paused scheduled recording for %s — %s...", matching_slot["start"], matching_slot["end"])
            self.suppressed_for_current_window = False
            self.suppressed_slot = None
            self.is_scheduled_recording_active = True
            self.active_slot = matching_slot
            self.on_start_recording(False)
