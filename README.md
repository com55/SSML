# StellaSora Mod Loader

A simple mod loader for StellaSora game that automatically installs mods and restores original files when the game closes.

## Features

- **Auto Mod Installation** - Automatically finds and installs mods from the `Mods` folder
- **Backup & Restore** - Backs up original game files before applying mods and restores them when the game closes
- **GUI Interface** - Easy to use interface with dark theme
- **Mod Management** - Enable/Disable mods directly from the list
- **System Tray Support** - Minimizes to system tray while waiting for game to close
- **Configuration Dialog** - Easy setup for game path and preferences

## Usage

1. Run the mod loader executable
2. On first run, select the `StellaSora.exe` game executable via the Settings dialog (if not auto-detected or if you are prompted)
3. Place your mod files (`.unity3d`) in the `Mods` folder (or select your custom Mods folder in Settings)
4. Use the list to Enable/Disable mods
5. Click "Launch Game" to:
   - Install enabled mods to the game directory
   - Launch the game
   - Restore original files when the game closes (if enabled)

## Configuration

Settings can be changed via the "Settings" button in the application.

- `Game Executable`: Path to game executable
- `Mods Directory`: Mods folder location
- `Mod Extension`: Mod file extension (default: `.unity3d`)
- `Restore original files`: Check to auto-restore files on game close
- `Minimize to Tray`: Check to minimize to tray while game runs

## Requirements

- Windows OS
- Python 3.11+ (if running from source)
- Dependencies: `psutil`, `PySide6`, `pystray`, `Pillow`

## Running from Source

```bash
uv sync
uv run python main.py
```
