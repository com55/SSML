from PySide6.QtCore import QObject, QTimer, Signal, QThread, Slot
from pathlib import Path
from typing import TypedDict
from core import Config, StellaSoraModLoader, StellaSoraGame, get_exe_path, ModStatusEntry


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
        backups_dir = Path(self.config.BackupsDir.get() or "")
        mod_ext = self.config.ModExtension.get() or ".unity3d"

        loader = StellaSoraModLoader(game_exe.parent, mods_dir, backups_dir, mod_ext, logger=self.log_message)
        game = StellaSoraGame(game_exe)

        if game.is_running():
            self.log_message("Game is already running! Please close it first.")
            self.finished_signal.emit()
            return

        # Sync mods and handle orphaned ones before launch
        try:
            orphaned = loader.sync_mods()
            if orphaned:
                loader.restore_orphaned_backups(orphaned)
        except Exception as e:
            self.log_message(f"Error syncing mods: {e}")
            self.finished_signal.emit()
            return

        # Verify that enabled mods are properly applied (hash check)
        try:
            loader.verify_enabled_mods()
        except Exception as e:
            self.log_message(f"Error verifying mods: {e}")
            self.finished_signal.emit()
            return

        self.log_message("Starting game...")
        game.start()
            
        closed = game.wait_for_game_closed()
        if closed:
            self.log_message("Game closed detected.")
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
        
        if not self.config.BackupsDir.get():
            default_backups = get_exe_path("Backups")
            default_backups.mkdir(parents=True, exist_ok=True)
            self.config.BackupsDir.set(default_backups.as_posix())

    def reload_config(self):
        self.config.reload()
        # After config reload, we might need to update derived state if any
        # For now, load_mods handles re-creating the loader with new paths

    def _create_loader(self):
        game_exe_str = self.config.GameExePath.get() or ""
        game_resource_dir = Path(game_exe_str).parent if game_exe_str else Path(".")
        mods_dir_str = self.config.ModsDir.get() or ""
        backups_dir_str = self.config.BackupsDir.get() or ""
        mod_ext = self.config.ModExtension.get() or ".unity3d"
        return StellaSoraModLoader(
            game_resource_dir, 
            Path(mods_dir_str),
            Path(backups_dir_str),
            mod_ext,
            logger=lambda msg: self.log_message.emit(msg)
        )

    def load_mods(self):
        self.loader = self._create_loader() # Re-create in case config changed
        if not self.loader.mods_dir.exists():
            self.log_message.emit("Mods directory invalid.")
            return

        # Sync mod status with actual files and detect orphaned mods
        orphaned = self.loader.sync_mods()
        
        # Restore game files for orphaned mods (enabled but file deleted/moved)
        if orphaned:
            self.loader.restore_orphaned_backups(orphaned)
            for entry in orphaned:
                self.log_message.emit(f"Restored game file: {entry['path']} (mod removed or moved)")
        
        # Cleanup empty folders in Backups directory
        self.loader.cleanup_empty_backup_folders()

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

    def check_duplicate_conflict(self, mod_path: Path) -> list[ModStatusEntry]:
        """Check if enabling this mod would conflict with other enabled mods.
        
        Returns list of conflicting mods (enabled mods with same filename).
        """
        return self.loader.check_duplicate_conflict(mod_path)
    
    def disable_conflicting_mod(self, conflict_path: str) -> None:
        """Disable a conflicting mod by its relative path."""
        full_path = self.loader.mods_dir / conflict_path
        if full_path.exists():
            self.loader.toggle_mod(full_path, False)
            self.log_message.emit(f"Disabled conflicting mod: {Path(conflict_path).name}")
    
    def toggle_mod(self, mod_path: Path, enable: bool):
        try:
            self.loader.toggle_mod(mod_path, enable)
            msg = "enabled" if enable else "disabled"
            self.log_message.emit(f"Mod {msg}: {mod_path.name}")
            self.load_mods() # Refresh list
        except Exception as e:
            self.log_message.emit(f"Error toggling mod: {e}")

    def toggle_all_mods(self, enable: bool):
        """Enable or disable all mods at once."""
        try:
            mods = self.loader.get_mods_list()
            count = 0
            for mod in mods:
                is_currently_enabled = not self.loader.is_disabled(mod)
                if is_currently_enabled != enable:
                    self.loader.toggle_mod(mod, enable)
                    count += 1
            
            if count > 0:
                msg = "enabled" if enable else "disabled"
                self.log_message.emit(f"All mods {msg}: {count} mod(s)")
                self.load_mods()  # Refresh list
            else:
                msg = "enabled" if enable else "disabled"
                self.log_message.emit(f"All mods already {msg}")
        except Exception as e:
            self.log_message.emit(f"Error toggling all mods: {e}")

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

    def get_backups_dir(self):
        return self.config.BackupsDir.get() or ""

    def set_backups_dir(self, val: str) -> None:
        self.config.BackupsDir.set(val)

    def get_mod_ext(self):
        return self.config.ModExtension.get() or ".unity3d"

    def set_mod_ext(self, val: str) -> None:
        self.config.ModExtension.set(val)

    def get_hide_console(self):
        val = self.config.HideConsoleWhenRunning.get()
        return val if val is not None else True

    def set_hide_console(self, val: bool):
        self.config.HideConsoleWhenRunning.set(val)
