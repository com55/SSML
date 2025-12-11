from collections import defaultdict
import configparser
import hashlib
from pathlib import Path
import shutil
import time
import psutil
import subprocess
from tkinter import filedialog
from rich.console import Console
from rich.text import Text

console = Console()


def full_width_line(char: str = "=") -> str:
    width = max(console.size.width, 10)
    return char * width

def clear_line(num_lines: int = 1) -> None:
    print("\033[1A\033[K" * num_lines, end="")

def status_text(status: bool) -> Text:
    style = "bold green" if status else "bold red"
    return Text("Enabled" if status else "Disabled", style=style)

class Config:
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self._load_config()
    
    def get_game_exe_path(self):
        return self.config.get('Directory', 'game_exe_path', fallback=None)
    
    def set_game_exe_path(self, path: str):
        if not self.config.has_section('Directory'):
            self.config.add_section('Directory')
        self.config.set('Directory', 'game_exe_path', path)
        self._save_config()

    def get_mods_dir(self):
        return self.config.get('Directory', 'mods_dir', fallback=None)
    
    def set_mods_dir(self, path: str):
        if not self.config.has_section('Directory'):
            self.config.add_section('Directory')
        self.config.set('Directory', 'mods_dir', path)
        self._save_config()

    def get_setting_value(self, option: str):
        return self.config.get('Settings', option, fallback=None)
    
    def set_setting_value(self, option: str, value: str):
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', option, value)
        self._save_config()

    def _load_config(self):
        self.config.read(self.config_file)
    
    def _save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

class StellaSoraModLoader:
    def __init__(self, game_resource_dir: Path, mods_dir: Path) -> None:
        self.game_resource_dir = game_resource_dir
        self.mods_dir = mods_dir
        self.mods_list = self.get_mods_list()
    
    def get_mods_list(self) -> list[Path]:
        return [
            mod_file
            for mod_file in self.mods_dir.rglob('*.unity3d')
            if not self._is_disabled_path(mod_file)
        ]

    def _is_disabled_path(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.mods_dir).parts
        except ValueError:
            return False
        return any(part.lower().startswith('disabled') for part in relative_parts)
    
    def install_mod(self) -> None:
        for mod_file in self.mods_list:
            console.print(f"[bold blue]Installing {mod_file.relative_to(self.mods_dir).as_posix()}[/bold blue]")
            backedup_files = self.backup_original_files(mod_file)
            for target_file in backedup_files.keys():
                shutil.copy2(mod_file, target_file)
                console.print(f"[yellow]  - Applied {mod_file.relative_to(self.mods_dir).as_posix()} to {target_file.as_posix()}[/yellow]")
    
    def backup_original_files(self, mod_file: Path) -> dict[Path, list[Path]]:
        backedup_files = defaultdict[Path, list[Path]](list)
        original_files = self.find_original_files(mod_file)
        for original_file in original_files:
            if self.get_file_hash(original_file) == self.get_file_hash(mod_file):
                console.print(f"[yellow]  - Skip backing up {original_file.as_posix()} because it is the same as the mod file[/yellow]")
                continue
            relative_path = original_file.relative_to(self.game_resource_dir).parts
            backup_file_name = original_file.name + ".backup." + ".".join(relative_path[:-1])
            shutil.copy2(original_file, mod_file.parent / backup_file_name)
            
            backedup_files[original_file].append(mod_file.parent / backup_file_name)
            console.print(f"[green]  - Backed up {original_file.as_posix()}[/green]")
        return backedup_files
    
    def restore_all(self) -> None:
        for mod_file in self.mods_list:
            self.restore_original_files(mod_file)
    
    def restore_original_files(self, mod_file: Path) -> None:
        console.print(f"[bold blue]Restoring original files for {mod_file.relative_to(self.mods_dir).as_posix()}[/bold blue]")
        prefix = f"{mod_file.name}.backup."
        for backup in self.mods_dir.rglob(f"{prefix}*"):
            if not backup.is_file():
                continue
            suffix = backup.name[len(prefix):]
            relative_parts = [part for part in suffix.split(".") if part]
            target_path = self.game_resource_dir.joinpath(*relative_parts, mod_file.name)
            shutil.copy2(backup, target_path)
            backup.unlink()
            console.print(f"[green]  - Restored {target_path.as_posix()}[/green]")

    def find_original_files(self, mod_file: Path) -> list[Path]:
        return list(self.game_resource_dir.rglob(mod_file.name))

    def get_file_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

class StellaSoraGame:
    def __init__(self, game_exe_path: Path) -> None:
        self.game_exe_path = Path(game_exe_path)
    
    def start(self) -> None:
        subprocess.Popen([self.game_exe_path])

    def is_running(self) -> bool:
        for proc in psutil.process_iter(['name']):  # pyright: ignore[reportUnknownMemberType]
            try:
                if proc.info['name'].lower() == self.game_exe_path.name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

