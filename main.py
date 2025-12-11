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
from threading import Thread
import msvcrt
from tkinter import filedialog
from typing import Any, Callable, Generic, TypeVar, cast
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

def minimize_to_tray() -> Any:
    """
    ย่อคอนโซลลง system tray พร้อมเมนูเปิดหน้าต่าง / ออกโปรแกรม
    ถ้าไม่มี pystray/Pillow จะ fallback เป็นการซ่อนคอนโซลเฉยๆ
    """
    try:
        import pystray  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        hide_console()
        return None

    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if not hwnd:
        return None

    def load_icon_image() -> Any:
        icon_path = PROGRAM_PATH / "icon.ico"
        if icon_path.exists():
            return Image.open(icon_path)
        return Image.new("RGB", (64, 64), (0, 170, 255))

    def on_restore(icon: Any, _item: Any) -> None:
        show_console()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Show console", on_restore),
    )

    icon = pystray.Icon(
        "StellaSoraModLoader",
        load_icon_image(),
        "StellaSora Mod Loader - Waiting for game to close...",
        menu=menu,
    )

    ctypes.windll.user32.ShowWindow(hwnd, 0)  # ซ่อนหน้าต่างคอนโซล
    Thread(target=icon.run, daemon=True).start()
    return icon

def full_width_line(char: str = "=") -> str:
    width = max(console.size.width, 10)
    return char * width

def clear_line(num_lines: int = 1) -> None:
    print("\033[1A\033[K" * num_lines, end="")

def status_text(status: bool) -> Text:
    style = "bold green" if status else "bold red"
    return Text("Enabled" if status else "Disabled", style=style)

T = TypeVar("T")

class ConfigOption(Generic[T]):
    def __init__(
        self,
        config_parent: "Config",
        section: str,
        option: str,
        default: T | None = None,
        type_func: Callable[[str], T] | None = str,
    ) -> None:
        self.config_parent = config_parent  # เก็บตัวแม่ไว้เรียก save
        self.section = section
        self.option = option
        self.default = default
        # type_func ใช้แปลงค่าจาก string ใน config ให้เป็น type ที่ต้องการ เช่น str, bool, int
        self.type_func: Callable[[str], T] = (
            type_func if type_func is not None else cast(Callable[[str], T], str)
        )

    def get(self) -> T | None:
        """ดึงค่าล่าสุดจากไฟล์"""
        val = self.config_parent.config.get(self.section, self.option, fallback=self.default)

        if val is None:
            return None

        # จัดการเรื่อง Boolean เป็นพิเศษ เพราะ configparser เก็บเป็น string
        if self.type_func is bool:
            return cast(T, str(val).lower() in ("true", "yes", "1", "on"))

        return self.type_func(str(val))

    def set(self, value: T) -> None:
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
        
        # แบบ String
        self.GameExePath: ConfigOption[str] = ConfigOption(self, 'Directory', 'game_exe_path')
        self.ModsDir: ConfigOption[str] = ConfigOption(self, 'Directory', 'mods_dir')
        self.TargetExeName: ConfigOption[str] = ConfigOption(self, 'Settings', 'target_exe_name')
        self.ModExtension: ConfigOption[str] = ConfigOption(self, 'Settings', 'mod_extension')
        
        # แบบ Boolean (ใส่ type_func=bool)
        self.RestoreOriginalFileWhenGameClosed: ConfigOption[bool] = ConfigOption(self, 'Settings', 'restore_when_close', None, type_func=bool)
        self.HideConsoleWhenRunning: ConfigOption[bool] = ConfigOption(self, 'Settings', 'hide_console', True, type_func=bool)

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
            self.process_handle.wait()

        # Final safety check to ensure process is closed
        while self.is_running():
            time.sleep(1)
        
        return True

