"""Background worker for launching and monitoring the game."""
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from core import Config, StellaSoraModLoader, StellaSoraGame


class GameLauncherWorker(QThread):
    """Worker thread that launches the game and monitors its status."""
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
