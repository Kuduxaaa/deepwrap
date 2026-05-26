from __future__ import annotations

import json
import os

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

APP_NAME = "deepwrap"

@dataclass
class AppConfig:
    token: Optional[str] = None
    model: str = "expert"
    show_thinking: bool = True
    search_enabled: bool = True
    god_mode: bool = False


class ConfigStore:
    """
    Handles loading and saving of application configuration.
    This includes the bearer token and user preferences. The configuration is
    stored in a JSON file in the user's config directory (e.g. ~/.config/deepwrap/config.json).
    """

    def __init__(self) -> None:
        self.path = self._config_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppConfig:
        """
        Load the application configuration from disk.
        
        Returns:
            An AppConfig instance with the loaded configuration. If the config
            file does not exist or is invalid, returns an AppConfig with default
            values.
        """
        
        if not self.path.exists():
            return AppConfig()

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))

        except Exception:
            return AppConfig()

        return AppConfig(
            token          = payload.get("token"),
            model          = payload.get("model", "expert"),
            show_thinking  = bool(payload.get("show_thinking", True)),
            search_enabled = bool(payload.get("search_enabled", True)),
            god_mode       = bool(payload.get("god_mode", False)),
        )

    def save(self, config: AppConfig) -> None:
        """
        Save the application configuration to disk.
        
        Args:
            config: The AppConfig instance to save.
        """
        
        self.path.write_text(
            json.dumps(asdict(config), indent=2),
            encoding="utf-8",
        )

    def update_token(self, token: str) -> AppConfig:
        """
        Update the stored bearer token in the configuration.
        
        Args:
            token: The new bearer token to store.
        
        Returns:
            The updated AppConfig instance after saving.
        """
        
        config = self.load()
        config.token = token
        self.save(config)
        return config

    @staticmethod
    def _config_path() -> Path:
        """
        Determine the path to the configuration file based on the operating system.
        """
        
        if os.name == "nt":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / APP_NAME / "config.json"

        xdg = os.getenv("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"

        return base / APP_NAME / "config.json"