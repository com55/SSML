"""Game launcher module for quick launch functionality."""
import logging
from pathlib import Path

from core import Config, StellaSoraModLoader, StellaSoraGame
from utils import get_exe_path

logger = logging.getLogger(__name__)


class GameLauncher:
    """Handles game launching with mod verification."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def quick_launch(self) -> tuple[bool, str | None]:
        """
        Launch game immediately without UI.
        
        Verifies mods are applied correctly before launching.
        
        Returns:
            (success, error_message) - If success is False, error_message explains why
        """
        logger.info("Quick launch: starting")
        
        # Validate game path
        game_exe = self.config.GameExePath.get()
        if not game_exe:
            logger.warning("Quick launch: Game path not configured")
            return False, "Game path not configured"
        
        game_path = Path(game_exe)
        if not game_path.exists():
            logger.warning(f"Quick launch: Game not found at {game_path}")
            return False, f"Game not found: {game_path}"
        
        # Setup directories
        mods_dir_str = self.config.ModsDir.get()
        backups_dir_str = self.config.BackupsDir.get()
        
        mods_dir = Path(mods_dir_str) if mods_dir_str else get_exe_path("Mods")
        backups_dir = Path(backups_dir_str) if backups_dir_str else get_exe_path("Backups")
        mod_ext = self.config.ModExtension.get() or ".unity3d"
        
        # Create loader
        loader = StellaSoraModLoader(
            game_path.parent,
            mods_dir,
            backups_dir,
            mod_ext
        )
        
        # Sync and check for problems
        try:
            logger.debug("Quick launch: syncing mods")
            orphaned = loader.sync_mods()
            if orphaned:
                logger.warning(f"Quick launch: Found {len(orphaned)} orphaned mod(s)")
                return False, f"Found {len(orphaned)} orphaned mod(s) that need attention"
            
            # Check for conflicts in enabled mods
            mods = loader.get_mods_list()
            enabled_mods = [m for m in mods if not loader.is_disabled(m)]
            
            for mod in enabled_mods:
                conflicts = loader.check_duplicate_conflict(mod)
                if conflicts:
                    conflict_names = [c["path"] for c in conflicts]
                    logger.warning(f"Quick launch: Mod conflict detected - {mod.name}")
                    return False, f"Mod conflict detected: {mod.name} conflicts with {conflict_names}"
            
            # Verify enabled mods are applied
            logger.debug("Quick launch: verifying enabled mods")
            loader.verify_enabled_mods()
            
        except Exception as e:
            logger.error(f"Quick launch: Error during mod verification - {e}", exc_info=True)
            return False, f"Error during mod verification: {e}"
        
        # Launch game
        try:
            logger.info("Quick launch: launching game")
            game = StellaSoraGame(game_path)
            game.start()
        except Exception as e:
            logger.error(f"Quick launch: Failed to launch game - {e}", exc_info=True)
            return False, f"Failed to launch game: {e}"
        
        logger.info("Quick launch: success")
        return True, None

