import configparser
import hashlib
import os
from pathlib import Path
import shutil
import time
import subprocess
import psutil
import sys

# Determine program path
_nuitka_onefile_parent = os.environ.get("NUITKA_ONEFILE_PARENT")
if _nuitka_onefile_parent:
    PROGRAM_PATH = Path(_nuitka_onefile_parent).parent
elif getattr(sys, 'frozen', False):
    PROGRAM_PATH = Path(sys.executable).parent
else:
    PROGRAM_PATH = Path(__file__).parent.absolute()

def resource_path(relative_path: str) -> Path:
    if os.environ.get("NUITKA_ONEFILE_PARENT"):
        return Path(os.environ.get("NUITKA_ONEFILE_PARENT")) / relative_path
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path # type: ignore
    return PROGRAM_PATH / relative_path

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
        self.config_file = config_file
        self._load_config()

        self.GameExePath = StringConfig(self, 'Directory', 'game_exe_path')
        self.ModsDir = StringConfig(self, 'Directory', 'mods_dir')
        self.TargetExeName = StringConfig(self, 'Settings', 'target_exe_name')
        self.ModExtension = StringConfig(self, 'Settings', 'mod_extension')

        self.RestoreOriginalFileWhenGameClosed = BoolConfig(self, 'Settings', 'restore_original_file_when_game_closed')
        self.HideConsoleWhenRunning = BoolConfig(self, 'Settings', 'hide_console_when_running')

    def reload(self):
        self.config.read(self.config_file)

    def _load_config(self):
        self.config.read(self.config_file)

    def _save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

class StellaSoraModLoader:
    def __init__(self, game_resource_dir: Path, mods_dir: Path, mod_extension: str, logger=None) -> None:
        self.game_resource_dir = game_resource_dir
        self.mods_dir = mods_dir
        self.mod_extension = mod_extension
        self.logger = logger if logger else lambda msg: None

    def log(self, message: str):
        self.logger(message)

    def get_mods_list(self) -> list[Path]:
        pattern = f"*{self.mod_extension}"
        # Return all mod files, UI will handle enable/disable display based on filename
        return list(self.mods_dir.rglob(pattern))

    def is_disabled(self, path: Path) -> bool:
        """Check if mod is disabled based on filename prefix or parent folder."""
        # Check filename prefix
        if path.name.startswith("DISABLED"):
            return True

        # Check parent folders
        try:
            relative_parts = path.relative_to(self.mods_dir).parts
        except ValueError:
            return False
        return any(part.lower().startswith('disabled') for part in relative_parts)

    def toggle_mod(self, mod_path: Path, enable: bool):
        """Enable or disable a mod by renaming it."""
        parent = mod_path.parent
        name = mod_path.name

        if enable:
            # Enable: Remove 'DISABLED' prefix if present
            if name.startswith("DISABLED"):
                new_name = name.replace("DISABLED", "", 1).lstrip("_")
                new_path = parent / new_name
                mod_path.rename(new_path)
                return new_path
        else:
            # Disable: Add 'DISABLED_' prefix if not present
            if not name.startswith("DISABLED"):
                new_name = "DISABLED_" + name
                new_path = parent / new_name
                mod_path.rename(new_path)
                return new_path
        return mod_path

    def install_mod(self) -> None:
        mods = self.get_mods_list()
        active_mods = [m for m in mods if not self.is_disabled(m)]

        for mod_file in active_mods:
            self.log(f"Installing {mod_file.relative_to(self.mods_dir).as_posix()}")
            backedup_files = self.backup_original_files(mod_file)
            for target_file in backedup_files.keys():
                shutil.copy2(mod_file, target_file)
                self.log(f"  - Applied {mod_file.name} to {target_file.name}")

    def backup_original_files(self, mod_file: Path) -> dict[Path, list[Path]]:
        from collections import defaultdict
        backedup_files = defaultdict(list)
        original_files = self.find_original_files(mod_file)

        for original_file in original_files:
            if self.get_file_hash(original_file) == self.get_file_hash(mod_file):
                self.log(f"  - Skip backing up {original_file.name} (same content)")
                continue

            relative_path = original_file.relative_to(self.game_resource_dir).parts
            # Using specific backup naming convention
            backup_file_name = original_file.name + ".backup." + ".".join(relative_path[:-1])
            backup_path = mod_file.parent / backup_file_name
            shutil.copy2(original_file, backup_path)

            backedup_files[original_file].append(backup_path)
            self.log(f"  - Backed up {original_file.name}")
        return backedup_files

    def restore_all(self) -> None:
        # Restore for all mods (even disabled ones if they left backups)
        # Or just scan for all .backup files in mods dir?
        # The original logic iterated over mods_list.
        # It's safer to scan for backup files.
        self.log("Restoring original files...")
        backup_files = list(self.mods_dir.rglob("*.backup.*"))
        for backup in backup_files:
             self.restore_backup_file(backup)

    def restore_backup_file(self, backup: Path):
        # Extract original info from backup name
        # Name format: {original_name}.backup.{path_parts_joined_by_dots}
        # e.g. mod.unity3d.backup.Folder1.Folder2

        parts = backup.name.split(".backup.")
        if len(parts) != 2:
            return

        original_name = parts[0]
        path_suffix = parts[1]

        relative_parts = [part for part in path_suffix.split(".") if part]
        target_path = self.game_resource_dir.joinpath(*relative_parts, original_name)

        if target_path.exists() or target_path.parent.exists():
             shutil.copy2(backup, target_path)
             backup.unlink()
             self.log(f"  - Restored {target_path.name}")

    def find_original_files(self, mod_file: Path) -> list[Path]:
        # Logic: find files in game dir with same name as mod file
        # Note: If mod file is named DISABLED_mod.unity3d, we should search for mod.unity3d?
        # The original logic used mod_file.name.
        # If we rename the mod file to DISABLED_..., we probably shouldn't install it anyway.
        # So install_mod only iterates active mods.
        return list(self.game_resource_dir.rglob(mod_file.name))

    def get_file_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

class StellaSoraGame:
    def __init__(self, game_exe_path: Path) -> None:
        self.game_exe_path = Path(game_exe_path)

    def start(self) -> None:
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
        return self.get_process() is not None

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