def main():
    config_file = 'config.ini'
    config = Config(config_file)
    GAME_EXE_PATH = config.GameExePath()
    TARGET_EXE_NAME = config.TargetExeName() or "StellaSora.exe"
    MODS_DIR = config.ModsDir()
    MOD_EXTENSION = config.ModExtension() or ".unity3d"
    RESTORE_ORIGINAL_FILE_WHEN_CLOSED = config.RestoreOriginalFileWhenGameClosed
    HIDE_CONSOLE_WHEN_RUNNING = bool(config.HideConsoleWhenRunning)
    
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
    
    if RESTORE_ORIGINAL_FILE_WHEN_CLOSED is None:
        console.print("Do you need to restore the original files when game is closed?", style="bold bright_blue")
        console.print("  - [Y] Yes, restore the original files when game is closed (recommended)", style="yellow")
        console.print("  - [N] No, do not restore the original files when game is closed", style="yellow")
        console.print("  - Default is Enabled", style="bold yellow")
        RESTORE_ORIGINAL_FILE_WHEN_CLOSED = input("Enter your choice: ")
        if RESTORE_ORIGINAL_FILE_WHEN_CLOSED.lower() == "y":
            RESTORE_ORIGINAL_FILE_WHEN_CLOSED = True
        elif RESTORE_ORIGINAL_FILE_WHEN_CLOSED.lower() == "n":
            RESTORE_ORIGINAL_FILE_WHEN_CLOSED = False
        elif RESTORE_ORIGINAL_FILE_WHEN_CLOSED.lower() == "":
            RESTORE_ORIGINAL_FILE_WHEN_CLOSED = True
        else:
            console.print("Invalid choice, default is Enabled", style="yellow")
            RESTORE_ORIGINAL_FILE_WHEN_CLOSED = True
        config.RestoreOriginalFileWhenGameClosed.set(RESTORE_ORIGINAL_FILE_WHEN_CLOSED)
        clear_line()
        console.print(
            Text("Restore original files when game is closed set to ", style="bright_blue")
            + status_text(RESTORE_ORIGINAL_FILE_WHEN_CLOSED)
        )
        console.print()
    RESTORE_ORIGINAL_FILE_WHEN_CLOSED = bool(RESTORE_ORIGINAL_FILE_WHEN_CLOSED)
    
    console.rule(Text("Configuration", style="bold"), style="white")
    console.rule(Text(f"You can change settings in the {config_file} file", style="green"), characters=" ")
    console.rule(Text("Or delete it to restart the configuration wizard.", style="green"), characters=" ")
    console.print(full_width_line("-"))
    console.print(Text("Game executable path: ", style="bright_blue") + Text(GAME_EXE_PATH, style="yellow"))
    console.print(Text("Target executable name: ", style="bright_blue") + Text(TARGET_EXE_NAME, style="yellow"))
    console.print(Text("Mods directory: ", style="bright_blue") + Text(MODS_DIR, style="yellow"))
    console.print(Text("Mods extension: ", style="bright_blue") + Text(MOD_EXTENSION, style="yellow"))
    console.print(Text("Restore original files when game is closed: ", style="bright_blue") + status_text(RESTORE_ORIGINAL_FILE_WHEN_CLOSED))
    console.print(Text("Hide console windows when running: ", style="bright_blue") + status_text(HIDE_CONSOLE_WHEN_RUNNING))

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
    console.rule(Text("Game status: ", style="bright_blue") + Text("Starting game...", style="bold green"), characters=" ")
    game.start()
    if not RESTORE_ORIGINAL_FILE_WHEN_CLOSED:
        console.print("Mods will not be restored when game is closed, program will exit...", style="bold yellow")
        input("Press Enter to exit...")
        return
    
    # wait for game to spawn process
    time.sleep(1)
    
    clear_line()
    console.rule(Text("Game status: ", style="bright_blue") + Text("Running", style="bold green"), characters=" ")
    console.rule(Text("Please do not close this window", style="bold yellow"), characters=" ")
    console.rule(Text("Waiting for the restore after the game is closed...", style="bold yellow"), characters=" ")
    console.print(full_width_line("─"))

    time.sleep(3)

    tray_icon = None
    if HIDE_CONSOLE_WHEN_RUNNING:
        tray_icon = minimize_to_tray()

    game.wait_for_game_closed()

    if HIDE_CONSOLE_WHEN_RUNNING:
        show_console()
        if tray_icon:
            try:
                tray_icon.stop()
            except Exception:
                pass

    clear_line(4)
    console.rule(Text("Game status: ", style="bright_blue") + Text("Game closed detected", style="bold red"), characters=" ")
    console.print(full_width_line("─"))
    
    time.sleep(1)
    
    clear_line()
    console.rule(Text("Restore Original Files", style="bold"), style="white")
    loader.restore_all()
    console.print("Mods restored successfully", style="bold green")
    console.print(full_width_line("─"))
    
    # Countdown with abort option
    aborted = False
    for i in range(5, 0, -1):
        console.print(f"Program will exit in {i} seconds, press any key to abort exit...", style="bold yellow")
        # Wait 1 second but check for keypress every 100ms
        for _ in range(10):
            time.sleep(0.1)
            if msvcrt.kbhit():
                msvcrt.getch()  # clear the key from buffer
                aborted = True
                break
        clear_line()
        if aborted:
            break
    
    if aborted:
        console.print("Exit aborted. Press Enter to close the program...", style="bold green")
        input()
    
    sys.exit(0)
if __name__ == "__main__":
    main()
