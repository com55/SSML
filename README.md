# StellaSora Mod Loader

A simple mod loader for StellaSora game that automatically installs mods and restores original files when the game closes.

## Features

- **Auto Mod Installation** - Automatically finds and installs mods from the `Mods` folder
- **Backup & Restore** - Backs up original game files before applying mods and restores them when the game closes
- **System Tray Support** - Minimizes to system tray while waiting for game to close
- **Configuration Wizard** - First-run wizard to set up game path and preferences
- **Subfolder Support** - Organize mods in subfolders
- **Disabled Mods** - Skip to install mods when file name starts with `disabled` or placed in folder starting with `disabled` (e.g., `DISABLEDmod.unity3d` or `DISABLED_folder_name/mod.unity3d`)

## Usage

1. Run the mod loader executable
2. On first run, select the `StellaSora.exe` game executable when prompted
3. Place your mod files (`.unity3d`) in the `Mods` folder
4. The loader will automatically:
   - Install mods to the game directory
   - Launch the game
   - Restore original files when the game closes if enabled

## Configuration

Settings are stored in `config.ini`:

| Option | Description |
|--------|-------------|
| `game_exe_path` | Path to game executable |
| `mods_dir` | Mods folder location |
| `target_exe_name` | Game executable name (default: `StellaSora.exe`) |
| `mod_extension` | Mod file extension (default: `.unity3d`) |
| `restore_original_file_when_game_closed` | Auto-restore files on game close |
| `hide_console_when_running` | Minimize to tray while game runs |

Delete `config.ini` to restart the configuration wizard.

## Disabling Mods

To temporarily disable mods without removing them, place them in a folder starting with `disabled` (e.g., `Mods/disabled_old/`).

## Requirements

- Windows OS
- Python 3.11+ (if running from source)
- uv (for package management)

## Dependencies

- psutil
- rich
- pystray
- Pillow

