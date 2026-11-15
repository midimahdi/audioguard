"""
AudioGuard - Main Desktop Application
High-Performance, Zero-Lag Desktop Utility (customtkinter)
- Clean Dual-View: Focused Dashboard + Dedicated Settings View
- Multi-Slot Daily Schedules (e.g. 09:00-10:00, 12:00-14:00, 18:00-21:00)
- Master Enable/Disable Toggle for Automatic Recording
- 1-Second Dedicated Elapsed Recording Timer (Smooth HH:MM:SS)
- Zero-Lag Resizing with Automatic Draw-Throttling during Window Drag
- Throttled Zero-Allocation Stereo VU Meter (Paused when hidden/minimized)
- Clean Hardware Input Detection (No hardcoded "Mixer 3.5mm" text)
- Volunteer-Proof System Tray Minimization with IPC Auto-Restore
"""

from __future__ import annotations
import os
import sys
import re
import time
import socket
import argparse
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config_manager import (
    ConfigManager, setup_logging, logger,
    is_autostart_enabled, set_autostart,
    SingleInstanceLock, get_free_disk_space_gb, get_disk_safety_floors,
    cleanup_old_backups, list_available_profiles, delete_profile,
    create_desktop_shortcut, get_default_backup_folder
)
from audio_engine import AudioEngine
from scheduler import SchedulerEngine
from tray_manager import TrayManager
from locales import (
    t, set_current_language, get_current_language, SUPPORTED_LANGUAGES
)

# Clean Desktop Palette
COLOR_BG = "#121214"            # Matte charcoal background
COLOR_PANEL = "#1C1C20"         # Clean flat panel
COLOR_PANEL_BORDER = "#2A2A30"  # Subtle 1px divider
COLOR_TEXT_WHITE = "#FFFFFF"    # Crisp primary text
COLOR_TEXT_MUTED = "#9E9EA8"    # Legible secondary label
COLOR_GREEN = "#10B981"         # Standby / Normal / Level Safe
COLOR_GREEN_HOVER = "#059669"
COLOR_AMBER = "#F59E0B"         # Warning / Sweet Spot
COLOR_RED = "#DC2626"           # Recording / Stop
COLOR_RED_HOVER = "#B91C1C"
COLOR_BLUE = "#3B82F6"          # Clean blue accent

IPC_BASE_PORT = 54900


def get_ipc_port(profile: str = "default") -> int:
    """Returns the dedicated IPC port for the given profile."""
    if profile == "default":
        return IPC_BASE_PORT
    offset = sum((i + 1) * ord(c) for i, c in enumerate(profile)) % 40
    return IPC_BASE_PORT + 1 + offset


def signal_existing_instance(profile: str = "default") -> bool:
    """Sends a wake-up signal to an already running AudioGuard instance for the specified profile."""
    port = get_ipc_port(profile)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect(("127.0.0.1", port))
        s.sendall(b"SHOW\n")
        s.close()
        return True
    except Exception as e:
        logger.debug("Could not signal existing instance [%s] on port %d: %s", profile, port, e)
        return False


