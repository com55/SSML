from collections import defaultdict
import ctypes
import configparser
import hashlib
from pathlib import Path
import shutil
import time
import psutil
import subprocess
import sys
from tkinter import filedialog
from rich.console import Console
from rich.text import Text

console = Console()

if getattr(sys, 'frozen', False):
    PROGRAM_PATH = Path(sys.executable).parent
else:
    PROGRAM_PATH = Path(__file__).parent

def hide_console():
    """Hide Console/Terminal (SW_HIDE = 0)"""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(hwnd, 0) 
    except Exception:
        pass

def show_console():
    """Show Console/Terminal (SW_SHOW = 5)"""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # SW_SHOW = 5
            ctypes.windll.user32.ShowWindow(hwnd, 5) 
    except Exception:
        pass

def full_width_line(char: str = "=") -> str:
    width = max(console.size.width, 10)
    return char * width

def clear_line(num_lines: int = 1) -> None:
    print("\033[1A\033[K" * num_lines, end="")

def status_text(status: bool) -> Text:
    style = "bold green" if status else "bold red"
    return Text("Enabled" if status else "Disabled", style=style)

class ConfigOption:
    def __init__(self, config_parent, section: str, option: str, default: str, type_func=str):
        self.config_parent = config_parent # เก็บตัวแม่ไว้เรียก save
        self.section = section
        self.option = option
        self.default = default
        self.type_func = type_func # ตัวแปลง type เช่น str, bool, int

    def get(self):
        """ดึงค่าล่าสุดจากไฟล์"""
        val = self.config_parent.config.get(self.section, self.option, fallback=self.default)
        
        # จัดการเรื่อง Boolean เป็นพิเศษ เพราะ configparser เก็บเป็น string
        if self.type_func == bool:
            return str(val).lower() in ('true', 'yes', '1', 'on')
            
        return self.type_func(val)

    def set(self, value):
        """บันทึกค่าลงไฟล์"""
        if not self.config_parent.config.has_section(self.section):
            self.config_parent.config.add_section(self.section)
            
        self.config_parent.config.set(self.section, self.option, str(value))
        self.config_parent._save_config()

    # --- Magic Methods เพื่อให้ใช้งานได้เหมือนตัวแปรปกติ ---
    
    def __call__(self):
        """ถ้าเรียกเป็นฟังก์ชัน config.Option() ให้คืนค่า"""
        return self.get()

    def __bool__(self):
        """ถ้าเอาไปใส่ if config.Option: ให้เช็คค่า bool"""
        return bool(self.get())

    def __str__(self):
        """ถ้าสั่ง print(config.Option) ให้แสดงค่า"""
        return str(self.get())
        
    def __eq__(self, other):
        """เปรียบเทียบค่าได้เลย if config.Option == True:"""
        return self.get() == other

class Config:
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self._load_config()
        
        # --- กำหนด Setting ต่างๆ ตรงนี้ (Class ซ้อน Class แบบที่นายอยากได้) ---
        
        # แบบ String
        self.GameExePath = ConfigOption(self, 'Directory', 'game_exe_path', '')
        self.ModsDir = ConfigOption(self, 'Directory', 'mods_dir', '')
        self.TargetExeName = ConfigOption(self, 'Settings', 'target_exe_name', 'StellaSora.exe')
        self.ModExtension = ConfigOption(self, 'Settings', 'mod_extension', '.unity3d')
        
        # แบบ Boolean (ใส่ type_func=bool)
        self.RestoreModsWhenClose = ConfigOption(self, 'Settings', 'restore_when_close', 'True', type_func=bool)
        self.HideConsoleWhenRunning = ConfigOption(self, 'Settings', 'hide_console', 'True', type_func=bool)

    def _load_config(self):
        self.config.read(self.config_file)
    
    def _save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

