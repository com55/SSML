import configparser
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
import subprocess
from typing import Callable, TypedDict
import psutil
import sys

from utils import get_exe_path

logger = logging.getLogger(__name__)


class ModStatusEntry(TypedDict):
    """Type definition for mod status entry in JSON."""
    path: str  # relative path from mods_dir
    hash: str  # SHA256 hash of the current mod file
    applied_hash: str  # hash of mod that was applied to game (empty if not applied)
    enabled: bool

class _ConfigOptionBase:
    def __init__(self, config_parent: "Config", section: str, option: str) -> None:
        self.config_parent = config_parent
        self.section = section
        self.option = option

    def _get_raw(self) -> str | None:
        try:
            val = self.config_parent.config.get(self.section, self.option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
        if not val or val.strip() == "":
            return None
        return val

    def _set_raw(self, value: str) -> None:
        if not self.config_parent.config.has_section(self.section):
            self.config_parent.config.add_section(self.section)
        self.config_parent.config.set(self.section, self.option, value)
        self.config_parent._save_config()

class StringConfig(_ConfigOptionBase):
    def get(self) -> str | None:
        return self._get_raw()

    def set(self, value: str) -> str:
        self._set_raw(value)
        return value

class BoolConfig(_ConfigOptionBase):
    def get(self) -> bool | None:
        val = self._get_raw()
        if val is None:
            return None
        val_lower = val.strip().lower()
        if val_lower in ("true", "yes", "1", "on"):
            return True
        if val_lower in ("false", "no", "0", "off"):
            return False
        return None

    def set(self, value: bool) -> bool:
        self._set_raw(str(value))
        return value

class Config:
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        config_path = Path(config_file)
        if not config_path.is_absolute():
            self.config_file = get_exe_path(config_file)
        else:
            self.config_file = config_path
        self._load_config()

        self.GameExePath = StringConfig(self, 'Directory', 'game_exe_path')
        self.ModsDir = StringConfig(self, 'Directory', 'mods_dir')
        self.BackupsDir = StringConfig(self, 'Directory', 'backups_dir')
        self.TargetExeName = StringConfig(self, 'Settings', 'target_exe_name')
        self.ModExtension = StringConfig(self, 'Settings', 'mod_extension')

        self.HideConsoleWhenRunning = BoolConfig(self, 'Settings', 'hide_console_when_running')
        self.NonPermanentMode = BoolConfig(self, 'Settings', 'non_permanent_mode')

    def reload(self) -> None:
        self.config.read(self.config_file, encoding='utf-8')

    def _load_config(self) -> None:
        if self.config_file.exists():
            self.config.read(self.config_file, encoding='utf-8')

    def _save_config(self) -> None:
        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)


