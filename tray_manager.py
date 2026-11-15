"""
AudioGuard - System Tray Manager
- pystray + Pillow dynamic icon generation
- Red Circle for Recording, Green/Blue Shield for Standby
- Intercepts window close to minimize to tray
- Right-click menu with Dashboard, Start/Stop toggle, and Admin Quit
"""

from __future__ import annotations
import sys
import logging
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    pystray = None
    HAS_PYSTRAY = False

logger = logging.getLogger("AudioGuard.Tray")

class TrayManager:
    def __init__(self,
                 on_show_window: Callable[[], None],
                 on_toggle_record: Callable[[], None],
                 on_admin_quit: Callable[[], None],
                 app_title: str = "AudioGuard"):
        self.on_show_window = on_show_window
        self.on_toggle_record = on_toggle_record
        self.on_admin_quit = on_admin_quit
        self.app_title = app_title
        
        self.icon: Optional[pystray.Icon] = None
        self.is_recording = False
        self._tray_thread: Optional[threading.Thread] = None
        
        self._icon_standby = self._create_shield_icon()
        self._icon_recording = self._create_record_icon()

    @staticmethod
    def _create_shield_icon(size: int = 64) -> Image.Image:
        """Draws a crisp emerald/blue shield icon for Standby mode."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Shield coordinates
        # Outer shield boundary
        shield_poly = [
            (size * 0.5, size * 0.08),
            (size * 0.88, size * 0.22),
            (size * 0.88, size * 0.58),
            (size * 0.5, size * 0.92),
            (size * 0.12, size * 0.58),
            (size * 0.12, size * 0.22)
        ]
        # Emerald fill (#10B981)
        draw.polygon(shield_poly, fill=(16, 185, 129, 255))
        # Highlight border (#34D399)
        draw.polygon(shield_poly, outline=(52, 211, 153, 255), width=2)
        
        # Inner white checkmark or mini mic
        center_x, center_y = size * 0.5, size * 0.5
        draw.ellipse([center_x - 6, center_y - 8, center_x + 6, center_y + 4], fill=(255, 255, 255, 255))
        draw.rectangle([center_x - 2, center_y + 4, center_x + 2, center_y + 10], fill=(255, 255, 255, 255))
        draw.rectangle([center_x - 6, center_y + 10, center_x + 6, center_y + 12], fill=(255, 255, 255, 255))
        
        return img

    @staticmethod
    def _create_record_icon(size: int = 64) -> Image.Image:
        """Draws a bright red circle icon for Recording mode."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        margin = size * 0.1
        # Outer vibrant red circle (#EF4444)
        draw.ellipse([margin, margin, size - margin, size - margin], fill=(239, 68, 68, 255))
        # Inner white pulsing center
        inner_margin = size * 0.28
        draw.ellipse([inner_margin, inner_margin, size - inner_margin, size - inner_margin], fill=(255, 255, 255, 255))
        
        return img

    def start(self):
        """Initializes and runs the system tray icon in a dedicated daemon thread."""
        if sys.platform != "win32" or not HAS_PYSTRAY:
            logger.info("System Tray skipped on %s (Dock / foreground mode active)", sys.platform)
            return

        def run():
            try:
                menu = pystray.Menu(
                    pystray.MenuItem("Open Dashboard", self._on_menu_open, default=True),
                    pystray.MenuItem(self._get_toggle_text, self._on_menu_toggle_record),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Exit (Admin Quit)", self._on_menu_quit)
                )
                self.icon = pystray.Icon(
                    name=self.app_title,
                    icon=self._icon_standby,
                    title=f"{self.app_title} (Standby)",
                    menu=menu
                )
                self.icon.run()
            except Exception as e:
                logger.error("Failed to run system tray icon: %s", e)

        self._tray_thread = threading.Thread(target=run, daemon=True)
        self._tray_thread.start()
        logger.info("System Tray initialized (%s).", self.app_title)

    def _get_toggle_text(self, item) -> str:
        return "⏹ Stop Recording Now" if self.is_recording else "🔴 Start Manual Recording"

    def _on_menu_open(self, icon, item):
        self.on_show_window()

    def _on_menu_toggle_record(self, icon, item):
        self.on_toggle_record()

    def _on_menu_quit(self, icon, item):
        self.on_admin_quit()

    def update_recording_state(self, recording: bool, tooltip_text: str = ""):
        """Updates the tray icon color and tooltip based on recording status."""
        self.is_recording = recording
        if not self.icon:
            return
            
        try:
            self.icon.icon = self._icon_recording if recording else self._icon_standby
            if tooltip_text:
                self.icon.title = f"{self.app_title}: {tooltip_text}"
            else:
                self.icon.title = f"{self.app_title}: RECORDING" if recording else f"{self.app_title}: STANDBY"
        except Exception as e:
            logger.debug("Error updating tray icon: %s", e)

    def set_recording_state(self, recording: bool, tooltip_text: str = ""):
        """Alias for update_recording_state."""
        self.update_recording_state(recording, tooltip_text)

    def notify(self, title: str, message: str):
        """Displays a brief balloon or system notification."""
        if self.icon:
            try:
                self.icon.notify(title=title, message=message)
            except Exception as e:
                logger.debug("Tray notification error: %s", e)
        elif sys.platform == "darwin":
            try:
                import subprocess
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{message}" with title "{title}"'
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def stop(self):
        """Stops and cleans up the system tray icon."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
