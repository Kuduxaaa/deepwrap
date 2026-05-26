
import subprocess
import tempfile
import shutil

from typing import Optional
from .browser_finder import BrowserFinder

class BrowserProcess:
    """
    Manages the lifecycle of a browser process launched for authentication.
    """
    
    def __init__(self, url: str, port: int) -> None:
        self.url = url
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.browser_path: Optional[str] = None
        self.user_data_dir: Optional[str] = None

    def start(self) -> "BrowserProcess":
        """
        Start the browser process with the appropriate flags for remote debugging.
        """
        
        browsers = BrowserFinder.find()

        if not browsers:
            raise Exception(
                "No Chromium-based browser was found. Please install Chrome, Edge, Brave, Chromium, Opera, or Vivaldi."
            )

        self.browser_path = browsers[0]
        self.user_data_dir = tempfile.mkdtemp(prefix="deepwrap-auth-profile-")

        args = [
            self.browser_path,
            f"--remote-debugging-port={self.port}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            self.url,
        ]

        self.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return self

    def terminate(self) -> None:
        """
        Terminate the browser process and clean up the user data directory.
        """
        
        if self.process:
            try:
                self.process.terminate()

            except Exception:
                pass

        if self.user_data_dir:
            try:
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except Exception:
                pass