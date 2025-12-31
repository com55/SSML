# Stella Sora Mod Launcher

A modern mod launcher for Stella Sora game with advanced mod management, automatic backup/restore, and intelligent conflict detection.

## Features

- **Modern GUI Interface** - Clean, dark-themed interface built with PySide6
- **Tree View with Nested Folders** - Organize mods in subfolders with hierarchical tree view
- **JSON-Based Status Tracking** - Mod enable/disable status stored in `ModsStatus.json` (no file renaming)
- **Automatic File Watching** - Auto-refreshes mod list when files are added/removed from Mods folder
- **Hash-Based Verification** - Verifies mod integrity using SHA256 hashes
- **Smart Conflict Detection** - Detects and warns about duplicate filename conflicts
- **Orphan Recovery** - Automatically restores game files when enabled mods are deleted/moved
- **Master Toggle** - Enable/Disable all mods with one click
- **Folder-Level Controls** - Enable/Disable all mods in a folder at once
- **Image Preview** - Preview images in mod folders with built-in image viewer (supports PNG, JPG, GIF, BMP, WebP)
- **Backup & Restore System** - Automatic backup of original game files with organized backup structure
- **System Tray Support** - Minimizes to system tray while game is running
- **Game Process Monitoring** - Monitors game process and handles cleanup automatically

## Usage

1. Run the mod launcher executable
2. On first run, select the `StellaSora.exe` game executable via the Settings dialog
3. Place your mod files (`.unity3d`) in the `Mods` folder:
   - Mods can be organized in subfolders (e.g., `Mods/CharacterName/mod.unity3d`)
   - The tree view will automatically reflect the folder structure
4. Use the tree view to Enable/Disable mods:
   - Click "Enabled"/"Disabled" button next to each mod
   - Use folder buttons to toggle all mods in a folder
   - Use "Enable All"/"Disable All" buttons at the top for master control
5. Click "Launch Game" to:
   - Sync and verify enabled mods
   - Apply enabled mods to the game directory
   - Launch the game
   - Monitor game process until it closes

## Configuration

Settings can be changed via the "Settings" button in the application.

- `Game Executable`: Path to game executable (e.g., `StellaSora.exe`)
- `Mods Directory`: Location of your mods folder (default: `Mods` folder next to executable)
- `Backups Directory`: Location where original game files are backed up (default: `Backups` folder)
- `Minimize to Tray`: Automatically minimize to system tray when game is running

## Mod Organization

Mods can be organized in nested folders within the Mods directory:

```
Mods/
├── char_2d_12301.unity3d          (root level mod)
├── CharacterName/
│   ├── char_2d_14401.unity3d
│   └── char_2d_14402.unity3d
└── AnotherFolder/
    └── SubFolder/
        └── mod.unity3d
```

The tree view will display this structure with folder icons and allow you to manage mods at any level.

### Image Preview

Folders containing image files (PNG, JPG, GIF, BMP, WebP) will show a 📷 photo button next to the Enable/Disable All button. Click it to open the image preview dialog where you can:

- View all images in the folder
- Navigate between images with Previous/Next buttons or **← / →** arrow keys
- Toggle fullscreen mode with the Fullscreen button or **F11** key
- Press **Escape** to exit fullscreen
- Images are automatically scaled to fit the window

## How It Works

1. **Status Management**: Mod enable/disable status is stored in `ModsStatus.json` (not file renaming)
2. **Hash Tracking**: Each mod file is tracked by SHA256 hash to detect changes
3. **Backup System**: Original game files are backed up to `Backups` directory with the same folder structure as Mods
4. **Conflict Detection**: When enabling a mod, the system checks for other enabled mods with the same filename
5. **Verification**: Before launching, the system verifies that all enabled mods are properly applied
6. **Orphan Recovery**: If an enabled mod is deleted, the system automatically restores the original game file

## Requirements

- Windows OS
- Python 3.11+ (if running from source)
- Dependencies:
  - `psutil>=7.1.3` - Process monitoring
  - `PySide6>=6.10.1` - GUI framework
  - `qt-material-icons>=0.4.1` - Material design icons
  - `pystray>=0.19.5` - System tray support (optional)
  - `Pillow>=10.0.0` - Image processing for tray icon

## Running from Source

```bash
uv sync
uv run python main.py
```

## Project Structure

```
SSML-GUI/
├── main.py                     # Application entry point
├── core.py                     # Core mod loader logic, configuration, game management
├── style.qss                   # Qt stylesheet for dark theme
│
├── ui/                         # UI Layer
│   ├── main_window.py          # Main application window
│   ├── helpers.py              # UI utilities (stylesheet, folder tree, etc.)
│   ├── dialogs/
│   │   ├── settings_dialog.py  # Settings configuration dialog
│   │   └── image_preview_dialog.py  # Image preview dialog
│   └── widgets/
│       └── mod_tree_widget.py  # Mod list tree widget
│
├── viewmodels/                 # ViewModel Layer (MVVM)
│   ├── base.py                 # Shared types (ModData)
│   ├── main_viewmodel.py       # Main window ViewModel
│   ├── settings_viewmodel.py   # Settings dialog ViewModel
│   └── workers.py              # Background workers (GameLauncher)
│
├── config.ini                  # Configuration file (auto-generated)
└── ModsStatus.json             # Mod status tracking (auto-generated)
```