class ModsStatusManager:
    """Manages mod enable/disable status using a JSON file instead of file renaming."""
    
    def __init__(self, mods_dir: Path, mod_extension: str) -> None:
        self.mods_dir = mods_dir
        self.mod_extension = mod_extension
        self.status_file = get_exe_path("ModsStatus.json")
        self._status_data: list[ModStatusEntry] = []
        self._dirty = False
        self.load()
    
    def load(self) -> None:
        """Load status data from JSON file."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    self._status_data = json.load(f)
                logger.debug(f"Loaded {len(self._status_data)} mod entries from {self.status_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load mod status file: {e}")
                self._status_data = []
        else:
            self._status_data = []
    
    def save(self) -> None:
        """Save status data to JSON file."""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self._status_data, f, indent=2, ensure_ascii=False)
        self._dirty = False
        logger.debug(f"Saved {len(self._status_data)} mod entries to {self.status_file}")
    
    def mark_dirty(self) -> None:
        """Mark data as modified, requiring save."""
        self._dirty = True
    
    def save_if_dirty(self) -> None:
        """Save only if data has been modified."""
        if self._dirty:
            self.save()
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    def _get_relative_path(self, file_path: Path) -> str:
        """Get relative path from mods_dir as posix string."""
        return file_path.relative_to(self.mods_dir).as_posix()
    
    def sync_with_files(self) -> list[ModStatusEntry]:
        """Sync status data with actual files in mods_dir.
        
        - Add new files with enabled=False (default disabled)
        - Remove entries for files that no longer exist
        - Update hash if file content changed
        - Return list of orphaned enabled mods (enabled but file deleted/moved)
        """
        pattern = f"*{self.mod_extension}"
        current_files = list(self.mods_dir.rglob(pattern))
        
        # Filter out backup files (hidden files starting with dot)
        current_files = [f for f in current_files if not f.name.startswith(".")]
        
        # Build a dict of current entries by path for quick lookup
        existing_entries: dict[str, ModStatusEntry] = {
            entry["path"]: entry for entry in self._status_data
        }
        
        # Build set of current file paths
        current_paths = {self._get_relative_path(f) for f in current_files}
        
        # Detect orphaned mods before removal (enabled but file no longer exists)
        orphaned_mods: list[ModStatusEntry] = []
        for entry in self._status_data:
            if entry["path"] not in current_paths and entry["enabled"]:
                orphaned_mods.append(entry.copy())
        
        # Remove entries for files that no longer exist
        self._status_data = [
            entry for entry in self._status_data
            if entry["path"] in current_paths
        ]
        
        # Rebuild existing_entries after removal
        existing_entries = {
            entry["path"]: entry for entry in self._status_data
        }
        
        # Process each current file
        for file_path in current_files:
            rel_path = self._get_relative_path(file_path)
            current_hash = self._get_file_hash(file_path)
            
            if rel_path in existing_entries:
                entry = existing_entries[rel_path]
                # Check if file content changed
                if entry["hash"] != current_hash:
                    # File changed - update hash (keep enabled status, applied_hash stays for comparison)
                    entry["hash"] = current_hash
                # Ensure applied_hash field exists (migration from old format)
                if "applied_hash" not in entry:
                    entry["applied_hash"] = ""
            else:
                # New file - add with enabled=False (default disabled)
                new_entry: ModStatusEntry = {
                    "path": rel_path,
                    "hash": current_hash,
                    "applied_hash": "",
                    "enabled": False
                }
                self._status_data.append(new_entry)
        
        self.mark_dirty()
        return orphaned_mods
    
    def get_status(self, file_path: Path) -> bool:
        """Get enabled status for a mod file. Returns False if not found."""
        rel_path = self._get_relative_path(file_path)
        for entry in self._status_data:
            if entry["path"] == rel_path:
                return entry["enabled"]
        return False  # Default to disabled if not found
    
    def get_entry(self, file_path: Path) -> ModStatusEntry | None:
        """Get mod entry by file path."""
        rel_path = self._get_relative_path(file_path)
        for entry in self._status_data:
            if entry["path"] == rel_path:
                return entry
        return None
    
    def set_status(self, file_path: Path, enabled: bool) -> None:
        """Set enabled status for a mod file."""
        rel_path = self._get_relative_path(file_path)
        for entry in self._status_data:
            if entry["path"] == rel_path:
                entry["enabled"] = enabled
                self.mark_dirty()
                return
        
        # If not found, add new entry
        current_hash = self._get_file_hash(file_path)
        new_entry: ModStatusEntry = {
            "path": rel_path,
            "hash": current_hash,
            "applied_hash": "",
            "enabled": enabled
        }
        self._status_data.append(new_entry)
        self.mark_dirty()
    
    def set_applied_hash(self, file_path: Path, applied_hash: str) -> None:
        """Set the applied hash for a mod file (hash of mod that was copied to game)."""
        rel_path = self._get_relative_path(file_path)
        for entry in self._status_data:
            if entry["path"] == rel_path:
                entry["applied_hash"] = applied_hash
                self.mark_dirty()
                return
    
    def get_enabled_mods_with_same_name(self, filename: str, exclude_path: Path | None = None) -> list[ModStatusEntry]:
        """Get all enabled mods with the same filename."""
        result = []
        exclude_rel = self._get_relative_path(exclude_path) if exclude_path else None
        for entry in self._status_data:
            if entry["enabled"] and Path(entry["path"]).name == filename:
                if exclude_rel and entry["path"] == exclude_rel:
                    continue
                result.append(entry)
        return result


class StellaSoraModLoader:
    def __init__(
        self,
        game_resource_dir: Path,
        mods_dir: Path,
        backups_dir: Path,
        mod_extension: str,
        logger: Callable[[str], None] | None = None
    ) -> None:
        self.game_resource_dir = game_resource_dir
        self.mods_dir = mods_dir
        self.backups_dir = backups_dir
        self.mod_extension = mod_extension
        self.logger: Callable[[str], None] = logger if logger else lambda msg: None
        self.status_manager = ModsStatusManager(mods_dir, mod_extension)

    def log(self, message: str) -> None:
        self.logger(message)

    def sync_mods(self) -> list[ModStatusEntry]:
        """Sync mod status with actual files in mods_dir.
        
        Returns list of orphaned enabled mods (enabled but file deleted/moved).
        """
        return self.status_manager.sync_with_files()

    def restore_orphaned_backups(self, orphaned_entries: list[ModStatusEntry]) -> None:
        """Restore game files for mods that were deleted/moved while enabled.
        
        Searches for backup files in Backups directory matching the orphaned mod paths.
        """
        if not orphaned_entries:
            return
        
        self.log(f"Detected {len(orphaned_entries)} missing enabled mod(s), restoring game files...")
        
        for entry in orphaned_entries:
            mod_rel_path = Path(entry["path"])
            # Backup files are stored in Backups/{subfolder}/ with same structure as Mods
            backup_subdir = self.backups_dir / mod_rel_path.parent
            mod_name = mod_rel_path.name
            
            if not backup_subdir.exists():
                self.log(f"  - No backup folder for {entry['path']}")
                continue
            
            # Find backup files matching pattern: {mod_name}.backup.*
            pattern = f"{mod_name}.backup.*"
            backups_found = list(backup_subdir.glob(pattern))
            
            if not backups_found:
                self.log(f"  - No backup found for {entry['path']}")
                continue
            
            for backup in backups_found:
                self.restore_backup_file(backup)

    def get_mods_list(self) -> list[Path]:
        pattern = f"*{self.mod_extension}"
        # Return all mod files, filter out backup files (hidden files starting with dot)
        all_files = list(self.mods_dir.rglob(pattern))
        return [f for f in all_files if not f.name.startswith(".")]

    def is_disabled(self, path: Path) -> bool:
        """Check if mod is disabled based on JSON status."""
        return not self.status_manager.get_status(path)

    def check_duplicate_conflict(self, mod_path: Path) -> list[ModStatusEntry]:
        """Check if there are other enabled mods with the same filename.
        
        Returns list of conflicting enabled mods (excluding the current one).
        """
        return self.status_manager.get_enabled_mods_with_same_name(mod_path.name, exclude_path=mod_path)
    
    def toggle_mod(self, mod_path: Path, enable: bool) -> bool:
        """Enable or disable a mod with backup/restore.
        
        When enabling:
        - Check hashes and apply mod to game files
        - Backup original game files if needed
        
        When disabling:
        - Restore original files from backup
        
        Returns:
            bool: True if operation successful (mod enabled/disabled), False if failed (e.g. checks failed).
        """
        # Ensure status entry exists before applying mod (needed for set_applied_hash)
        if enable:
            entry = self.status_manager.get_entry(mod_path)
            if not entry:
                # Create entry with enabled=False first, will be set to True later
                self.status_manager.set_status(mod_path, False)
        
        success = True
        if enable:
            success = self._apply_mod(mod_path)
        else:
            self._unapply_mod(mod_path)
        
        if success:
            self.status_manager.set_status(mod_path, enable)
            
        return success
    
    def _get_backup_path(self, mod_file: Path, game_file: Path) -> Path:
        """Get the backup file path in Backups directory with same subfolder structure as Mods."""
        # Get relative path of mod from mods_dir (e.g. Chitose/char_2d_14401.unity3d)
        mod_relative = mod_file.relative_to(self.mods_dir)
        
        # Create same subfolder structure in Backups
        backup_subdir = self.backups_dir / mod_relative.parent
        backup_subdir.mkdir(parents=True, exist_ok=True)
        
        # Backup name: {original_name}.backup.{game_path_parts} (no leading dot)
        relative_path = game_file.relative_to(self.game_resource_dir).parts
        backup_file_name = game_file.name + ".backup." + ".".join(relative_path[:-1])
        
        return backup_subdir / backup_file_name
    
    def _apply_mod(self, mod_path: Path) -> bool:
        """Apply mod to game files with hash-based state detection.
        
        Returns:
            bool: True if applied successfully (or already applied), False if game files not found.
        """
        mod_hash = self.get_file_hash(mod_path)
        entry = self.status_manager.get_entry(mod_path)
        applied_hash = entry.get("applied_hash", "") if entry else ""
        
        game_files = self.find_original_files(mod_path)
        if not game_files:
            self.log(f"No game files found for `{mod_path.name}`. This file name is correct?")
            return False
        
        self.log(f"Applying {mod_path.relative_to(self.mods_dir).as_posix()}")
        
        for game_file in game_files:
            game_hash = self.get_file_hash(game_file)
            backup_path = self._get_backup_path(mod_path, game_file)
            
            # Case 1: mod_hash == game_hash - already applied
            if mod_hash == game_hash:
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): already applied")
                continue
            
            # Case 2: No backup exists - backup and apply
            if not backup_path.exists():
                shutil.copy2(game_file, backup_path)
                shutil.copy2(mod_path, game_file)
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): backed up & applied")
                continue
            
            # Case 3: Backup exists - check if game has old mod or was updated
            backup_hash = self.get_file_hash(backup_path)
            
            if game_hash == applied_hash and applied_hash:
                # Game has old mod - restore first then apply new mod
                shutil.copy2(backup_path, game_file)
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): restored old file")
                # Now backup the restored original and apply new mod
                shutil.copy2(game_file, backup_path)
                shutil.copy2(mod_path, game_file)
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): applied new mod")
            else:
                # Game was updated - re-backup and apply
                shutil.copy2(game_file, backup_path)
                shutil.copy2(mod_path, game_file)
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): re-backed up & applied")
        
        # Update applied_hash to current mod hash
        self.status_manager.set_applied_hash(mod_path, mod_hash)
        return True
    
    def _unapply_mod(self, mod_path: Path) -> None:
        """Restore original game files from backup."""
        game_files = self.find_original_files(mod_path)
        
        self.log(f"Disabling {mod_path.relative_to(self.mods_dir).as_posix()}")
        
        for game_file in game_files:
            backup_path = self._get_backup_path(mod_path, game_file)
            
            if backup_path.exists():
                shutil.copy2(backup_path, game_file)
                backup_path.unlink()
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): restored")
            else:
                self.log(f"  - {game_file.name} ({self._get_folder_name(game_file)}): no backup found")
        
        # Clear applied_hash
        self.status_manager.set_applied_hash(mod_path, "")

    def verify_enabled_mods(self) -> None:
        """Verify all enabled mods are properly applied to game files.
        
        For each enabled mod, check if mod_hash == game_hash.
        If not, re-apply the mod.
        """
        mods = self.get_mods_list()
        enabled_mods = [m for m in mods if not self.is_disabled(m)]
        
        if not enabled_mods:
            self.log("No enabled mods to verify.")
            return
        
        self.log("Verifying enabled mods...")
        
        for mod_path in enabled_mods:
            mod_hash = self.get_file_hash(mod_path)
            game_files = self.find_original_files(mod_path)
            
            needs_reapply = False
            for game_file in game_files:
                if not game_file.exists():
                    continue
                game_hash = self.get_file_hash(game_file)
                if mod_hash != game_hash:
                    needs_reapply = True
                    break
            
            if needs_reapply:
                self.log(f"Applying {mod_path.relative_to(self.mods_dir).as_posix()}...")
                self._apply_mod(mod_path)
            else:
                self.log(f"Verified: {mod_path.relative_to(self.mods_dir).as_posix()}")

    def install_mod(self) -> None:
        mods = self.get_mods_list()
        active_mods = [m for m in mods if not self.is_disabled(m)]

        for mod_file in active_mods:
            self.log(f"Installing {mod_file.relative_to(self.mods_dir).as_posix()}")
            backedup_files = self.backup_original_files(mod_file)
            for target_file in backedup_files.keys():
                shutil.copy2(mod_file, target_file)
                self.log(f"  - {target_file.name} ({self._get_folder_name(target_file)})")

    def backup_original_files(self, mod_file: Path) -> dict[Path, list[Path]]:
        from collections import defaultdict
        backedup_files = defaultdict(list)
        original_files = self.find_original_files(mod_file)

        for original_file in original_files:
            if self.get_file_hash(original_file) == self.get_file_hash(mod_file):
                self.log(f"  - Skip backing up {original_file.name} ({self._get_folder_name(original_file)}: same content)")
                continue

            backup_path = self._get_backup_path(mod_file, original_file)
            shutil.copy2(original_file, backup_path)

            backedup_files[original_file].append(backup_path)
            self.log(f"  - Backed up {original_file.name} ({self._get_folder_name(original_file)})")
        return backedup_files

    def restore_all(self) -> None:
        # Restore for all mods from Backups directory
        self.log("Restoring original files...")
        backup_files = list(self.backups_dir.rglob("*.backup.*"))
        for backup in backup_files:
             self.restore_backup_file(backup)

    def restore_backup_file(self, backup: Path) -> None:
        # Extract original info from backup name
        # Name format: {original_name}.backup.{path_parts_joined_by_dots}
        # e.g. mod.unity3d.backup.Folder1.Folder2

        backup_name = backup.name
        # Remove leading dot if present (for legacy backups)
        if backup_name.startswith("."):
            backup_name = backup_name[1:]

        parts = backup_name.split(".backup.")
        if len(parts) != 2:
            return

        original_name = parts[0]
        path_suffix = parts[1]

        relative_parts = [part for part in path_suffix.split(".") if part]
        target_path = self.game_resource_dir.joinpath(*relative_parts, original_name)

        if target_path.exists() or target_path.parent.exists():
             shutil.copy2(backup, target_path)
             backup.unlink()
             self.log(f"  - Restored {target_path.name} ({self._get_folder_name(target_path)})")

    def find_original_files(self, mod_file: Path) -> list[Path]:
        # Logic: find files in game dir with same name as mod file
        # Note: If mod file is named DISABLED_mod.unity3d, we should search for mod.unity3d?
        # The original logic used mod_file.name.
        # If we rename the mod file to DISABLED_..., we probably shouldn't install it anyway.
        # So install_mod only iterates active mods.
        return list(self.game_resource_dir.rglob(mod_file.name))

    def get_file_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    def _get_folder_name(self, path: Path) -> str:
        return path.relative_to(self.game_resource_dir).parts[0]

    def cleanup_empty_backup_folders(self) -> None:
        """Remove empty folders in Backups directory."""
        if not self.backups_dir.exists():
            return
        
        # Walk directory tree bottom-up to remove empty folders
        for folder in sorted(self.backups_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if folder.is_dir():
                try:
                    # Check if folder is empty
                    if not any(folder.iterdir()):
                        folder.rmdir()
                except (OSError, PermissionError):
                    pass  # Ignore errors when removing folders
    
class StellaSoraGame:
    def __init__(self, game_exe_path: Path) -> None:
        self.game_exe_path = Path(game_exe_path)

    def start(self) -> None:
        logger.info(f"Starting game: {self.game_exe_path}")
        subprocess.Popen(
            f'start "" "{self.game_exe_path}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

    def get_process(self) -> psutil.Process | None:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == self.game_exe_path.name.lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def is_running(self) -> bool:
        running = self.get_process() is not None
        logger.debug(f"Game running check: {running}")
        return running

    def wait_for_game_closed(self) -> bool:
        proc = None
        for _ in range(30): # Wait up to 30s for game to start
            proc = self.get_process()
            if proc:
                break
            time.sleep(1)

        if not proc:
            return False

        try:
            proc.wait()
        except psutil.NoSuchProcess:
            pass

        # Double check
        while self.is_running():
            time.sleep(1)

        return True