def main():
    config_file = 'config.ini'
    config = Config(config_file)
    GAME_EXE_PATH = config.get_game_exe_path()
    MODS_DIR = config.get_mods_dir()
    RESTORE_WHEN_CLOSE = config.get_setting_value('restore_when_close')
    
    if not GAME_EXE_PATH or not Path(GAME_EXE_PATH).exists() or "stellasora.exe" not in GAME_EXE_PATH.lower():
        console.print(full_width_line("-"), style="blue")
        console.print("Game executable path missing or not valid, please select the game executable", style="bold bright_blue")
        GAME_EXE_PATH = filedialog.askopenfilename(filetypes=[("StellaSora.exe", "StellaSora.exe")])
        config.set_game_exe_path(GAME_EXE_PATH)
        clear_line()
        console.print(Text(f"Game executable path set to ", style="bright_blue") + Text(GAME_EXE_PATH, style="yellow"))
        console.print(full_width_line("-"), style="blue")
    
    if not MODS_DIR:
        mods_dir = Path("Mods").absolute()
        mods_dir.mkdir(parents=True, exist_ok=True)
        MODS_DIR = mods_dir.as_posix()
        config.set_mods_dir(MODS_DIR)
        console.print("Mods directory not found", style="bold yellow")
        console.print(Text(f"Using default directory: ", style="bright_blue") + Text(MODS_DIR, style="yellow"))
        console.print(full_width_line("-"), style="blue")
    
    if RESTORE_WHEN_CLOSE is None:
        console.print("Do you need to restore the original files when game is closed?", style="bold bright_blue")
        console.print("  - [Y] Yes, restore the original files when game is closed (recommended)", style="yellow")
        console.print("  - [N] No, do not restore the original files when game is closed", style="yellow")
        console.print("  - Default is Enabled", style="bold yellow")
        RESTORE_WHEN_CLOSE = input("Enter your choice: ")
        if RESTORE_WHEN_CLOSE.lower() == "y":
            RESTORE_WHEN_CLOSE = True
        elif RESTORE_WHEN_CLOSE.lower() == "n":
            RESTORE_WHEN_CLOSE = False
        elif RESTORE_WHEN_CLOSE.lower() == "":
            RESTORE_WHEN_CLOSE = True
        else:
            console.print("Invalid choice, default is Enabled", style="yellow")
            RESTORE_WHEN_CLOSE = True
        config.set_setting_value('restore_when_close', str(RESTORE_WHEN_CLOSE))
        clear_line()
        console.print(
            Text("Restore when game is closed set to ", style="bright_blue")
            + status_text(RESTORE_WHEN_CLOSE)
        )
        console.print()
    RESTORE_WHEN_CLOSE = bool(RESTORE_WHEN_CLOSE)
    
    console.rule(Text("Configuration", style="bold"), style="white")
    console.rule(Text(f"You can change settings in the {config_file} file", style="green"), characters=" ")
    console.rule(Text("Or delete it to restart the configuration wizard.", style="green"), characters=" ")
    console.print(full_width_line("─"))
    console.print(Text("Game executable path: ", style="bright_blue") + Text(GAME_EXE_PATH, style="yellow"))
    console.print(Text("Mods directory: ", style="bright_blue") + Text(MODS_DIR, style="yellow"))
    console.print(Text("Restore when game is closed: ", style="bright_blue") + status_text(RESTORE_WHEN_CLOSE))
    
    loader = StellaSoraModLoader(Path(GAME_EXE_PATH).parent, Path(MODS_DIR))
    mods_list = loader.get_mods_list()
    
    game = StellaSoraGame(Path(GAME_EXE_PATH))
    
    if game.is_running():
        console.print("Game is running, please close it before installing mods\nProgram will exit...", style="bold yellow")
        input("Press Enter to exit...")
        return
    
    console.rule(Text("Installing", style="bold"), style="white")
    loader.install_mod()
    console.print("Mods installed successfully", style="bold green")
    
    console.rule(Text("Start Game", style="bold"), style="white")
    console.print("Starting game...", style="bold green")
    game.start()
    if not RESTORE_WHEN_CLOSE:
        console.print("Mods will not be restored when game isclosed, program will exit...", style="bold yellow")
        input("Press Enter to exit...")
        return
    
    # wait for game to spawn process
    time.sleep(5)
    clear_line()
    console.print("Waiting for game to start...")
    console.print(full_width_line("─"))
    game_started = False
    while True:
        if game.is_running():
            game_started = True
            clear_line(2)
            console.print(Text("Game status: ", style="bright_blue") + Text("Running", style="bold green"))
            console.print(full_width_line("─"))
        else:
            if game_started:
                clear_line(2)
                console.print(Text("Game status: ", style="bright_blue") + Text("Game closed detected.", style="bold red"))
                break
        time.sleep(5)
    console.print(full_width_line("─"))
    
    console.rule(Text("Restore Original Files", style="bold"), style="white")
    loader.restore_all()
    console.print("Mods restored successfully", style="bold green")
    console.print(full_width_line("─"))
    console.print("Program will exit...", style="bold yellow")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