def is_profile_running(profile: str = "default") -> bool:
    """Checks whether an instance for the given profile is currently running."""
    port = get_ipc_port(profile)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def enable_windows_dark_title_bar(window_root):
    """Enables Windows 10 & 11 immersive dark mode title bar."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window_root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window_root.winfo_id())
        if not hwnd:
            hwnd = window_root.winfo_id()
        value = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE on Windows 11 & modern Win10, 19 on older Win10
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        if res != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AudioGuardApp:
    def __init__(self, root: ctk.CTk, start_minimized: bool = False, profile: str = "default"):
        self.root = root
        self.profile = profile or "default"
        self._schedules_dirty = False

        app_title = "AudioGuard" if self.profile == "default" else f"AudioGuard [{self.profile}]"
        self.root.title(app_title)
        self.root.geometry("560x620")
        self.root.minsize(500, 500)
        self.root.configure(fg_color=COLOR_BG)
        enable_windows_dark_title_bar(self.root)

        self.current_view = "dashboard"
        self._last_resize_time = 0.0

        if start_minimized:
            self.root.withdraw()
            logger.info("Application initialized minimized to System Tray (%s).", self.profile)

        # Initialize Config
        self.config = ConfigManager(profile=self.profile)

        # Initialize Localization
        saved_lang = self.config.get("language", "en")
        set_current_language(saved_lang)

        # Initialize Audio Engine
        self.audio = AudioEngine(self.config)

        # Initialize Scheduler (Multi-Slot Support)
        self.scheduler = SchedulerEngine(
            config_manager=self.config,
            on_start_recording=self.on_scheduler_start_recording,
            on_stop_recording=self.on_scheduler_stop_recording,
            is_voice_active_fn=self.audio.is_voice_active
        )

        # Initialize Tray Manager
        self.tray = TrayManager(
            on_show_window=self.show_window_from_tray,
            on_toggle_record=self.toggle_manual_recording,
            on_admin_quit=self.admin_quit,
            app_title=app_title
        )

        # Build UI
        self._build_header()
        self._build_dashboard_view()
        self._build_settings_view()

        # Start with Dashboard visible
        self.show_dashboard()

        # Bind window resize to debounce canvas drawing and prevent freezes
        self.root.bind("<Configure>", self._on_window_configure)

        # Populate devices and start audio
        self.refresh_devices_list()
        self.audio.start_input_stream()

        # Startup retention cleanup
        self.root.after(1000, self._startup_cleanup)

        # Start background loops
        self.tray.start()
        self._start_ipc_server()
        self._schedule_watchdog_tick()
        self._meter_ui_tick()
        self._timer_ui_tick()

        # Intercept window close button (volunteer-proof hide to tray / Dock)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_button_clicked)

        # macOS Dock reopen hook (restores window when Dock icon is clicked)
        if sys.platform == "darwin":
            try:
                self.root.createcommand("::tk::mac::ReopenApplication", self.show_window_from_tray)
            except Exception as e:
                logger.debug("Could not bind macOS ReopenApplication: %s", e)

    def _start_ipc_server(self):
        """Listens on localhost for wake-up commands when user opens shortcut."""
        port = get_ipc_port(self.profile)
        def server_loop():
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", port))
                srv.listen(2)
                while True:
                    conn, _ = srv.accept()
                    data = conn.recv(64)
                    conn.close()
                    if b"SHOW" in data:
                        logger.info("Received wake-up signal from secondary instance [%s]. Restoring window...", self.profile)
                        self.root.after(0, self.show_window_from_tray)
            except Exception as e:
                logger.debug("IPC server loop [%s] stopped: %s", self.profile, e)

        t = threading.Thread(target=server_loop, daemon=True)
        t.start()

    def _on_window_configure(self, event):
        """Records resize timestamp to pause heavy canvas draws during window drag."""
        if event.widget == self.root:
            self._last_resize_time = time.time()

    # -------------------------------------------------------------
    # Top Navigation Header
    # -------------------------------------------------------------
    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=16, pady=(12, 6))

        # Title / Brand
        header_text = t("app_title") if self.profile == "default" else f"{t('app_title')} [{self.profile}]"
        self.header_title = ctk.CTkLabel(
            self.header_frame,
            text=header_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_WHITE
        )
        self.header_title.pack(side="left")

        # View Toggle Button (⚙️ Settings / ← Dashboard)
        self.nav_btn = ctk.CTkButton(
            self.header_frame,
            text=t("nav_settings"),
            width=110,
            height=28,
            corner_radius=6,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            font=ctk.CTkFont(size=12),
            command=self.toggle_view
        )
        self.nav_btn.pack(side="right")

    def toggle_view(self):
        if self.current_view == "dashboard":
            self.show_settings()
        else:
            self.show_dashboard()

    def show_dashboard(self):
        self.current_view = "dashboard"
        self.settings_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.nav_btn.configure(text=t("nav_settings"))
        self._update_status_banner()
        self._update_dashboard_summary()

    def show_settings(self):
        self.current_view = "settings"
        self.dashboard_frame.pack_forget()
        self.settings_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.nav_btn.configure(text=t("nav_dashboard"))
        self._update_settings_lock_state(force=True)

    # -------------------------------------------------------------
    # 1. Dashboard View (Simple, Focused, Zero-Clutter)
    # -------------------------------------------------------------
    def _build_dashboard_view(self):
        self.dashboard_frame = ctk.CTkFrame(self.root, fg_color="transparent")

        # 1. Status Banner
        self.status_banner = ctk.CTkFrame(
            self.dashboard_frame,
            fg_color=COLOR_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        self.status_banner.pack(fill="x", pady=(0, 10))

        status_inner = ctk.CTkFrame(self.status_banner, fg_color="transparent")
        status_inner.pack(fill="x", padx=16, pady=12)

        self.status_title = ctk.CTkLabel(
            status_inner,
            text="● STANDBY",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLOR_GREEN,
            anchor="w"
        )
        self.status_title.pack(fill="x")

        self.status_subtitle = ctk.CTkLabel(
            status_inner,
            text="Calculating next scheduled recording...",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.status_subtitle.pack(fill="x", pady=(2, 0))

        # 2. Audio Level Meter (Zero-Allocation Canvas)
        meter_panel = ctk.CTkFrame(
            self.dashboard_frame,
            fg_color=COLOR_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        meter_panel.pack(fill="x", pady=(0, 10))

        meter_inner = ctk.CTkFrame(meter_panel, fg_color="transparent")
        meter_inner.pack(fill="x", padx=14, pady=10)

        meter_head = ctk.CTkFrame(meter_inner, fg_color="transparent")
        meter_head.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            meter_head,
            text="Audio Level",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE
        ).pack(side="left")

        self.meter_numeric_lbl = ctk.CTkLabel(
            meter_head,
            text="L: -60.0 dBFS | R: -60.0 dBFS",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.meter_numeric_lbl.pack(side="right")

        # Canvas for L and R level bars
        self.meter_canvas_height = 34
        self.meter_canvas = tk.Canvas(
            meter_inner,
            height=self.meter_canvas_height,
            bg=COLOR_PANEL,
            highlightthickness=0
        )
        self.meter_canvas.pack(fill="x")

        # Pre-allocate canvas elements once
        bar_h = 13
        self.y_l = 2
        self.y_r = 17

        self.track_l = self.meter_canvas.create_rectangle(0, self.y_l, 1000, self.y_l + bar_h, fill="#0A0A0C", outline="")
        self.track_r = self.meter_canvas.create_rectangle(0, self.y_r, 1000, self.y_r + bar_h, fill="#0A0A0C", outline="")

        self.bar_l_green = self.meter_canvas.create_rectangle(0, self.y_l, 0, self.y_l + bar_h, fill=COLOR_GREEN, outline="")
        self.bar_l_amber = self.meter_canvas.create_rectangle(0, self.y_l, 0, self.y_l + bar_h, fill=COLOR_AMBER, outline="")
        self.bar_l_red   = self.meter_canvas.create_rectangle(0, self.y_l, 0, self.y_l + bar_h, fill=COLOR_RED, outline="")

        self.bar_r_green = self.meter_canvas.create_rectangle(0, self.y_r, 0, self.y_r + bar_h, fill=COLOR_GREEN, outline="")
        self.bar_r_amber = self.meter_canvas.create_rectangle(0, self.y_r, 0, self.y_r + bar_h, fill=COLOR_AMBER, outline="")
        self.bar_r_red   = self.meter_canvas.create_rectangle(0, self.y_r, 0, self.y_r + bar_h, fill=COLOR_RED, outline="")

        self.meter_canvas.create_text(8, self.y_l + bar_h // 2, text="L", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), anchor="w")
        self.meter_canvas.create_text(8, self.y_r + bar_h // 2, text="R", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), anchor="w")

        # 3. Read-Only Summary Info Card
        summary_panel = ctk.CTkFrame(
            self.dashboard_frame,
            fg_color=COLOR_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        summary_panel.pack(fill="x", pady=(0, 12))

        summary_inner = ctk.CTkFrame(summary_panel, fg_color="transparent")
        summary_inner.pack(fill="x", padx=14, pady=10)

        self.sum_mic_lbl = ctk.CTkLabel(
            summary_inner,
            text="🎤  Input: Default Audio Device",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_WHITE,
            anchor="w"
        )
        self.sum_mic_lbl.pack(fill="x", pady=(0, 3))

        self.sum_sch_lbl = ctk.CTkLabel(
            summary_inner,
            text="⏰  Schedules: Loading...",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_WHITE,
            anchor="w"
        )
        self.sum_sch_lbl.pack(fill="x", pady=(0, 3))

        self.sum_disk_lbl = ctk.CTkLabel(
            summary_inner,
            text="📁  Storage: Calculating free space...",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_GREEN,
            anchor="w"
        )
        self.sum_disk_lbl.pack(fill="x")

        # 4. Primary Big Action Button
        self.action_btn = ctk.CTkButton(
            self.dashboard_frame,
            text="🔴 Start Manual Recording",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            corner_radius=8,
            fg_color=COLOR_RED,
            hover_color=COLOR_RED_HOVER,
            command=self.toggle_manual_recording
        )
        self.action_btn.pack(fill="x")

    def _update_dashboard_summary(self):
        """Updates the read-only summary card on the Dashboard."""
        # Mic Device
        cur_mic = self.config.get("input_device_name", "")
        if not cur_mic:
            cur_mic = self.input_device_combo.get() if hasattr(self, "input_device_combo") else "Default"
        self.sum_mic_lbl.configure(text=f"🎤  {t('sec_audio_device')} {cur_mic}")

        # Schedules summary
        if not self.scheduler.enabled:
            self.sum_sch_lbl.configure(text=f"⏰  {t('sum_schedule')} {t('sum_schedules_disabled')}", justify="left")
        else:
            slots = self.scheduler.slots
            if slots:
                parts = []
                for s in slots:
                    days = s.get("days", ["All"])
                    if "All" in days or len(days) == 7:
                        d_str = t("sum_daily")
                    elif len(days) == 1:
                        d_str = days[0]
                    elif set(days) == {"Mon", "Tue", "Wed", "Thu", "Fri"}:
                        d_str = "Mon–Fri"
                    elif set(days) == {"Sat", "Sun"}:
                        d_str = "Sat–Sun"
                    else:
                        d_str = ",".join(days)
                    lbl = s.get("label", "").strip()
                    prefix = f"{lbl}: " if lbl else ""
                    parts.append(f"{prefix}{s['start']}–{s['end']} ({d_str})")
                if len(parts) == 1:
                    self.sum_sch_lbl.configure(text=f"⏰  {t('sum_schedule')} {parts[0]}", justify="left")
                else:
                    bullets = "\n".join([f"    • {p}" for p in parts])
                    self.sum_sch_lbl.configure(text=f"⏰  {t('sum_schedule')}\n{bullets}", justify="left")
            else:
                self.sum_sch_lbl.configure(text=f"⏰  {t('sum_schedule')} {t('sum_no_upcoming')}", justify="left")

        # Disk
        folder = self.config.get("backup_folder", "")
        grouping = self.config.get("folder_grouping", "monthly")
        grouping_key = f"group_{grouping}"
        grouping_display = t(grouping_key) if grouping_key in ["group_monthly", "group_daily", "group_weekly", "group_none"] else grouping.capitalize()
        free_gb = get_free_disk_space_gb(folder)
        safety_floor_gb, warning_floor_gb = get_disk_safety_floors(folder)
        if free_gb < safety_floor_gb:
            color = COLOR_RED
        elif free_gb < warning_floor_gb:
            color = COLOR_AMBER
        else:
            color = COLOR_GREEN
        self.sum_disk_lbl.configure(text=f"📁  {t('sum_storage')} {t('sum_free', free_gb=free_gb)}  ({folder} • {grouping_display})", text_color=color)

    # -------------------------------------------------------------
    # 2. Settings View (Dedicated Configuration Panel)
    # -------------------------------------------------------------
    def _build_settings_view(self):
        self.settings_frame = ctk.CTkFrame(self.root, fg_color="transparent")

        # Scrollable Container Panel for all settings
        self.settings_scroll = ctk.CTkScrollableFrame(
            self.settings_frame,
            fg_color=COLOR_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        self.settings_scroll.pack(fill="both", expand=True)
        self._bind_touchpad_scroll()

        # Settings Lock Banner (Displayed when active recording is underway)
        self.settings_lock_banner = ctk.CTkFrame(
            self.settings_scroll,
            fg_color="#332200",
            border_width=1,
            border_color="#B8860B",
            corner_radius=6
        )
        self.lock_banner_lbl = ctk.CTkLabel(
            self.settings_lock_banner,
            text=t("settings_locked_banner"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFD700",
            wraplength=480
        )
        self.lock_banner_lbl.pack(padx=12, pady=8)

        # Section 1: Audio Input Device
        self.sec_mic_head = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        self.sec_mic_head.pack(fill="x", padx=16, pady=(12, 4))

        self.sec_mic_lbl = ctk.CTkLabel(
            self.sec_mic_head,
            text=t("sec_audio_device"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE
        )
        self.sec_mic_lbl.pack(side="left")

        self.rescan_btn = ctk.CTkButton(
            self.sec_mic_head,
            text=f"🔄 {t('btn_refresh')}",
            width=80,
            height=22,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            font=ctk.CTkFont(size=11),
            command=self.refresh_devices_list
        )
        self.rescan_btn.pack(side="right")

        self.input_device_combo = ctk.CTkComboBox(
            self.settings_scroll,
            values=["Searching audio devices..."],
            height=30,
            command=self.on_input_device_changed
        )
        self.input_device_combo.pack(fill="x", padx=16, pady=(0, 12))

        # Section 2: Multi-Slot Daily Schedules
        sch_head = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        sch_head.pack(fill="x", padx=16, pady=(0, 4))

        self.sec_sch_lbl = ctk.CTkLabel(
            sch_head,
            text=t("sec_schedules"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE
        )
        self.sec_sch_lbl.pack(side="left")

        # Master Enable/Disable Toggle
        self.sched_enabled_var = ctk.BooleanVar(value=self.scheduler.enabled)
        self.sched_enabled_chk = ctk.CTkCheckBox(
            sch_head,
            text=t("opt_schedule_master"),
            variable=self.sched_enabled_var,
            font=ctk.CTkFont(size=11),
            command=self.on_toggle_schedule_enabled
        )
        self.sched_enabled_chk.pack(side="right")

        # Container for time slots
        self.slots_frame = ctk.CTkFrame(
            self.settings_scroll,
            fg_color="#141417",
            corner_radius=6,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        self.slots_frame.pack(fill="x", padx=16, pady=(0, 6))

        # Dynamic slot row tracking
        self.slot_rows = []
        self._populate_slot_rows()

        # Slot action buttons (Add, Save)
        sch_actions = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        sch_actions.pack(fill="x", padx=16, pady=(0, 12))

        self.add_slot_btn = ctk.CTkButton(
            sch_actions,
            text=t("btn_add_slot"),
            width=120,
            height=26,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            font=ctk.CTkFont(size=11),
            command=self.on_add_slot_clicked
        )
        self.add_slot_btn.pack(side="left", padx=(0, 8))

        self.save_sch_btn = ctk.CTkButton(
            sch_actions,
            text=t("btn_save_schedules"),
            width=130,
            height=26,
            state="disabled",
            fg_color="#2A2A30",
            hover_color="#2A2A30",
            text_color="#8E8E93",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.on_save_schedules_clicked
        )
        self.save_sch_btn.pack(side="left")

        # Section 3: Backup Directory & Retention
        self.sec_storage_lbl = ctk.CTkLabel(
            self.settings_scroll,
            text=t("sec_storage"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE,
            anchor="w"
        )
        self.sec_storage_lbl.pack(fill="x", padx=16, pady=(0, 4))

        f_row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        f_row.pack(fill="x", padx=16, pady=(0, 6))

        self.folder_entry = ctk.CTkEntry(f_row, height=28)
        self.folder_entry.insert(0, self.config.get("backup_folder", ""))
        self.folder_entry.configure(state="readonly")
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.browse_btn = ctk.CTkButton(
            f_row,
            text=t("btn_browse"),
            width=75,
            height=28,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            command=self.on_browse_folder
        )
        self.browse_btn.pack(side="left", padx=(0, 6))

        self.open_folder_btn = ctk.CTkButton(
            f_row,
            text="📂 Open",
            width=65,
            height=28,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            command=self.on_open_folder
        )
        self.open_folder_btn.pack(side="left")

        # Retention Days
        ret_row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        ret_row.pack(fill="x", padx=16, pady=(0, 2))

        self.sec_retention_lbl = ctk.CTkLabel(
            ret_row,
            text=t("sec_retention"),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.sec_retention_lbl.pack(side="left", padx=(0, 6))

        self.retention_entry = ctk.CTkEntry(ret_row, width=40, height=24)
        self.retention_entry.insert(0, str(self.config.get("retention_days", 30)))
        self.retention_entry.pack(side="left", padx=(0, 6))

        self.retention_hint_lbl = ctk.CTkLabel(
            self.settings_scroll,
            text=t("retention_hint"),
            font=ctk.CTkFont(size=10),
            text_color="#8E8E93",
            anchor="w",
            justify="left"
        )
        self.retention_hint_lbl.pack(fill="x", padx=16, pady=(0, 8))

        # File Naming Format
        naming_head = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        naming_head.pack(fill="x", padx=16, pady=(0, 4))

        self.sec_naming_lbl = ctk.CTkLabel(
            naming_head,
            text=t("sec_naming"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE
        )
        self.sec_naming_lbl.pack(side="left")

        self.naming_tokens_lbl = ctk.CTkLabel(
            naming_head,
            text=t("naming_tokens"),
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED
        )
        self.naming_tokens_lbl.pack(side="right")

        naming_row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        naming_row.pack(fill="x", padx=16, pady=(0, 4))

        current_pat = self.config.get("filename_pattern", "Audio_Backup_{date}_{time}")
        self.naming_entry = ctk.CTkEntry(naming_row, height=28, font=ctk.CTkFont(family="Consolas", size=11))
        self.naming_entry.insert(0, current_pat)
        self.naming_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.naming_entry.bind("<KeyRelease>", self._on_naming_pattern_changed)

        self.save_naming_btn = ctk.CTkButton(
            naming_row,
            text="💾 Save",
            width=65,
            height=28,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            font=ctk.CTkFont(size=11),
            command=self.on_save_naming_pattern
        )
        self.save_naming_btn.pack(side="left")

        from config_manager import format_recording_filename
        initial_preview = format_recording_filename(current_pat)
        self.naming_preview_lbl = ctk.CTkLabel(
            self.settings_scroll,
            text=t("naming_preview", preview=initial_preview),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_GREEN,
            anchor="w"
        )
        self.naming_preview_lbl.pack(fill="x", padx=16, pady=(0, 6))

        # Companion Audio Export Format
        comp_frame = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        comp_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.sec_comp_lbl = ctk.CTkLabel(
            comp_frame,
            text=t("opt_companion_format"),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.sec_comp_lbl.pack(side="left", padx=(0, 8))

        self.companion_format_map = {
            t("fmt_mp3"): "mp3",
            t("fmt_wav"): "wav",
            t("fmt_ogg"): "ogg",
            t("fmt_none"): "none"
        }
        self.companion_format_reverse_map = {v: k for k, v in self.companion_format_map.items()}

        cur_comp = self.config.get("companion_format")
        if not cur_comp:
            cur_comp = "mp3" if self.config.get("auto_export_mp3", True) else "none"

        comp_display = self.companion_format_reverse_map.get(cur_comp, t("fmt_mp3"))

        self.companion_combo = ctk.CTkComboBox(
            comp_frame,
            values=list(self.companion_format_map.keys()),
            width=210,
            height=26,
            command=self.on_companion_format_changed
        )
        self.companion_combo.set(comp_display)
        self.companion_combo.pack(side="left")

        # Folder Grouping Options
        group_frame = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        group_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.sec_group_lbl = ctk.CTkLabel(
            group_frame,
            text=t("sec_folder_grouping"),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.sec_group_lbl.pack(side="left", padx=(0, 8))

        self.grouping_options = {
            "Monthly (YYYY-MM)": "monthly",
            "Daily (YYYY-MM-DD)": "daily",
            "Weekly (YYYY-Www)": "weekly",
            "None (Flat)": "none"
        }
        self.rev_grouping_options = {v: k for k, v in self.grouping_options.items()}

        current_grp = self.config.get("folder_grouping", "monthly")
        current_display = self.rev_grouping_options.get(current_grp, "Monthly (YYYY-MM)")

        self.folder_grouping_menu = ctk.CTkOptionMenu(
            group_frame,
            values=list(self.grouping_options.keys()),
            width=180,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.on_folder_grouping_changed
        )
        self.folder_grouping_menu.set(current_display)
        self.folder_grouping_menu.pack(side="left")

        # Section 4: System Options
        self.sec_system_lbl = ctk.CTkLabel(
            self.settings_scroll,
            text=t("sec_system"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE,
            anchor="w"
        )
        self.sec_system_lbl.pack(fill="x", padx=16, pady=(0, 6))

        opts_frame = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        opts_frame.pack(fill="x", padx=16, pady=(0, 16))

        # Language Selector Row
        lang_row = ctk.CTkFrame(opts_frame, fg_color="transparent")
        lang_row.pack(fill="x", pady=(0, 6))

        self.lang_lbl = ctk.CTkLabel(
            lang_row,
            text=t("opt_language"),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_WHITE
        )
        self.lang_lbl.pack(side="left", padx=(0, 8))

        lang_options = list(SUPPORTED_LANGUAGES.values())
        cur_lang_code = get_current_language()
        cur_lang_display = SUPPORTED_LANGUAGES.get(cur_lang_code, "English")

        self.lang_menu = ctk.CTkOptionMenu(
            lang_row,
            values=lang_options,
            width=160,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.on_language_changed
        )
        self.lang_menu.set(cur_lang_display)
        self.lang_menu.pack(side="left")

        self.startup_var = ctk.BooleanVar(value=is_autostart_enabled(profile=self.profile))
        os_label = "Windows" if sys.platform == "win32" else "macOS" if sys.platform == "darwin" else "Linux" if sys.platform.startswith("linux") else "System"
        self.startup_chk = ctk.CTkCheckBox(
            opts_frame,
            text=f"{t('opt_autostart')} ({os_label})",
            variable=self.startup_var,
            font=ctk.CTkFont(size=12),
            command=self.on_startup_toggled
        )
        self.startup_chk.pack(anchor="w", pady=(0, 4))

        self.mono_switch_var = ctk.BooleanVar(value=self.config.get("mono_sum", True))
        self.mono_switch = ctk.CTkCheckBox(
            opts_frame,
            text=t("opt_mono_sum"),
            variable=self.mono_switch_var,
            font=ctk.CTkFont(size=12),
            command=self.on_mono_switch_toggled
        )
        self.mono_switch.pack(anchor="w", pady=(0, 4))

        self.monitor_switch_var = ctk.BooleanVar(value=False)
        self.monitor_switch = ctk.CTkCheckBox(
            opts_frame,
            text=f"🎧 {t('opt_headphone')}",
            variable=self.monitor_switch_var,
            font=ctk.CTkFont(size=12),
            command=self.on_monitor_switch_toggled
        )
        self.monitor_switch.pack(anchor="w", pady=(0, 8))

        # Open Log File action row
        log_row = ctk.CTkFrame(opts_frame, fg_color="transparent")
        log_row.pack(fill="x", pady=(2, 0))

        self.open_log_btn = ctk.CTkButton(
            log_row,
            text=t("btn_open_log"),
            width=180,
            height=28,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            font=ctk.CTkFont(size=11),
            command=self.on_open_log_file
        )
        self.open_log_btn.pack(side="left")

        # Section 5: Audio Profiles (Multi-Tenancy / Second Audio Input)
        self.sec_prof_lbl = ctk.CTkLabel(
            self.settings_scroll,
            text=t("sec_profiles"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_WHITE,
            anchor="w"
        )
        self.sec_prof_lbl.pack(fill="x", padx=16, pady=(14, 2))

        self.sec_prof_desc = ctk.CTkLabel(
            self.settings_scroll,
            text=t("sec_profiles_desc"),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.sec_prof_desc.pack(fill="x", padx=16, pady=(0, 8))

        # Container frame for profile list rows
        self.profiles_container = ctk.CTkFrame(
            self.settings_scroll,
            fg_color=COLOR_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_PANEL_BORDER
        )
        self.profiles_container.pack(fill="x", padx=16, pady=(0, 10))

        # Add Profile Button
        self.add_profile_btn = ctk.CTkButton(
            self.settings_scroll,
            text=t("btn_add_profile"),
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30,
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            command=self.on_show_add_profile_dialog
        )
        self.add_profile_btn.pack(anchor="w", padx=16, pady=(0, 20))

        self._populate_profiles_list()
        self._update_settings_lock_state(force=True)

    def _update_settings_lock_state(self, force: bool = False):
        """
        Locks critical settings when audio recording is active.
        Prevents PortAudio stream destruction, disk path mutations, and schedule race conditions.
        """
        is_rec = bool(getattr(self.audio, "is_recording", False))
        if not force and getattr(self, "_last_settings_locked_state", None) == is_rec:
            return
        self._last_settings_locked_state = is_rec

        # Show or hide settings lock banner
        if hasattr(self, "settings_lock_banner") and hasattr(self, "sec_mic_head"):
            if is_rec:
                self.settings_lock_banner.pack(fill="x", padx=16, pady=(10, 8), before=self.sec_mic_head)
            else:
                self.settings_lock_banner.pack_forget()

        # State string for UI inputs
        state_str = "disabled" if is_rec else "normal"

        # 1. Audio input device controls
        if hasattr(self, "input_device_combo"):
            self.input_device_combo.configure(state=state_str)
        if hasattr(self, "rescan_btn"):
            self.rescan_btn.configure(state=state_str)

        # 2. Storage & File naming controls
        if hasattr(self, "browse_btn"):
            self.browse_btn.configure(state=state_str)
        if hasattr(self, "retention_entry"):
            self.retention_entry.configure(state=state_str)
        if hasattr(self, "naming_entry"):
            self.naming_entry.configure(state=state_str)
        if hasattr(self, "save_naming_btn"):
            self.save_naming_btn.configure(state=state_str)
        if hasattr(self, "companion_combo"):
            self.companion_combo.configure(state=state_str)
        if hasattr(self, "folder_grouping_menu"):
            self.folder_grouping_menu.configure(state=state_str)

        # 3. Schedule controls
        if hasattr(self, "sched_enabled_chk"):
            self.sched_enabled_chk.configure(state=state_str)
        if hasattr(self, "add_slot_btn"):
            self.add_slot_btn.configure(state=state_str)
        if hasattr(self, "save_sch_btn"):
            if is_rec:
                self.save_sch_btn.configure(state="disabled")
            else:
                if getattr(self, "_schedules_dirty", False):
                    self.save_sch_btn.configure(
                        state="normal",
                        fg_color=COLOR_GREEN,
                        hover_color=COLOR_GREEN_HOVER,
                        text_color="#FFFFFF"
                    )
                else:
                    self.save_sch_btn.configure(
                        state="disabled",
                        fg_color="#2A2A30",
                        hover_color="#2A2A30",
                        text_color="#8E8E93"
                    )

        # Slot row elements
        if hasattr(self, "slot_rows"):
            for row in self.slot_rows:
                if "start_entry" in row:
                    row["start_entry"].configure(state=state_str)
                if "end_entry" in row:
                    row["end_entry"].configure(state=state_str)
                if "label_entry" in row:
                    row["label_entry"].configure(state=state_str)
                if "all_btn" in row and row["all_btn"]:
                    row["all_btn"].configure(state=state_str)
                if "del_btn" in row and row["del_btn"]:
                    row["del_btn"].configure(state=state_str)
                if "day_buttons" in row and row["day_buttons"]:
                    for d_btn in row["day_buttons"].values():
                        d_btn.configure(state=state_str)

        # 4. Profiles controls
        if hasattr(self, "add_profile_btn"):
            self.add_profile_btn.configure(state=state_str)

    def _populate_profiles_list(self):
        """Populates the profiles container with cards for each configured profile."""
        for child in self.profiles_container.winfo_children():
            child.destroy()

        profiles = list_available_profiles()
        for idx, prof in enumerate(profiles):
            pid = prof["id"]
            pname = prof["name"]
            is_active_window = (pid == self.profile)
            running = is_active_window or is_profile_running(pid)

            row = ctk.CTkFrame(self.profiles_container, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=6)

            # Left side: Name, Active Badge, Status
            left_f = ctk.CTkFrame(row, fg_color="transparent")
            left_f.pack(side="left", fill="x", expand=True)

            status_color = COLOR_GREEN if running else COLOR_TEXT_MUTED
            status_text = t("status_running") if running else t("status_inactive")
            if is_active_window:
                name_display = f"{pname}  {t('active_badge')}"
            else:
                name_display = pname

            ctk.CTkLabel(
                left_f,
                text=name_display,
                font=ctk.CTkFont(size=12, weight="bold" if is_active_window else "normal"),
                text_color=COLOR_TEXT_WHITE if is_active_window else COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(side="left", padx=(0, 10))

            ctk.CTkLabel(
                left_f,
                text=status_text,
                font=ctk.CTkFont(size=10),
                text_color=status_color
            ).pack(side="left")

            # Right side: Action buttons
            right_f = ctk.CTkFrame(row, fg_color="transparent")
            right_f.pack(side="right")

            # 1. Desktop Shortcut button
            ctk.CTkButton(
                right_f,
                text=f"🖥️ {t('btn_shortcut')}",
                width=115,
                height=24,
                font=ctk.CTkFont(size=10),
                fg_color="#2A2A30",
                hover_color=COLOR_PANEL_BORDER,
                command=lambda p_id=pid, p_name=pname: self._on_create_profile_shortcut(p_id, p_name)
            ).pack(side="left", padx=(0, 6))

            # 2. Launch / Show button (not needed for active window)
            if not is_active_window:
                ctk.CTkButton(
                    right_f,
                    text=t("btn_open_window"),
                    width=105,
                    height=24,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=COLOR_BLUE if not running else COLOR_GREEN,
                    hover_color="#2563EB",
                    command=lambda p_id=pid: self._on_launch_profile_instance(p_id)
                ).pack(side="left", padx=(0, 6))

            # 3. Delete button (only for custom inactive profiles)
            if pid != "default" and not is_active_window:
                del_btn = ctk.CTkButton(
                    right_f,
                    text="✕",
                    width=24,
                    height=24,
                    font=ctk.CTkFont(size=11),
                    fg_color="#2A2A30",
                    hover_color="#7F1D1D",
                    command=lambda p_id=pid, p_name=pname: self._on_delete_profile(p_id, p_name)
                )
                if running or self.audio.is_recording:
                    del_btn.configure(state="disabled", text_color="#555555")
                del_btn.pack(side="left")

    def _on_create_profile_shortcut(self, profile_id: str, display_name: str):
        success = create_desktop_shortcut(profile=profile_id, display_name=display_name)
        if success:
            messagebox.showinfo("Shortcut Created", f"Desktop shortcut created successfully for '{display_name}'!")
        else:
            messagebox.showerror("Error", f"Could not create desktop shortcut for '{display_name}'.")

    def _on_launch_profile_instance(self, profile_id: str):
        if is_profile_running(profile_id):
            signal_existing_instance(profile_id)
        else:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--profile", profile_id]
            elif sys.platform == "darwin" and Path("/Applications/AudioGuard.app").exists():
                cmd = ["open", "-n", "/Applications/AudioGuard.app", "--args", "--profile", profile_id]
            else:
                cmd = [sys.executable, os.path.abspath(sys.argv[0]), "--profile", profile_id]
            try:
                subprocess.Popen(cmd)
                self.root.after(1000, self._populate_profiles_list)
            except Exception as e:
                logger.error("Failed to launch profile %s: %s", profile_id, e)
                messagebox.showerror("Error", f"Failed to launch profile window:\n{e}")

    def _on_delete_profile(self, profile_id: str, display_name: str):
        if self.audio.is_recording:
            messagebox.showwarning("Recording Active", "Cannot delete profiles while a recording is in progress.")
            return

        if is_profile_running(profile_id):
            messagebox.showwarning("Profile Running", f"Profile '{display_name}' is currently running.\nPlease close its window before deleting it.")
            return

        confirm = messagebox.askyesno(
            t("dlg_delete_prof_title"),
            t("dlg_delete_prof_msg", name=display_name),
            icon="warning"
        )
        if confirm:
            delete_profile(profile_id)
            self._populate_profiles_list()

    def on_show_add_profile_dialog(self):
        """Displays modal dialog to configure and launch a Second Audio Input profile."""
        if self.audio.is_recording:
            messagebox.showwarning("Recording Active", "Cannot configure profiles while a recording is in progress.")
            return
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(t("dlg_add_prof_title"))
        dlg.geometry("480x440")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        try:
            x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - 440) // 2
            dlg.geometry(f"+{x}+{y}")
        except Exception:
            pass

        content = ctk.CTkFrame(dlg, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # 1. Profile Name
        ctk.CTkLabel(content, text=t("lbl_prof_name"), font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", pady=(0, 2))
        name_entry = ctk.CTkEntry(content, font=ctk.CTkFont(size=12))
        name_entry.insert(0, "Second Audio Input")
        name_entry.pack(fill="x", pady=(0, 10))

        # 2. Select Audio Input Device
        ctk.CTkLabel(content, text=t("lbl_prof_device"), font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", pady=(0, 2))
        raw_devices = self.audio.get_input_devices()
        device_names = [d["name"] for d in raw_devices] if raw_devices else ["Default Audio Device"]
        current_used_device = self.config.get("input_device_name", "")
        sel_idx = 0
        if len(device_names) > 1:
            for i, d in enumerate(device_names):
                if d != current_used_device:
                    sel_idx = i
                    break
        device_menu = ctk.CTkOptionMenu(content, values=device_names, font=ctk.CTkFont(size=11))
        device_menu.set(device_names[sel_idx])
        device_menu.pack(fill="x", pady=(0, 10))

        # 3. Storage Folder
        ctk.CTkLabel(content, text=t("lbl_prof_folder"), font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", pady=(0, 2))
        folder_frame = ctk.CTkFrame(content, fg_color="transparent")
        folder_frame.pack(fill="x", pady=(0, 12))

        def_folder = self.config.get("backup_folder", "") or get_default_backup_folder()
        suggested_folder = str(Path(def_folder) / "Second_Audio_Input")
        folder_entry = ctk.CTkEntry(folder_frame, font=ctk.CTkFont(size=11))
        folder_entry.insert(0, suggested_folder)
        folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _browse_dlg_folder():
            chosen = filedialog.askdirectory(initialdir=def_folder, title="Select Storage Directory")
            if chosen:
                folder_entry.delete(0, "end")
                folder_entry.insert(0, chosen)

        ctk.CTkButton(folder_frame, text=t("btn_browse"), width=70, font=ctk.CTkFont(size=11), command=_browse_dlg_folder).pack(side="left")

        # 4. Checkboxes
        launch_now_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text=t("chk_launch_now"), variable=launch_now_var, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 4))

        shortcut_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text=t("chk_create_shortcut"), variable=shortcut_var, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 4))

        autostart_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text=t("chk_autostart_boot"), variable=autostart_var, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 14))

        # 5. Buttons
        btn_box = ctk.CTkFrame(content, fg_color="transparent")
        btn_box.pack(fill="x")

        def _on_confirm_create():
            raw_name = name_entry.get().strip()
            if not raw_name:
                raw_name = "Second Audio Input"

            raw_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_name.lower()).strip('_')
            slug = raw_slug if raw_slug else f"second_input_{int(time.time()) % 1000}"
            if slug == "default":
                slug = "second_input"

            chosen_dev = device_menu.get()
            chosen_folder = folder_entry.get().strip() or def_folder

            new_mgr = ConfigManager(profile=slug)
            new_mgr.set("profile_display_name", raw_name)
            new_mgr.set("input_device_name", chosen_dev)
            new_mgr.set("backup_folder", chosen_folder)
            new_mgr.set("filename_pattern", f"Audio_Backup_{slug}_{{date}}_{{time}}")
            new_mgr.save()

            if autostart_var.get():
                set_autostart(True, profile=slug)

            if shortcut_var.get():
                create_desktop_shortcut(profile=slug, display_name=raw_name)

            dlg.destroy()
            self._populate_profiles_list()

            if launch_now_var.get():
                self.root.after(300, lambda: self._on_launch_profile_instance(slug))

        ctk.CTkButton(
            btn_box,
            text=t("btn_create_profile"),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_GREEN,
            hover_color=COLOR_GREEN_HOVER,
            command=_on_confirm_create
        ).pack(side="right")

        ctk.CTkButton(
            btn_box,
            text="Cancel",
            font=ctk.CTkFont(size=12),
            fg_color="#2A2A30",
            hover_color=COLOR_PANEL_BORDER,
            command=dlg.destroy
        ).pack(side="right", padx=(0, 8))

    def _bind_touchpad_scroll(self):
        """
        Binds modern Tk 9 <TouchpadScroll> events (TIP 684) so macOS and Windows
        precision trackpads can scroll the settings view smoothly with two-finger gestures.
        """
        def _on_touchpad_scroll(event):
            if self.current_view != "settings":
                return
            canvas = getattr(self.settings_scroll, "_parent_canvas", None)
            if canvas is None or not canvas.winfo_exists():
                return

            # Decode 32-bit packed signed 16-bit delta values (TIP 684)
            # High 16 bits = delta_x (horizontal), Low 16 bits = delta_y (vertical)
            raw = int(getattr(event, "delta", 0) or 0) & 0xFFFFFFFF
            delta_y = raw & 0xFFFF
            if delta_y >= 0x8000:
                delta_y -= 0x10000

            if delta_y != 0:
                bbox = canvas.bbox("all")
                if bbox:
                    total_h = bbox[3] - bbox[1]
                    if total_h > 0:
                        top, _ = canvas.yview()
                        # Smooth 1:1 pixel-to-trackpad scaling (prevents high-frequency multi-line jumping)
                        fraction_step = (-delta_y * 0.75) / total_h
                        canvas.yview_moveto(top + fraction_step)

        try:
            self.root.bind_all("<TouchpadScroll>", _on_touchpad_scroll, add="+")
        except Exception as e:
            logger.debug("Could not bind <TouchpadScroll>: %s", e)

    # -------------------------------------------------------------
    # Multi-Slot Schedule Rows UI Helpers (with Day-of-Week Toggles)
    # -------------------------------------------------------------
    def _mark_schedules_dirty(self):
        """Activates the Save Schedules button when any changes are made."""
        self._schedules_dirty = True
        if hasattr(self, "save_sch_btn"):
            self.save_sch_btn.configure(
                state="normal",
                fg_color=COLOR_GREEN,
                hover_color=COLOR_GREEN_HOVER,
                text_color="#FFFFFF"
            )

    def _mark_schedules_clean(self):
        """Disables the Save Schedules button when there are no unsaved changes."""
        self._schedules_dirty = False
        if hasattr(self, "save_sch_btn"):
            self.save_sch_btn.configure(
                state="disabled",
                fg_color="#2A2A30",
                hover_color="#2A2A30",
                text_color="#8E8E93"
            )

    def _populate_slot_rows(self):
        """Populates the frame with slot rows from scheduler.slots."""
        for item in self.slot_rows:
            item["frame"].destroy()
        self.slot_rows.clear()

        slots = self.scheduler.slots
        if not slots:
            slots = [{"start": "18:00", "end": "21:00", "days": ["All"], "label": ""}]

        for s in slots:
            self._create_slot_row(
                s.get("start", "18:00"),
                s.get("end", "21:00"),
                s.get("days", ["All"]),
                s.get("label", "")
            )
        self._mark_schedules_clean()

    def _create_slot_row(self, start_val: str, end_val: str, days_val: Optional[List[str]] = None, label_val: str = ""):
        row = ctk.CTkFrame(self.slots_frame, fg_color="transparent")
        row.pack(fill="x", pady=3, padx=4)

        ctk.CTkLabel(row, text="From", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 3))
        st_entry = ctk.CTkEntry(row, width=54, height=24, font=ctk.CTkFont(size=11))
        st_entry.insert(0, start_val)
        st_entry.pack(side="left", padx=(0, 4))
        st_entry.bind("<KeyRelease>", lambda e: self._mark_schedules_dirty())

        ctk.CTkLabel(row, text="to", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 3))
        et_entry = ctk.CTkEntry(row, width=54, height=24, font=ctk.CTkFont(size=11))
        et_entry.insert(0, end_val)
        et_entry.pack(side="left", padx=(0, 6))
        et_entry.bind("<KeyRelease>", lambda e: self._mark_schedules_dirty())

        # Days of Week container
        days_box = ctk.CTkFrame(row, fg_color="transparent")
        days_box.pack(side="left", padx=(0, 6))

        day_vars = {}
        day_buttons = {}
        all_days_keys = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        normalized_days = days_val if days_val is not None else ["All"]
        is_all_active = ("All" in normalized_days) or (len(normalized_days) == 7)

        def _update_all_btn():
            all_on = all(day_vars[k].get() for k in all_days_keys)
            all_btn.configure(
                fg_color=COLOR_GREEN if all_on else "#2A2A30",
                text_color="#FFFFFF" if all_on else "#8E8E93"
            )

        def _on_day_clicked(k):
            new_state = not day_vars[k].get()
            day_vars[k].set(new_state)
            day_buttons[k].configure(
                fg_color=COLOR_GREEN if new_state else "#2A2A30",
                text_color="#FFFFFF" if new_state else "#8E8E93"
            )
            _update_all_btn()
            self._mark_schedules_dirty()

        def _on_all_clicked():
            current_all = all(day_vars[k].get() for k in all_days_keys)
            target = not current_all
            for k in all_days_keys:
                day_vars[k].set(target)
                day_buttons[k].configure(
                    fg_color=COLOR_GREEN if target else "#2A2A30",
                    text_color="#FFFFFF" if target else "#8E8E93"
                )
            _update_all_btn()
            self._mark_schedules_dirty()

        all_btn = ctk.CTkButton(
            days_box,
            text=t("day_all"),
            width=32 if get_current_language() == "ar" else 28,
            height=22,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_GREEN if is_all_active else "#2A2A30",
            text_color="#FFFFFF" if is_all_active else "#8E8E93",
            hover_color=COLOR_GREEN_HOVER,
            command=_on_all_clicked
        )
        all_btn.pack(side="left", padx=(0, 3))

        day_labels = [
            ("Mon", t("day_mon")),
            ("Tue", t("day_tue")),
            ("Wed", t("day_wed")),
            ("Thu", t("day_thu")),
            ("Fri", t("day_fri")),
            ("Sat", t("day_sat")),
            ("Sun", t("day_sun"))
        ]
        for k, lbl in day_labels:
            active = is_all_active or (k in normalized_days)
            var = ctk.BooleanVar(value=active)
            day_vars[k] = var

            btn = ctk.CTkButton(
                days_box,
                text=lbl,
                width=22,
                height=22,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=COLOR_GREEN if active else "#2A2A30",
                text_color="#FFFFFF" if active else "#8E8E93",
                hover_color=COLOR_GREEN_HOVER,
                command=lambda day_key=k: _on_day_clicked(day_key)
            )
            btn.pack(side="left", padx=1)
            day_buttons[k] = btn

        # Slot Label Entry (e.g. Friday Prayer)
        lbl_entry = ctk.CTkEntry(
            row,
            placeholder_text=t("slot_label_placeholder"),
            width=120,
            height=24,
            font=ctk.CTkFont(size=11)
        )
        if label_val:
            lbl_entry.insert(0, label_val)
        lbl_entry.pack(side="left", padx=(0, 6))
        lbl_entry.bind("<KeyRelease>", lambda e: self._mark_schedules_dirty())

        entry_data = {
            "frame": row,
            "start_entry": st_entry,
            "end_entry": et_entry,
            "label_entry": lbl_entry,
            "all_btn": all_btn,
            "day_vars": day_vars,
            "day_buttons": day_buttons,
            "del_btn": None
        }

        del_btn = ctk.CTkButton(
            row,
            text="✕",
            width=24,
            height=22,
            fg_color="#2A2A30",
            hover_color="#7F1D1D",
            font=ctk.CTkFont(size=11),
            command=lambda: self._delete_slot_row(entry_data)
        )
        del_btn.pack(side="left")
        entry_data["del_btn"] = del_btn

        self.slot_rows.append(entry_data)

    def on_add_slot_clicked(self):
        self._create_slot_row("12:00", "14:00", ["All"], label_val="")
        self._mark_schedules_dirty()

    def _delete_slot_row(self, row_dict):
        if len(self.slot_rows) <= 1:
            messagebox.showwarning("Notice", "You must keep at least one time slot. (You can uncheck 'Enable Auto-Recording' above instead).")
            return
        row_dict["frame"].destroy()
        self.slot_rows.remove(row_dict)
        self._mark_schedules_dirty()

    def on_toggle_schedule_enabled(self):
        new_state = self.sched_enabled_var.get()
        if not new_state:
            # User wants to DISABLE
            confirm = messagebox.askyesno(
                t("dlg_disable_sch_title"),
                t("dlg_disable_sch_msg"),
                icon="warning"
            )
            if not confirm:
                self.sched_enabled_var.set(True)
                return
        else:
            # User wants to ENABLE
            confirm = messagebox.askyesno(
                t("dlg_enable_sch_title"),
                t("dlg_enable_sch_msg"),
                icon="question"
            )
            if not confirm:
                self.sched_enabled_var.set(False)
                return

        self.scheduler.enabled = new_state
        self.config.set("schedule_enabled", new_state)
        self.scheduler.evaluate()
        self._update_status_banner()
        self._update_dashboard_summary()

    def on_save_schedules_clicked(self):
        enabled = self.sched_enabled_var.get()
        slots = []
        for r in self.slot_rows:
            st = r["start_entry"].get().strip()
            et = r["end_entry"].get().strip()
            lbl = r["label_entry"].get().strip() if "label_entry" in r else ""
            sel_days = [d for d, var in r["day_vars"].items() if var.get()]
            if not sel_days or len(sel_days) == 7:
                days_payload = ["All"]
            else:
                days_payload = sel_days
            slots.append({"start": st, "end": et, "days": days_payload, "label": lbl})

        success = self.scheduler.update_schedules(enabled=enabled, slots=slots)
        if success:
            merged_count = len(self.scheduler.slots)
            self._populate_slot_rows()
            self._update_status_banner()
            self._update_dashboard_summary()
            self._mark_schedules_clean()
            if merged_count < len(slots):
                messagebox.showinfo(t("dlg_save_title"), t("dlg_merged_slots"))
            else:
                messagebox.showinfo(t("dlg_save_title"), t("dlg_saved_count", count=merged_count))
        else:
            messagebox.showerror("Invalid Schedule", "Please ensure all time slots are valid 24-hour times in HH:MM format (e.g. 09:00, 14:30).")

    # -------------------------------------------------------------
    # Fast Zero-Allocation VU Meter (Throttled & Window-Aware)
    # -------------------------------------------------------------
    def _meter_ui_tick(self):
        """Smooth level meter updates paused when window is hidden or dragged."""
        try:
            if not self.root.winfo_viewable() or self.root.state() == "iconic":
                self.root.after(500, self._meter_ui_tick)
                return
        except Exception:
            pass

        if (time.time() - self._last_resize_time) < 0.15:
            self.root.after(66, self._meter_ui_tick)
            return

        l_peak, r_peak, l_rms, r_rms, l_clip, r_clip = self.audio.get_levels()
        self.meter_numeric_lbl.configure(text=f"L: {l_peak:5.1f} dBFS | R: {r_peak:5.1f} dBFS")

        if self.current_view == "dashboard":
            w = self.meter_canvas.winfo_width()
            if w > 20:
                bar_h = 13
                self.meter_canvas.coords(self.track_l, 0, self.y_l, w, self.y_l + bar_h)
                self.meter_canvas.coords(self.track_r, 0, self.y_r, w, self.y_r + bar_h)

                green_end = int(w * (42.0 / 60.0))
                amber_end = int(w * (54.0 / 60.0))

                def calc_segments(peak_db: float):
                    norm = max(0.0, min(1.0, (peak_db + 60.0) / 60.0))
                    px = int(norm * w)
                    gw = min(px, green_end)
                    aw = min(px, amber_end) if px > green_end else green_end
                    rw = px if px > amber_end else amber_end
                    return gw, aw, rw

                lg, la, lr = calc_segments(l_peak)
                self.meter_canvas.coords(self.bar_l_green, 0, self.y_l, lg, self.y_l + bar_h)
                self.meter_canvas.coords(self.bar_l_amber, green_end, self.y_l, la, self.y_l + bar_h)
                self.meter_canvas.coords(self.bar_l_red, amber_end, self.y_l, lr, self.y_l + bar_h)

                rg, ra, rr = calc_segments(r_peak)
                self.meter_canvas.coords(self.bar_r_green, 0, self.y_r, rg, self.y_r + bar_h)
                self.meter_canvas.coords(self.bar_r_amber, green_end, self.y_r, ra, self.y_r + bar_h)
                self.meter_canvas.coords(self.bar_r_red, amber_end, self.y_r, rr, self.y_r + bar_h)

        self.root.after(66, self._meter_ui_tick)

    # -------------------------------------------------------------
    # 1-Second Dedicated Elapsed Recording Timer
    # -------------------------------------------------------------
    def _timer_ui_tick(self):
        """Updates elapsed recording counter smoothly every 1 second."""
        if self.audio.is_recording and self.current_view == "dashboard":
            self._update_status_banner()
        self.root.after(1000, self._timer_ui_tick)

    # -------------------------------------------------------------
    # Audio Routing & Callbacks
    # -------------------------------------------------------------
    def refresh_devices_list(self):
        """Enumerates deduplicated hardware audio devices."""
        inputs, outputs = self.audio.get_audio_devices()
        self.input_devices_cache = inputs
        self.output_devices_cache = outputs

        input_names = [d["display_name"] for d in inputs]
        if not input_names:
            input_names = ["No Input Devices Found"]
        self.input_device_combo.configure(values=input_names)

        saved_name = self.config.get("input_device_name", "")
        selected_in = input_names[0]
        if saved_name:
            for name in input_names:
                if saved_name.lower() in name.lower() or name.lower() in saved_name.lower():
                    selected_in = name
                    break
        self.input_device_combo.set(selected_in)
        self._update_dashboard_summary()

    def on_input_device_changed(self, choice: str):
        """User selected a new input device."""
        for dev in self.input_devices_cache:
            if dev["display_name"] == choice or dev["name"] == choice:
                self.config.update(input_device_name=dev["name"], input_host_api=dev["hostapi"])
                logger.info("Selected input device: %s (%s, ID: %d)", dev["name"], dev["hostapi"], dev["id"])
                self.audio.start_input_stream()
                self._update_dashboard_summary()
                break

    def on_mono_switch_toggled(self):
        self.audio.set_mono_sum(self.mono_switch_var.get())

    def on_monitor_switch_toggled(self):
        self.audio.set_monitoring(self.monitor_switch_var.get())

    # -------------------------------------------------------------
    # Schedule & Manual Override Logic
    # -------------------------------------------------------------
    def toggle_manual_recording(self):
        """Toggles recording when the prominent Action button or tray menu is clicked (Thread-Safe)."""
        def _do_toggle():
            if self.audio.is_recording:
                self.scheduler.trigger_manual_stop()
            else:
                self.scheduler.trigger_manual_start()
        self.root.after(0, _do_toggle)

    def on_scheduler_start_recording(self, is_manual: bool, slot_label: str = ""):
        mode = "MANUAL" if is_manual else "SCHEDULED"
        res = self.audio.start_recording(manual=is_manual, slot_label=slot_label)
        if res:
            logger.info("Recording started successfully (%s, slot: '%s'): %s", mode, slot_label, res)
            self._update_status_banner()
            self._update_settings_lock_state(force=True)
            self.tray.update_recording_state(True)
        else:
            logger.error("Failed to start recording.")

    def on_scheduler_stop_recording(self):
        self.audio.stop_recording()
        self._update_status_banner()
        self._update_settings_lock_state(force=True)
        self.tray.update_recording_state(False)
        self.root.after(500, self._startup_cleanup)

    def _schedule_watchdog_tick(self):
        """2-second scheduler evaluation loop."""
        self.scheduler.evaluate()
        self._update_status_banner()
        if not hasattr(self, "_disk_tick_counter"):
            self._disk_tick_counter = 0
        self._disk_tick_counter += 1
        if self._disk_tick_counter >= 5: # Every 10 seconds
            self._disk_tick_counter = 0
            self._update_dashboard_summary()
        self.root.after(2000, self._schedule_watchdog_tick)

    def _update_status_banner(self):
        """Refreshes status banner and action button."""
        self._update_settings_lock_state()

        # Low Disk Space Emergency Alert
        if self.audio.low_disk_state:
            self.status_title.configure(text="⚠️ DISK FULL — RECORDING STOPPED", text_color=COLOR_RED)
            self.status_subtitle.configure(text="Free disk space is below 500 MB. Please clear disk space.")
            self.status_banner.configure(border_color=COLOR_RED)
            return

        # Audio Disconnected Alert
        if self.audio.device_error_state:
            self.status_title.configure(text="🔴 AUDIO INPUT DISCONNECTED", text_color=COLOR_RED)
            self.status_subtitle.configure(text="Check audio input cable. Retrying connection every 5s...")
            self.status_banner.configure(border_color=COLOR_RED)
            return

        # Recording Active
        if self.audio.is_recording:
            start_t = self.audio.recording_start_time or time.time()
            elapsed_sec = max(0, int(time.time() - start_t))
            hh = elapsed_sec // 3600
            mm = (elapsed_sec % 3600) // 60
            ss = elapsed_sec % 60
            elapsed_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
            filename = Path(self.audio.recording_file_path or "").name
            size_mb = 0.0
            try:
                if self.audio.recording_file_path and os.path.exists(self.audio.recording_file_path):
                    size_mb = os.path.getsize(self.audio.recording_file_path) / (1024 * 1024)
            except Exception:
                pass

            if self.scheduler.is_in_overtime:
                overtime_min = int((time.time() - (self.scheduler.overtime_start_time or time.time())) / 60)
                end_str = self.scheduler.active_slot["end"] if self.scheduler.active_slot else "Schedule"
                self.status_title.configure(
                    text=f"{t('status_recording')} {t('status_overtime')} [{elapsed_str}]",
                    text_color=COLOR_GREEN
                )
                self.status_subtitle.configure(
                    text=f"{filename} • {t('status_overtime')} (+{overtime_min}m)"
                )
                self.status_banner.configure(border_color=COLOR_GREEN)
            else:
                mode_tag = "MANUAL" if self.audio.is_manual_recording else "SCHEDULED"
                slot_info = f" ({self.scheduler.active_slot['start']}—{self.scheduler.active_slot['end']})" if self.scheduler.active_slot else ""
                self.status_title.configure(
                    text=f"{t('status_recording')} ({mode_tag}{slot_info}) [{elapsed_str}]",
                    text_color=COLOR_RED
                )
                self.status_subtitle.configure(
                    text=t("subtitle_recording", filename=filename, size_mb=size_mb)
                )
                self.status_banner.configure(border_color=COLOR_RED)

            self.action_btn.configure(
                text=t("btn_stop_recording"),
                fg_color="#7F1D1D",
                hover_color=COLOR_RED_HOVER
            )
            return

        # Paused / Suppressed for current window
        if self.scheduler.suppressed_for_current_window:
            slot_str = ""
            if self.scheduler.suppressed_slot:
                slot_str = f" ({self.scheduler.suppressed_slot['start']}—{self.scheduler.suppressed_slot['end']})"
            self.status_title.configure(
                text=t("status_paused"),
                text_color=COLOR_AMBER
            )
            self.status_subtitle.configure(
                text=f"{t('subtitle_paused')}{slot_str}"
            )
            self.status_banner.configure(border_color=COLOR_AMBER)
            self.action_btn.configure(
                text=t("btn_resume_schedule"),
                fg_color=COLOR_AMBER,
                hover_color="#D97706"
            )
            return

        # Standby
        if not self.scheduler.enabled:
            self.status_title.configure(
                text=t("status_standby"),
                text_color=COLOR_AMBER
            )
            cur_mic = self.config.get("input_device_name", "Default")
            self.status_subtitle.configure(
                text=t("subtitle_standby_manual", device=cur_mic)
            )
        else:
            next_info = self.scheduler.get_next_slot()
            if next_info:
                when = next_info.get("day_name", "Upcoming")
                st = next_info["slot"]["start"]
                et = next_info["slot"]["end"]
                self.status_title.configure(
                    text=t("status_standby"),
                    text_color=COLOR_GREEN
                )
                self.status_subtitle.configure(
                    text=f"{t('sum_next_schedule')} {when} ({st} — {et})"
                )
            else:
                self.status_title.configure(
                    text=t("status_standby"),
                    text_color=COLOR_AMBER
                )
                self.status_subtitle.configure(
                    text=t("sum_no_upcoming")
                )

        self.status_banner.configure(border_color=COLOR_PANEL_BORDER)
        self.action_btn.configure(
            text=t("btn_start_manual"),
            fg_color=COLOR_RED,
            hover_color=COLOR_RED_HOVER
        )

    # -------------------------------------------------------------
    # Storage & System Settings
    # -------------------------------------------------------------
    def on_browse_folder(self):
        curr = self.config.get("backup_folder", "")
        chosen = filedialog.askdirectory(initialdir=curr, title="Select Mosque Audio Backup Directory")
        if chosen:
            self.config.set("backup_folder", chosen)
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, chosen)
            self.folder_entry.configure(state="readonly")
            self._update_dashboard_summary()

    def on_open_folder(self):
        folder = self.config.get("backup_folder", "")
        if os.path.exists(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])

    def on_open_log_file(self):
        """Opens diagnostic log file in the default system text editor (e.g. Notepad)."""
        from config_manager import get_app_dir
        log_name = "app.log" if self.profile == "default" else f"app_{self.profile}.log"
        log_file = get_app_dir() / log_name
        if not log_file.exists():
            log_file.touch()

        try:
            if sys.platform == "win32":
                os.startfile(str(log_file))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_file)])
            else:
                subprocess.run(["xdg-open", str(log_file)])
        except Exception as e:
            logger.error("Failed to open log file %s: %s", log_file, e)
            messagebox.showerror("Error", f"Could not open log file:\n{e}")

    def on_startup_toggled(self):
        enabled = self.startup_var.get()
        set_autostart(enabled, profile=self.profile)
        self.config.set("auto_start_on_boot", enabled)

    def _on_naming_pattern_changed(self, event=None):
        """Updates live filename preview on user typing."""
        from config_manager import format_recording_filename
        pat = self.naming_entry.get().strip()
        if not pat:
            pat = "Audio_Backup_{date}_{time}"
        preview = format_recording_filename(pat)
        self.naming_preview_lbl.configure(text=f"Preview: {preview}", text_color=COLOR_GREEN)

    def on_save_naming_pattern(self):
        """Saves custom file naming format."""
        from config_manager import format_recording_filename
        pat = self.naming_entry.get().strip()
        if not pat:
            pat = "Audio_Backup_{date}_{time}"
            self.naming_entry.delete(0, "end")
            self.naming_entry.insert(0, pat)

        for ch in '<>:"/\\|?*':
            pat = pat.replace(ch, "_")

        self.config.set("filename_pattern", pat)
        preview = format_recording_filename(pat)
        self.naming_preview_lbl.configure(text=f"Preview: {preview} (Saved)", text_color=COLOR_GREEN)
        messagebox.showinfo("Naming Format Saved", f"File naming pattern saved successfully!\n\nPreview: {preview}")

    def on_companion_format_changed(self, choice: str):
        val = self.companion_format_map.get(choice, "mp3")
        self.config.set("companion_format", val)
        self.config.set("auto_export_mp3", (val != "none"))
        logger.info("Selected companion export format: %s", val.upper())
        if val != "none":
            from config_manager import recover_missing_companion_exports
            folder = self.config.get("backup_folder", "")
            if folder:
                threading.Thread(
                    target=recover_missing_companion_exports,
                    args=(folder, self.audio.recording_file_path, val),
                    daemon=True
                ).start()

    def on_folder_grouping_changed(self, choice: str):
        mapped = self.grouping_options.get(choice, "monthly")
        self.config.set("folder_grouping", mapped)
        self._update_dashboard_summary()
        logger.info("Folder grouping updated to: %s (%s)", choice, mapped)

    def on_language_changed(self, choice: str):
        rev_langs = {v: k for k, v in SUPPORTED_LANGUAGES.items()}
        code = rev_langs.get(choice, "en")
        set_current_language(code)
        self.config.set("language", code)
        logger.info("Language changed to: %s (%s)", choice, code)
        self._apply_language()

    def _apply_language(self):
        """Refreshes all UI text labels across views to the currently active language."""
        # Header / Brand
        if hasattr(self, "header_title"):
            title_text = t("app_title") if self.profile == "default" else f"{t('app_title')} [{self.profile}]"
            self.header_title.configure(text=title_text)
        if self.profile == "default":
            self.root.title(t("app_title"))
        else:
            self.root.title(f"{t('app_title')} [{self.profile}]")

        if hasattr(self, "nav_btn"):
            self.nav_btn.configure(text=t("nav_settings") if self.current_view == "dashboard" else t("nav_dashboard"))

        # Dashboard View
        if hasattr(self, "meter_title_lbl"):
            self.meter_title_lbl.configure(text=t("meter_title"))
        self._update_status_banner()
        self._update_dashboard_summary()

        # Settings View - Section 1 (Audio Input)
        if hasattr(self, "sec_mic_lbl"):
            self.sec_mic_lbl.configure(text=t("sec_audio_device"))
        if hasattr(self, "rescan_btn"):
            self.rescan_btn.configure(text=f"🔄 {t('btn_refresh')}")

        # Settings View - Section 2 (Schedules)
        if hasattr(self, "sec_sch_lbl"):
            self.sec_sch_lbl.configure(text=t("sec_schedules"))
        if hasattr(self, "sched_enabled_chk"):
            self.sched_enabled_chk.configure(text=t("opt_schedule_master"))
        if hasattr(self, "add_slot_btn"):
            self.add_slot_btn.configure(text=t("btn_add_slot"))
        if hasattr(self, "save_sch_btn"):
            self.save_sch_btn.configure(
                text=t("btn_save_schedules"),
                state="normal" if self._schedules_dirty else "disabled",
                fg_color=COLOR_GREEN if self._schedules_dirty else "#2A2A30",
                hover_color=COLOR_GREEN_HOVER if self._schedules_dirty else "#2A2A30",
                text_color="#FFFFFF" if self._schedules_dirty else "#8E8E93"
            )

        # Settings View - Section 3 (Storage)
        if hasattr(self, "sec_storage_lbl"):
            self.sec_storage_lbl.configure(text=t("sec_storage"))
        if hasattr(self, "browse_btn"):
            self.browse_btn.configure(text=t("btn_browse"))
        if hasattr(self, "sec_retention_lbl"):
            self.sec_retention_lbl.configure(text=t("sec_retention"))
        if hasattr(self, "sec_naming_lbl"):
            self.sec_naming_lbl.configure(text=t("sec_naming"))
        if hasattr(self, "naming_tokens_lbl"):
            self.naming_tokens_lbl.configure(text=t("naming_tokens"))
        if hasattr(self, "sec_comp_lbl"):
            self.sec_comp_lbl.configure(text=t("opt_companion_format"))
        if hasattr(self, "companion_combo"):
            self.companion_format_map = {
                t("fmt_mp3"): "mp3",
                t("fmt_wav"): "wav",
                t("fmt_ogg"): "ogg",
                t("fmt_none"): "none"
            }
            self.companion_format_reverse_map = {v: k for k, v in self.companion_format_map.items()}
            self.companion_combo.configure(values=list(self.companion_format_map.keys()))
            cur_comp = self.config.get("companion_format")
            if not cur_comp:
                cur_comp = "mp3" if self.config.get("auto_export_mp3", True) else "none"
            self.companion_combo.set(self.companion_format_reverse_map.get(cur_comp, t("fmt_mp3")))
        if hasattr(self, "sec_group_lbl"):
            self.sec_group_lbl.configure(text=t("sec_folder_grouping"))

        # Settings View - Section 4 (System Options)
        if hasattr(self, "sec_system_lbl"):
            self.sec_system_lbl.configure(text=t("sec_system"))
        if hasattr(self, "lang_lbl"):
            self.lang_lbl.configure(text=t("opt_language"))
        if hasattr(self, "startup_chk"):
            os_label = "Windows" if sys.platform == "win32" else "macOS" if sys.platform == "darwin" else "Linux" if sys.platform.startswith("linux") else "System"
            self.startup_chk.configure(text=f"{t('opt_autostart')} ({os_label})")
        if hasattr(self, "mono_switch"):
            self.mono_switch.configure(text=t("opt_mono_sum"))
        if hasattr(self, "monitor_switch"):
            self.monitor_switch.configure(text=f"🎧 {t('opt_headphone')}")
        if hasattr(self, "open_log_btn"):
            self.open_log_btn.configure(text=t("btn_open_log"))

        # Settings View - Section 5 (Audio Profiles)
        if hasattr(self, "sec_prof_lbl"):
            self.sec_prof_lbl.configure(text=t("sec_profiles"))
        if hasattr(self, "sec_prof_desc"):
            self.sec_prof_desc.configure(text=t("sec_profiles_desc"))
        if hasattr(self, "add_profile_btn"):
            self.add_profile_btn.configure(text=t("btn_add_profile"))
        if hasattr(self, "profiles_container"):
            self._populate_profiles_list()

        # Re-populate schedule slot rows with localized day button labels
        self._populate_slot_rows()

        if hasattr(self, "lock_banner_lbl"):
            self.lock_banner_lbl.configure(text=t("settings_locked_banner"))
        if hasattr(self, "retention_hint_lbl"):
            self.retention_hint_lbl.configure(text=t("retention_hint"))

        self._update_settings_lock_state(force=True)

    def _startup_cleanup(self):
        try:
            retention_days = int(self.retention_entry.get().strip())
            self.config.set("retention_days", retention_days)
            folder = self.config.get("backup_folder", "")
            pattern = self.config.get("filename_pattern", "")
            cleanup_old_backups(folder, retention_days, pattern=pattern, profile=self.profile)

            # Power-Cut Recovery & Missing Companion Generator
            companion_fmt = self.config.get("companion_format")
            if not companion_fmt:
                companion_fmt = "mp3" if self.config.get("auto_export_mp3", True) else "none"

            if companion_fmt != "none":
                from config_manager import recover_missing_companion_exports
                def _async_recovery():
                    logger.info("Scanning for missing %s files (power-cut recovery)...", companion_fmt.upper())
                    recovered = recover_missing_companion_exports(
                        folder,
                        active_recording_file=self.audio.recording_file_path,
                        target_format=companion_fmt
                    )
                    if recovered > 0:
                        logger.info("Power-cut recovery: Successfully generated %d missing %s copies.", recovered, companion_fmt.upper())

                t = threading.Thread(target=_async_recovery, daemon=True)
                t.start()
        except Exception as e:
            logger.error("Startup retention cleanup error: %s", e)

    # -------------------------------------------------------------
    # Volunteer-Proof Window Interception & System Tray
    # -------------------------------------------------------------
    def on_close_button_clicked(self):
        """Hides the window to tray on Windows/supported Linux, or minimizes cleanly."""
        if sys.platform == "win32" or (sys.platform.startswith("linux") and getattr(self.tray, "is_tray_available", False)):
            self.root.withdraw()
            self.tray.notify(
                title="AudioGuard",
                message="AudioGuard is running in the background and protecting audio backups."
            )
        else:
            self.root.iconify()

    def show_window_from_tray(self):
        """Restores window from system tray and brings to foreground (Thread-Safe)."""
        def _restore():
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
            try:
                self.root.attributes("-topmost", True)
                self.root.after(100, lambda: self.root.attributes("-topmost", False))
            except Exception:
                pass
        self.root.after(0, _restore)

    def admin_quit(self):
        """Admin Quit with confirmation dialog."""
        def confirm():
            ans = messagebox.askyesno(
                "Confirm AudioGuard Shutdown",
                "Are you sure you want to completely shut down AudioGuard?\n\n"
                "⚠️ Scheduled backups will NOT run while closed."
            )
            if ans:
                logger.info("Admin confirmed shutdown. Finalizing recording and exiting...")
                if self.audio.is_recording:
                    self.audio.stop_recording()
                self.audio.stop_input_stream()
                self.audio.stop_monitor_stream()
                self.tray.stop()
                self.root.destroy()
                sys.exit(0)

        self.root.after(0, confirm)


def main():
    parser = argparse.ArgumentParser(description="AudioGuard - Bulletproof Background Audio Backup")
    parser.add_argument("--profile", "-p", type=str, default="default", help="Configuration profile name for multi-instance recording")
    parser.add_argument("--minimized", "-m", action="store_true", help="Start minimized to system tray")
    args, _ = parser.parse_known_args()

    raw_profile = (args.profile or "default").strip()
    profile = re.sub(r'[^a-zA-Z0-9_\-]', '', raw_profile)
    if not profile:
        profile = "default"

    setup_logging(profile=profile)
    logger.info("=" * 60)
    logger.info("Starting AudioGuard [Profile: %s]...", profile)
    logger.info("=" * 60)

    start_minimized = args.minimized

    lock = SingleInstanceLock(profile=profile)
    if not lock.acquire():
        logger.info("AudioGuard [%s] is already running. Signaling existing instance to show window...", profile)
        signal_existing_instance(profile=profile)
        sys.exit(0)

    try:
        root = ctk.CTk()
        app = AudioGuardApp(root, start_minimized=start_minimized, profile=profile)
        root.mainloop()
    except Exception as e:
        logger.critical("Unhandled top-level crash in profile [%s]: %s", profile, e, exc_info=True)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
