import os
import sys
import threading
import logging
import subprocess
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

# Ensure SES can be imported if run standalone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ses.watcher.monitor import SESWatcher
from ses.config import WATCH_DIRECTORIES

# Setup AppData directory for logs and default manifest
APP_DIR = Path(os.getenv('APPDATA', '')) / 'SESEnterprise'
APP_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
LOG_FILE = APP_DIR / 'watcher.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TrayApp")

# Default Document Watch folder
DEFAULT_WATCH_DIR = Path.home() / 'Documents' / 'SES_Ingest'

class WatcherTrayApp:
    def __init__(self):
        self.watcher = None
        self.watcher_thread = None
        self.icon = None
        self.is_running = False
        
        # Resolve watch directories
        self.directories = WATCH_DIRECTORIES if WATCH_DIRECTORIES else [str(DEFAULT_WATCH_DIR)]
        for d in self.directories:
            os.makedirs(d, exist_ok=True)
            logger.info(f"Ensured directory exists: {d}")

    def create_image(self, running: bool):
        # Generate a simple colored icon (Green for running, Red for stopped)
        width = 64
        height = 64
        color1 = (0, 128, 0) if running else (128, 0, 0)
        color2 = (0, 200, 0) if running else (200, 0, 0)
        
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle(
            (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
            fill=color2
        )
        return image

    def start_watcher(self):
        if self.is_running:
            return
        
        try:
            import asyncio
            self.watcher = SESWatcher(directories=self.directories)
            
            # Create and start a dedicated event loop thread for async operations
            self.loop = asyncio.new_event_loop()
            self.watcher.loop = self.loop
            self.watcher_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
            self.watcher_thread.start()
            
            # Start the watcher (initial scan will use the background loop)
            self.watcher.start()
            
            self.is_running = True
            logger.info("Watcher started via Tray")
            self.update_icon()
        except Exception as e:
            logger.error(f"Failed to start watcher: {e}")

    def stop_watcher(self):
        if not self.is_running:
            return
        
        try:
            if self.watcher:
                self.watcher.stop()
            if hasattr(self, 'loop') and self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
            self.is_running = False
            logger.info("Watcher stopped via Tray")
            self.update_icon()
        except Exception as e:
            logger.error(f"Failed to stop watcher: {e}")

    def update_icon(self):
        if self.icon:
            self.icon.icon = self.create_image(self.is_running)
            self.icon.title = f"SES Watcher - {'Running' if self.is_running else 'Stopped'}"

    def toggle_state(self, icon, item):
        if self.is_running:
            self.stop_watcher()
        else:
            self.start_watcher()

    def open_folder(self, icon, item):
        # Open the first configured directory in File Explorer
        if self.directories:
            try:
                os.startfile(self.directories[0])
            except AttributeError:
                subprocess.call(['explorer', self.directories[0]])

    def view_logs(self, icon, item):
        try:
            os.startfile(str(LOG_FILE))
        except AttributeError:
            subprocess.call(['notepad', str(LOG_FILE)])

    def quit_app(self, icon, item):
        self.stop_watcher()
        icon.stop()

    def run(self):
        menu = pystray.Menu(
            item('Start / Stop', self.toggle_state, default=True),
            item('Open Ingest Folder', self.open_folder),
            item('View Logs', self.view_logs),
            item('Quit', self.quit_app)
        )
        
        # Start watcher automatically on boot
        self.start_watcher()
        
        self.icon = pystray.Icon(
            "SES Watcher",
            self.create_image(self.is_running),
            f"SES Watcher - {'Running' if self.is_running else 'Stopped'}",
            menu
        )
        logger.info("Tray App started")
        self.icon.run()

if __name__ == "__main__":
    app = WatcherTrayApp()
    app.run()
