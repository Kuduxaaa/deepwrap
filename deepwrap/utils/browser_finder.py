import os
import sys

from pathlib import Path
from shutil import which
from typing import Any, List

class BrowserFinder:
    """
    Utility class to find installed Chromium-based browsers on the system.
    This is used by the authentication module to launch a browser instance for user login when no active session is found.
    The finder checks common installation paths for major browsers across Windows, macOS, and Linux, as well as the system PATH.
    """
    
    CHROMIUM_EXECUTABLE_NAMES = [
        "chrome",
        "chrome.exe",
        "msedge",
        "msedge.exe",
        "brave",
        "brave.exe",
        "brave-browser",
        "chromium",
        "chromium-browser",
        "opera",
        "opera.exe",
        "vivaldi",
        "vivaldi.exe",
    ]

    @classmethod
    def find(cls) -> List[str]:
        """
        Find installed Chromium-based browsers.
        
        Returns:
            A list of file paths to detected browser executables. The list may be empty if no browsers are found.
        """
        
        paths = []
        paths.extend(cls._from_path())

        if sys.platform.startswith("win"):
            paths.extend(cls._windows_paths())

        elif sys.platform == "darwin":
            paths.extend(cls._macos_paths())

        else:
            paths.extend(cls._linux_paths())

        return cls._unique_existing(paths)

    @classmethod
    def _from_path(cls) -> List[str]:
        """
        Find browser executables in the system PATH.
        
        Returns:
            A list of file paths to browser executables found in the PATH.
        """

        paths = []

        for name in cls.CHROMIUM_EXECUTABLE_NAMES:
            found = which(name)

            if found:
                paths.append(found)

        return paths

    @staticmethod
    def _windows_paths() -> List[Path]:
        """
        Common installation paths for Chromium-based browsers on Windows.
        
        Returns:
            A list of file paths to browser executables based on common Windows installation directories.
        """
        
        local = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("PROGRAMFILES", "")
        pf86 = os.environ.get("PROGRAMFILES(X86)", "")

        return [
            Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",

            Path(local) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(pf86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",

            Path(local) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(pf) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(pf86) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",

            Path(local) / "Programs" / "Opera" / "opera.exe",
            Path(pf) / "Opera" / "opera.exe",

            Path(local) / "Vivaldi" / "Application" / "vivaldi.exe",
            Path(pf) / "Vivaldi" / "Application" / "vivaldi.exe",
        ]

    @staticmethod
    def _macos_paths() -> List[str]:
        """
        Common installation paths for Chromium-based browsers on macOS.
        
        Returns:
            A list of file paths to browser executables based on common macOS installation directories.
        """

        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Opera.app/Contents/MacOS/Opera",
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
        ]

    @staticmethod
    def _linux_paths() -> List[str]:
        """
        Common installation paths for Chromium-based browsers on Linux.
        
        Returns:
            A list of file paths to browser executables based on common Linux installation directories.
        """

        return [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
            "/usr/bin/brave-browser",
            "/usr/bin/opera",
            "/usr/bin/vivaldi",
            "/snap/bin/chromium",
            "/snap/bin/brave",
        ]

    @staticmethod
    def _unique_existing(paths: List[Any]) -> List[str]:
        """
        Filter the given list of paths to include only unique entries that exist on the filesystem.
        
        Returns:
            A list of unique file paths that exist on the filesystem.
        """
        
        seen = set()
        result = []

        for path in paths:
            if not path:
                continue

            path = str(Path(path))
            normalized = path.lower()

            if normalized in seen:
                continue

            if Path(path).exists():
                seen.add(normalized)
                result.append(path)

        return result