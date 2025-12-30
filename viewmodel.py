from PySide6.QtCore import QObject, QTimer, Signal, QThread, Slot
from pathlib import Path
from typing import TypedDict
from core import Config, StellaSoraModLoader, StellaSoraGame, get_exe_path


class ModData(TypedDict):
    """Type definition for mod data dictionary."""
    name: str
    enabled: bool
    path: Path
    relative_path: str  # e.g. "Chitose/char_2d_14401.unity3d"

class GameLauncherWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config

    def run(self):
        game_exe = Path(self.config.GameExePath.get() or "")
        mods_dir = Path(self.config.ModsDir.get() or "")
        mod_ext = self.config.ModExtension.get() or ".unity3d"
        restore = self.config.RestoreOriginalFileWhenGameClosed.get()

        loader = StellaSoraModLoader(game_exe.parent, mods_dir, mod_ext, logger=self.log_message)
        game = StellaSoraGame(game_exe)

        if game.is_running():
            self.log_message("Game is already running! Please close it first.")
            self.finished_signal.emit()
            return

        self.log_message("Installing mods...")
        try:
            loader.install_mod()
        except Exception as e:
            self.log_message(f"Error installing mods: {e}")
            self.finished_signal.emit()
            return

        self.log_message("Starting game...")
        game.start()

        if restore:
            self.log_message("Waiting for game close to restore files...")
            
        closed = game.wait_for_game_closed()
        if closed:
            self.finished_signal.emit()
            self.log_message("Game closed detected.")
            if restore:
                loader.restore_all()
                self.log_message("Original files restored.")
        else:
            self.log_message("Could not detect game process start.")

        self.finished_signal.emit()

    def log_message(self, msg: str) -> None:
        self.log_signal.emit(msg)

class MainViewModel(QObject):
    # Signals
    mods_list_changed = Signal(list) # List of (mod_name, is_enabled, full_path)
    log_message = Signal(str)
    game_status_changed = Signal(bool) # True = Running, False = Idle

    def __init__(self):
        super().__init__()
        self.config = Config('config.ini')
        self._ensure_defaults()
        self.loader = self._create_loader()
        self.launcher_thread = None

    def _ensure_defaults(self):
        if not self.config.ModsDir.get():
            default_mods = get_exe_path("Mods")
            default_mods.mkdir(parents=True, exist_ok=True)
            self.config.ModsDir.set(default_mods.as_posix())

    def reload_config(self):
        self.config.reload()
        # After config reload, we might need to update derived state if any
        # For now, load_mods handles re-creating the loader with new paths

    def _create_loader(self):
        mods_dir_str = self.config.ModsDir.get() or ""
        mod_ext = self.config.ModExtension.get() or ".unity3d"
        return StellaSoraModLoader(Path("."), Path(mods_dir_str), mod_ext)

    def load_mods(self):
        self.loader = self._create_loader() # Re-create in case config changed
        if not self.loader.mods_dir.exists():
            self.log_message.emit("Mods directory invalid.")
            return

        # Sync mod status with actual files
        self.loader.sync_mods()

        mods = self.loader.get_mods_list()
        mod_data = []
        for mod in mods:
            is_disabled = self.loader.is_disabled(mod)
            mod_data.append({
                "name": mod.name,
                "enabled": not is_disabled,
                "path": mod,
                "relative_path": mod.relative_to(self.loader.mods_dir).as_posix()
            })
        self.mods_list_changed.emit(mod_data)

    def toggle_mod(self, mod_path: Path, enable: bool):
        try:
            self.loader.toggle_mod(mod_path, enable)
            msg = "enabled" if enable else "disabled"
            self.log_message.emit(f"Mod {msg}: {mod_path.name}")
            self.load_mods() # Refresh list
        except Exception as e:
            self.log_message.emit(f"Error toggling mod: {e}")

    def launch_game(self):
        if not self.config.GameExePath.get():
            self.log_message.emit("Error: Game executable path not set!")
            return

        self.log_message.emit("Launching game process...")

        self.launcher_thread = GameLauncherWorker(self.config)
        self.launcher_thread.log_signal.connect(self.log_message)
        self.launcher_thread.finished_signal.connect(self.on_game_finished)
        self.launcher_thread.start()
        QTimer.singleShot(3000, lambda: self.game_status_changed.emit(True))

    @Slot()
    def on_game_finished(self):
        self.game_status_changed.emit(False)
        # self.log_message.emit("Process finished.")

class SettingsViewModel(QObject):
    def __init__(self):
        super().__init__()
        self.config = Config('config.ini')

    def get_game_path(self):
        return self.config.GameExePath.get() or ""

    def set_game_path(self, val: str) -> None:
        self.config.GameExePath.set(val)

    def get_mods_dir(self):
        return self.config.ModsDir.get() or ""

    def set_mods_dir(self, val: str) -> None:
        self.config.ModsDir.set(val)

    def get_mod_ext(self):
        return self.config.ModExtension.get() or ".unity3d"

    def set_mod_ext(self, val: str) -> None:
        self.config.ModExtension.set(val)

    def get_restore(self):
        val = self.config.RestoreOriginalFileWhenGameClosed.get()
        return val if val is not None else True

    def set_restore(self, val: bool):
        self.config.RestoreOriginalFileWhenGameClosed.set(val)

    def get_hide_console(self):
        val = self.config.HideConsoleWhenRunning.get()
        return val if val is not None else True

    def set_hide_console(self, val: bool):
        self.config.HideConsoleWhenRunning.set(val)
