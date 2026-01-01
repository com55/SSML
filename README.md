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
- **Auto-Update** - Automatically checks for updates from GitHub releases
- **Quick Launch Mode** - Launch game directly with `--quicklaunch` flag (skips UI)
- **Desktop Shortcuts** - Create normal or quick launch shortcuts from Settings
- **Single Instance Lock** - Prevents multiple instances from running
- **Comprehensive Logging** - Logs to `LatestLog.txt` for debugging

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

### Quick Launch Mode

Run from command line with `--quicklaunch` flag to skip the UI and launch the game directly:

```bash
StellaSoraModLauncher.exe --quicklaunch
```

You can also create a Quick Launch shortcut from Settings > "Create Quick Launch Shortcut".

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
7. **Deferred Save**: Status changes are batched and saved once per action for optimal I/O performance

## Requirements

- Windows OS
- Python 3.11+ (if running from source)
- Dependencies:
  - `psutil>=7.1.3` - Process monitoring
  - `PySide6>=6.10.1` - GUI framework
  - `requests>=2.32.3` - HTTP client for auto-update
  - `packaging>=24.2` - Version comparison

## Running from Source using [uv](https://github.com/astral-sh/uv#installation)

```bash
uv sync
uv run python main.py
```

## Project Structure

<details>
<summary>Click to see detail</summary>

```
SSML-GUI/
├── main.py                     # Application entry point with logging setup
├── core.py                     # Core mod loader logic, configuration, game management
├── launcher.py                 # Quick launch functionality
├── updater.py                  # Auto-update from GitHub releases
├── instance_lock.py            # Single instance lock
├── shortcut.py                 # Desktop shortcut creation
├── utils.py                    # Utility functions
├── styles.qss                   # Qt stylesheet for dark theme
│
├── ui/                         # UI Layer
│   ├── main_window.py          # Main application window
│   ├── helpers.py              # UI utilities (stylesheet, folder tree, etc.)
│   ├── dialogs/
│   │   ├── settings_dialog.py  # Settings configuration dialog
│   │   ├── image_preview_dialog.py  # Image preview dialog
│   │   └── update_dialog.py    # Update available dialog
│   └── widgets/
│       └── mod_tree_widget.py  # Mod list tree widget
│
├── viewmodels/                 # ViewModel Layer (MVVM)
│   ├── base.py                 # Shared types (ModData)
│   ├── main_viewmodel.py       # Main window ViewModel
│   ├── settings_viewmodel.py   # Settings dialog ViewModel
│   └── workers.py              # Background workers (GameLauncher, GameMonitor)
│
├── resources/                  # Icons and assets
│
├── config.ini                  # Configuration file (auto-generated)
├── ModsStatus.json             # Mod status tracking (auto-generated)
└── LatestLog.txt               # Application log (auto-generated)
```

</details>

## Contributing

- Found a bug or have a suggestion? Please [open an issue](https://github.com/com55/SSML/issues)
- Pull requests are welcome!

## License

This project is licensed under the [GPL v3.0](LICENSE) License.