class StellaSoraModLoader:
    def __init__(self, game_resource_dir: Path, mods_dir: Path, mod_extension: str) -> None:
        self.game_resource_dir = game_resource_dir
        self.mods_dir = mods_dir
        self.mod_extension = mod_extension
        self.mods_list = self.get_mods_list()
    
    def get_mods_list(self) -> list[Path]:
        pattern = f"*{self.mod_extension}"
        return [
            mod_file
            for mod_file in self.mods_dir.rglob(pattern)
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
        self.process_handle: subprocess.Popen | None = None
    
    def start(self) -> None:
        self.process_handle = subprocess.Popen([self.game_exe_path])

    def is_running(self) -> bool:
        # Check from Process Handle
        if self.process_handle:
            return self.process_handle.poll() is None
        
        # Fallback: if not have Process Handle
        for proc in psutil.process_iter(['name']):  # pyright: ignore[reportUnknownMemberType]
            try:
                if proc.info['name'].lower() == self.game_exe_path.name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def wait_for_game_closed(self) -> bool:
        """
        Blocks execution until the game process closes, using low CPU consumption.
        Returns True if process was successfully monitored and closed, False otherwise.
        """
        if not self.process_handle:
            return False 

        while self.process_handle.poll() is None:
            self.process_handle.wait(timeout=1)

        # Final safety check to ensure process is closed
        while self.is_running():
            time.sleep(1)
        
        return True

def main():
    config_file = 'config.ini'
    config = Config(config_file)
    GAME_EXE_PATH = config.GameExePath()
    TARGET_EXE_NAME = config.TargetExeName()
    MODS_DIR = config.ModsDir()
    MOD_EXTENSION = config.ModExtension()
    RESTORE_MODS_WHEN_CLOSE = config.RestoreModsWhenClose()
    HIDE_CONSOLE_WHEN_RUNNUNG = config.HideConsoleWhenRunning()
    
    if not GAME_EXE_PATH or not Path(GAME_EXE_PATH).exists() or TARGET_EXE_NAME.lower() not in GAME_EXE_PATH.lower():
        console.print(full_width_line("-"), style="blue")
        console.print("Game executable path missing or not valid, please select the game executable", style="bold bright_blue")
        GAME_EXE_PATH = filedialog.askopenfilename(filetypes=[(TARGET_EXE_NAME, TARGET_EXE_NAME)])
        config.GameExePath.set(GAME_EXE_PATH)
        clear_line()
        console.print(Text(f"Game executable path set to ", style="bright_blue") + Text(GAME_EXE_PATH, style="yellow"))
        console.print(full_width_line("-"), style="blue")
    
    if not MODS_DIR:
        mods_dir = Path(PROGRAM_PATH).absolute() / "Mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        MODS_DIR = mods_dir.as_posix()
        config.ModsDir.set(MODS_DIR)
        console.print("Mods directory not found", style="bold yellow")
        console.print(Text(f"Using default directory: ", style="bright_blue") + Text(MODS_DIR, style="yellow"))
        console.print(full_width_line("-"), style="blue")
    
    if RESTORE_MODS_WHEN_CLOSE is None:
        console.print("Do you need to restore the original files when game is closed?", style="bold bright_blue")
        console.print("  - [Y] Yes, restore the original files when game is closed (recommended)", style="yellow")
        console.print("  - [N] No, do not restore the original files when game is closed", style="yellow")
        console.print("  - Default is Enabled", style="bold yellow")
        RESTORE_MODS_WHEN_CLOSE = input("Enter your choice: ")
        if RESTORE_MODS_WHEN_CLOSE.lower() == "y":
            RESTORE_MODS_WHEN_CLOSE = True
        elif RESTORE_MODS_WHEN_CLOSE.lower() == "n":
            RESTORE_MODS_WHEN_CLOSE = False
        elif RESTORE_MODS_WHEN_CLOSE.lower() == "":
            RESTORE_MODS_WHEN_CLOSE = True
        else:
            console.print("Invalid choice, default is Enabled", style="yellow")
            RESTORE_MODS_WHEN_CLOSE = True
        config.RestoreModsWhenClose.set(RESTORE_MODS_WHEN_CLOSE)
        clear_line()
        console.print(
            Text("Restore when game is closed set to ", style="bright_blue")
            + status_text(RESTORE_MODS_WHEN_CLOSE)
        )
        console.print()
    RESTORE_MODS_WHEN_CLOSE = bool(RESTORE_MODS_WHEN_CLOSE)
    
    console.rule(Text("Configuration", style="bold"), style="white")
    console.rule(Text(f"You can change settings in the {config_file} file", style="green"), characters=" ")
    console.rule(Text("Or delete it to restart the configuration wizard.", style="green"), characters=" ")
    console.print(full_width_line("─"))
    console.print(Text("Game executable path: ", style="bright_blue") + Text(GAME_EXE_PATH, style="yellow"))
    console.print(Text("Mods directory: ", style="bright_blue") + Text(MODS_DIR, style="yellow"))
    console.print(Text("Restore when game is closed: ", style="bright_blue") + status_text(RESTORE_MODS_WHEN_CLOSE))
    
    loader = StellaSoraModLoader(Path(GAME_EXE_PATH).parent, Path(MODS_DIR), MOD_EXTENSION)
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
    if not RESTORE_MODS_WHEN_CLOSE:
        console.print("Mods will not be restored when game isclosed, program will exit...", style="bold yellow")
        input("Press Enter to exit...")
        return
    
    # wait for game to spawn process
    time.sleep(1)
    clear_line()
    console.print(full_width_line("─"))
    
    clear_line(2)
    console.print(Text("Game status: ", style="bright_blue") + Text("Running", style="bold green"))
    console.print(full_width_line("─"))

    time.sleep(1)

    if HIDE_CONSOLE_WHEN_RUNNUNG:
        hide_console()

    game.wait_for_game_closed()

    if HIDE_CONSOLE_WHEN_RUNNUNG:
        show_console()

    time.sleep(1)

    clear_line(2)
    console.print(Text("Game status: ", style="bright_blue") + Text("Game closed detected.", style="bold red"))
    console.print(full_width_line("─"))
    
    console.rule(Text("Restore Original Files", style="bold"), style="white")
    loader.restore_all()
    console.print("Mods restored successfully", style="bold green")
    console.print(full_width_line("─"))
    console.print("Program will exit...", style="bold yellow")

if __name__ == "__main__":
    main()
