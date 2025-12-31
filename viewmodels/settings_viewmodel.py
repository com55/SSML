"""Settings dialog ViewModel."""
from PySide6.QtCore import QObject

from core import Config


class SettingsViewModel(QObject):
    """ViewModel for the settings dialog."""
    
    def __init__(self):
        super().__init__()
        self.config = Config('config.ini')

    def get_game_path(self) -> str:
        return self.config.GameExePath.get() or ""

    def set_game_path(self, val: str) -> None:
        self.config.GameExePath.set(val)

    def get_mods_dir(self) -> str:
        return self.config.ModsDir.get() or ""

    def set_mods_dir(self, val: str) -> None:
        self.config.ModsDir.set(val)

    def get_backups_dir(self) -> str:
        return self.config.BackupsDir.get() or ""

    def set_backups_dir(self, val: str) -> None:
        self.config.BackupsDir.set(val)

    def get_mod_ext(self) -> str:
        return self.config.ModExtension.get() or ".unity3d"

    def set_mod_ext(self, val: str) -> None:
        self.config.ModExtension.set(val)

    def get_hide_console(self) -> bool:
        val = self.config.HideConsoleWhenRunning.get()
        return val if val is not None else True

    def set_hide_console(self, val: bool) -> None:
        self.config.HideConsoleWhenRunning.set(val)
