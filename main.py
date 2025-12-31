import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QLabel, QFileDialog, QCheckBox, QDialog,
                               QFormLayout, QLineEdit, QSystemTrayIcon, QMenu, QHeaderView,
                               QMessageBox, QScrollArea)
from PySide6.QtCore import QSize, Qt, QFileSystemWatcher, QTimer
from PySide6.QtGui import QCloseEvent, QIcon, QAction, QBrush, QColor, QFont, QPixmap

from viewmodel import MainViewModel, SettingsViewModel, ModData
from core import get_resource_path
from typing import Any

# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

# Type alias for nested folder structure
# Each folder node is a dict with "_mods" key for files in that folder
# and other keys for subfolders
FolderNode = dict[str, Any]  # {"_mods": list[ModData], "subfolder_name": FolderNode, ...}


def build_folder_tree(mods_data: list[ModData]) -> tuple[list[ModData], FolderNode]:
    """Build nested folder structure from flat mod list.
    
    Returns:
        Tuple of (root_mods, folder_tree) where:
        - root_mods: list of mods at root level
        - folder_tree: nested dict structure for subfolders
    """
    root_mods: list[ModData] = []
    tree: FolderNode = {}
    
    for mod in mods_data:
        parts = mod["relative_path"].split("/")
        if len(parts) == 1:
            # Root level mod (no subfolder)
            root_mods.append(mod)
        else:
            # Mod in subfolder - navigate/create path in tree
            current = tree
            for folder in parts[:-1]:  # All folders except filename
                if folder not in current:
                    current[folder] = {"_mods": []}
                current = current[folder]
            # Ensure _mods key exists
            if "_mods" not in current:
                current["_mods"] = []
            current["_mods"].append(mod)
    
    return root_mods, tree


def collect_all_mods_from_folder(folder_node: FolderNode) -> list[ModData]:
    """Recursively collect all mods from a folder and its subfolders."""
    mods: list[ModData] = []
    
    # Add mods directly in this folder
    if "_mods" in folder_node:
        mods.extend(folder_node["_mods"])
    
    # Recursively add mods from subfolders
    for key, value in folder_node.items():
        if key != "_mods" and isinstance(value, dict):
            mods.extend(collect_all_mods_from_folder(value))
    
    return mods


def load_stylesheet() -> str:
    """Load the QSS stylesheet from embedded resource."""
    style_path = get_resource_path("style.qss")
    if style_path.exists():
        return style_path.read_text(encoding="utf-8")
    return ""

def get_app_icon_path() -> Path:
    """Get the path to the application icon from embedded resource."""
    return get_resource_path("icon.ico")

# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(500, 300)
        self.vm = SettingsViewModel()
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.game_path_edit = QLineEdit(self.vm.get_game_path())
        self.game_path_edit.setCursorPosition(0)
        game_path_btn = QPushButton("Browse")
        game_path_btn.setObjectName("browseButton")
        game_path_btn.clicked.connect(self.browse_game_path)
        game_path_layout = QHBoxLayout()
        game_path_layout.addWidget(self.game_path_edit)
        game_path_layout.addWidget(game_path_btn)
        
        self.mods_dir_edit = QLineEdit(self.vm.get_mods_dir())
        self.mods_dir_edit.setCursorPosition(0)
        mods_dir_btn = QPushButton("Browse")
        mods_dir_btn.setObjectName("browseButton")
        mods_dir_btn.clicked.connect(self.browse_mods_dir)
        mods_dir_layout = QHBoxLayout()
        mods_dir_layout.addWidget(self.mods_dir_edit)
        mods_dir_layout.addWidget(mods_dir_btn)

        self.backups_dir_edit = QLineEdit(self.vm.get_backups_dir())
        self.backups_dir_edit.setCursorPosition(0)
        backups_dir_btn = QPushButton("Browse")
        backups_dir_btn.setObjectName("browseButton")
        backups_dir_btn.clicked.connect(self.browse_backups_dir)
        backups_dir_layout = QHBoxLayout()
        backups_dir_layout.addWidget(self.backups_dir_edit)
        backups_dir_layout.addWidget(backups_dir_btn)

        self.mod_ext_edit = QLineEdit(self.vm.get_mod_ext())

        self.hide_console_chk = QCheckBox("Minimize to Tray when running")
        self.hide_console_chk.setChecked(self.vm.get_hide_console())

        form.addRow("Game Executable:", game_path_layout)
        form.addRow("Mods Directory:", mods_dir_layout)
        form.addRow("Backups Directory:", backups_dir_layout)
        form.addRow("Mod Extension:", self.mod_ext_edit)
        form.addRow("", self.hide_console_chk)

        layout.addLayout(form)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

    def browse_game_path(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Game Executable", "", "StellaSora (StellaSora.exe)")
        if f:
            if not f.endswith("StellaSora.exe"):
                QMessageBox.warning(self, "Invalid File", "Selected file is not StellaSora.exe")
                return
            self.game_path_edit.setText(f)
            
    def browse_mods_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Mods Directory")
        if d:
            self.mods_dir_edit.setText(d)

    def browse_backups_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Backups Directory")
        if d:
            self.backups_dir_edit.setText(d)

    def save_settings(self):
        self.vm.set_game_path(self.game_path_edit.text())
        self.vm.set_mods_dir(self.mods_dir_edit.text())
        self.vm.set_backups_dir(self.backups_dir_edit.text())
        self.vm.set_mod_ext(self.mod_ext_edit.text())
        self.vm.set_hide_console(self.hide_console_chk.isChecked())
        self.accept()


# --- Image Preview Dialog ---
class ImagePreviewDialog(QDialog):
    """Dialog to preview images in a folder."""
    
    def __init__(self, folder_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.folder_path = folder_path
        self.image_files: list[Path] = []
        self.current_index = 0
        self.is_fullscreen = False
        
        # Find all image files in the folder
        self._load_images()
        
        self.setWindowTitle(f"Images in {folder_path.name}")
        self.setMinimumSize(600, 500)
        self.resize(800, 600)
        
        self._setup_ui()
        self._update_display()
    
    def _load_images(self) -> None:
        """Load all image files from the folder."""
        if self.folder_path.exists() and self.folder_path.is_dir():
            for file in sorted(self.folder_path.iterdir()):
                if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                    self.image_files.append(file)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Top bar with fullscreen button
        top_layout = QHBoxLayout()
        top_layout.addStretch(1)
        
        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        self.fullscreen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fullscreen_btn.setToolTip("Toggle fullscreen (F11)")
        self.fullscreen_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Prevent stealing focus
        top_layout.addWidget(self.fullscreen_btn)
        
        layout.addLayout(top_layout)
        
        # Image display area with scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #1a1a2e;")
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Prevent stealing focus
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("padding: 10px;")
        self.scroll_area.setWidget(self.image_label)
        
        layout.addWidget(self.scroll_area, 1)
        
        # Info and navigation
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self._prev_image)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Prevent stealing focus
        
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Prevent stealing focus
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.info_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
    
    def _update_display(self) -> None:
        """Update the displayed image and navigation state."""
        if not self.image_files:
            self.image_label.setText("No images found in this folder.")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.info_label.setText("0 / 0")
            return
        
        # Load and display current image
        current_file = self.image_files[self.current_index]
        pixmap = QPixmap(str(current_file))
        
        if pixmap.isNull():
            self.image_label.setText(f"Failed to load: {current_file.name}")
        else:
            # Scale image to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                self.scroll_area.width() - 30,
                self.scroll_area.height() - 30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        
        # Update info and navigation
        self.info_label.setText(f"{current_file.name}  ({self.current_index + 1} / {len(self.image_files)})")
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)
    
    def _prev_image(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._update_display()
    
    def _next_image(self) -> None:
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._update_display()
    
    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.is_fullscreen:
            self.showNormal()
            self.fullscreen_btn.setText("⛶ Fullscreen")
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("⛶ Exit Fullscreen")
            self.is_fullscreen = True
    
    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Left:
            self._prev_image()
        elif event.key() == Qt.Key.Key_Right:
            self._next_image()
        else:
            super().keyPressEvent(event)
    
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-scale image on resize
        if self.image_files:
            self._update_display()


def folder_has_images(folder_path: Path) -> bool:
    """Check if a folder contains any image files."""
    if not folder_path.exists() or not folder_path.is_dir():
        return False
    for file in folder_path.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
            return True
    return False

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stella Sora Mod Launcher")
        self.setMinimumSize(600, 500)

        self.vm = MainViewModel()
        self.is_running = False
        
        # Connect Signals
        self.vm.mods_list_changed.connect(self.update_mod_list)
        self.vm.log_message.connect(self.append_log)
        self.vm.game_status_changed.connect(self.on_game_status_changed)
        
        # Check if first run
        if not self.vm.config.GameExePath.get():
            self.open_settings()
            
        self.setup_ui()
        self.setup_tray()
        self.setup_file_watcher()

        # Initial Load
        self.vm.load_mods()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top buttons
        top_layout = QHBoxLayout()
        
        self.launch_btn = QPushButton("Launch Game")
        self.launch_btn.setIcon(QIcon(get_resource_path("resources/play_arrow.svg").as_posix()))
        self.launch_btn.setIconSize(QSize(20, 20))
        self.launch_btn.setObjectName("launchButton")
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.clicked.connect(self.vm.launch_game)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(QIcon(get_resource_path("resources/settings.svg").as_posix()))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        self.open_folder_btn = QPushButton("Open Mods Folder")
        self.open_folder_btn.setIcon(QIcon(get_resource_path("resources/folder_open.svg").as_posix()))
        self.open_folder_btn.setIconSize(QSize(18, 18))
        self.open_folder_btn.setObjectName("openFolderButton")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self.open_mods_folder)
        
        top_layout.addWidget(self.settings_btn)
        top_layout.addWidget(self.open_folder_btn)
        top_layout.addStretch(1)
        top_layout.addWidget(self.launch_btn)
        layout.addLayout(top_layout)
        
        layout.addSpacing(5)

        # Mod List Header with master toggle buttons
        mods_header_layout = QHBoxLayout()
        mods_label = QLabel("Mods:")
        mods_label.setObjectName("sectionLabel")
        mods_header_layout.addWidget(mods_label)
        mods_header_layout.addStretch(1)
        
        self.enable_all_btn = QPushButton("Enable All")
        self.enable_all_btn.setObjectName("folderEnableButton")
        self.enable_all_btn.setFixedSize(80, 24)
        self.enable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enable_all_btn.clicked.connect(lambda: self.on_master_toggle(True))
        
        self.disable_all_btn = QPushButton("Disable All")
        self.disable_all_btn.setObjectName("folderDisableButton")
        self.disable_all_btn.setFixedSize(80, 24)
        self.disable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disable_all_btn.clicked.connect(lambda: self.on_master_toggle(False))
        
        mods_header_layout.addWidget(self.enable_all_btn)
        mods_header_layout.addWidget(self.disable_all_btn)
        layout.addLayout(mods_header_layout)
        self.mod_tree_widget = QTreeWidget()
        self.mod_tree_widget.setObjectName("modTreeWidget")
        self.mod_tree_widget.setColumnCount(2)
        self.mod_tree_widget.setHeaderHidden(True)
        self.mod_tree_widget.setAutoScroll(False)  # Disable auto-scroll on mouse near edge
        self.mod_tree_widget.setMouseTracking(False)  # Disable mouse tracking
        self.mod_tree_widget.setIndentation(20)  # Indent for tree structure
        self.mod_tree_widget.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)  # Disable selection highlight
        self.mod_tree_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Disable focus rectangle
        self.mod_tree_widget.header().setStretchLastSection(False)
        self.mod_tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mod_tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.mod_tree_widget.header().resizeSection(1, 120)  # Fixed width for button column
        layout.addWidget(self.mod_tree_widget)
        
        # Log
        log_label = QLabel("Console Log:")
        log_label.setObjectName("sectionLabel")
        layout.addWidget(log_label)
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logTextEdit")
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(150)
        layout.addWidget(self.log_text)
        
    def setup_file_watcher(self):
        """Setup file system watcher to auto-refresh when Mods folder changes."""
        self.file_watcher = QFileSystemWatcher()
        mods_dir = self.vm.config.ModsDir.get()
        
        if mods_dir:
            mods_path = Path(mods_dir)
            if mods_path.exists():
                # Watch the mods directory
                self.file_watcher.addPath(str(mods_path))
                # Watch subdirectories
                for subdir in mods_path.rglob("*"):
                    if subdir.is_dir():
                        self.file_watcher.addPath(str(subdir))
        
        # Debounce timer to prevent rapid refreshes
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.on_files_changed)
        
        self.file_watcher.directoryChanged.connect(self.schedule_refresh)
        self.file_watcher.fileChanged.connect(self.schedule_refresh)

    def schedule_refresh(self, path: str):
        """Schedule a refresh with debounce to avoid rapid updates."""
        # Restart timer on each change (debounce 500ms)
        self.refresh_timer.start(500)

    def on_files_changed(self):
        """Called when files change after debounce period."""
        if not self.is_running:  # Don't refresh while game is running
            # Update file watcher to include newly created subdirectories
            self._update_file_watcher()
            self.vm.load_mods()

    def _update_file_watcher(self):
        """Update file watcher to include any newly created subdirectories."""
        mods_dir = self.vm.config.ModsDir.get()
        if not mods_dir:
            return
        
        mods_path = Path(mods_dir)
        if not mods_path.exists():
            return
        
        # Get currently watched directories
        watched_dirs = set(self.file_watcher.directories())
        
        # Find all subdirectories (including newly created ones)
        for subdir in mods_path.rglob("*"):
            if subdir.is_dir():
                subdir_str = str(subdir)
                if subdir_str not in watched_dirs:
                    # New subdirectory found - add to watcher
                    self.file_watcher.addPath(subdir_str)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            pixmap = QIcon.fromTheme("system-run").pixmap(64, 64)
            self.tray_icon.setIcon(QIcon(pixmap))

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("Quit", self)
        app_instance = QApplication.instance()
        if app_instance:
            quit_action.triggered.connect(app_instance.quit)

        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        self.tray_icon.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        # ซ่อนไปที่ tray แทนที่จะปิด
        event.ignore()
        if self.is_running:
            self.hide()
            self.tray_icon.showMessage(
                "Stella Sora Mod Launcher", 
                "Game is running. Minimized to tray.", 
                QSystemTrayIcon.MessageIcon.Information, 
                2000
            )
        else:
            app_instance = QApplication.instance()
            if app_instance:
                app_instance.quit()
            else:
                sys.exit(0)

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                if self.isMinimized():
                     self.show_window()
                else:
                     self.hide()
            else:
                self.show_window()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.vm.reload_config()
            self.vm.load_mods()
            self.append_log("Settings saved.")

    def open_mods_folder(self):
        """Open the Mods folder in file explorer."""
        mods_dir = self.vm.config.ModsDir.get()
        if mods_dir:
            mods_path = Path(mods_dir)
            if mods_path.exists():
                os.startfile(mods_path)
            else:
                self.append_log(f"Mods folder not found: {mods_dir}")
        else:
            self.append_log("Mods folder not configured.")

    def update_mod_list(self, mods_data: list[ModData]) -> None:
        self.mod_tree_widget.clear()
        
        # Build nested folder structure
        root_mods, folder_tree = build_folder_tree(mods_data)
        
        # Style settings for folders
        folder_text_color = QBrush(QColor("#6CB4EE"))  # Light blue for folder names
        folder_font = QFont()
        folder_font.setBold(True)
        folder_icon = QIcon(get_resource_path("resources/folder.svg").as_posix())
        
        # Get mods directory path for constructing folder paths
        mods_dir = Path(self.vm.config.ModsDir.get() or "")
        
        # Create folder items recursively
        for folder_name in sorted(k for k in folder_tree.keys() if k != "_mods"):
            folder_path = mods_dir / folder_name
            self._populate_folder_item(
                self.mod_tree_widget,
                folder_name,
                folder_tree[folder_name],
                folder_text_color,
                folder_font,
                folder_icon,
                folder_path
            )
        
        # Create root level mod items
        for mod in root_mods:
            mod_item = QTreeWidgetItem(self.mod_tree_widget)
            mod_item.setText(0, mod["name"])
            mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
            
            # Add toggle button
            btn = self.create_status_button(mod["path"], mod["enabled"])
            self.mod_tree_widget.setItemWidget(mod_item, 1, btn)

    def _populate_folder_item(
        self,
        parent: QTreeWidget | QTreeWidgetItem,
        folder_name: str,
        folder_node: FolderNode,
        folder_text_color: QBrush,
        folder_font: QFont,
        folder_icon: QIcon,
        folder_path: Path
    ) -> None:
        """Recursively create tree items for folders and their contents."""
        # Create folder item
        if isinstance(parent, QTreeWidget):
            folder_item = QTreeWidgetItem(parent)
        else:
            folder_item = QTreeWidgetItem(parent)
        
        folder_item.setText(0, folder_name)
        folder_item.setIcon(0, folder_icon)
        folder_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "name": folder_name, "path": folder_path})
        folder_item.setForeground(0, folder_text_color)
        folder_item.setFont(0, folder_font)
        
        # Collect all mods in this folder and subfolders for toggle button
        all_mods_in_folder = collect_all_mods_from_folder(folder_node)
        all_enabled = all(m["enabled"] for m in all_mods_in_folder) if all_mods_in_folder else False
        
        # Check if folder has images
        has_images = folder_has_images(folder_path)
        
        # Add folder buttons (photo preview if has images + toggle button)
        folder_btn = self.create_folder_buttons_widget(folder_name, all_enabled, all_mods_in_folder, folder_path, has_images)
        self.mod_tree_widget.setItemWidget(folder_item, 1, folder_btn)
        
        # Recursively add subfolders first (sorted)
        subfolder_names = sorted(k for k in folder_node.keys() if k != "_mods")
        for subfolder_name in subfolder_names:
            subfolder_path = folder_path / subfolder_name
            self._populate_folder_item(
                folder_item,
                subfolder_name,
                folder_node[subfolder_name],
                folder_text_color,
                folder_font,
                folder_icon,
                subfolder_path
            )
        
        # Add mod files in this folder
        if "_mods" in folder_node:
            for mod in folder_node["_mods"]:
                mod_item = QTreeWidgetItem(folder_item)
                mod_item.setText(0, mod["name"])
                mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
                
                # Add toggle button
                btn = self.create_status_button(mod["path"], mod["enabled"])
                self.mod_tree_widget.setItemWidget(mod_item, 1, btn)
        
        # Expand folder by default
        folder_item.setExpanded(True)

    def create_button_container(self, btn: QPushButton) -> QWidget:
        """Wrap button in a container widget aligned to the right."""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)  # Right padding
        layout.setSpacing(0)
        layout.addStretch()  # Push button to right
        layout.addWidget(btn)
        return container

    def create_status_button(self, mod_path: Path, enabled: bool) -> QWidget:
        """Create a status button for a mod file."""
        btn = QPushButton("Enabled" if enabled else "Disabled")
        btn.setObjectName("enabledButton" if enabled else "disabledButton")
        btn.setFixedSize(65, 22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.on_toggle_clicked(mod_path, not enabled))
        return self.create_button_container(btn)

    def create_folder_button(self, folder_name: str, all_enabled: bool, mods: list[ModData]) -> QPushButton:
        """Create a toggle all button for a folder."""
        btn = QPushButton("Disable All" if all_enabled else "Enable All")
        btn.setObjectName("folderDisableButton" if all_enabled else "folderEnableButton")
        btn.setFixedSize(80, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.on_folder_toggle_clicked(folder_name, not all_enabled, mods))
        return btn
    
    def create_photo_button(self, folder_path: Path) -> QPushButton:
        """Create a photo preview button for a folder."""
        btn = QPushButton()
        btn.setIcon(QIcon(get_resource_path("resources/photo_library.svg").as_posix()))
        btn.setIconSize(QSize(18, 18))
        btn.setObjectName("photoButton")
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Preview images")
        btn.clicked.connect(lambda: self.open_image_preview(folder_path))
        return btn
    
    def create_folder_buttons_widget(self, folder_name: str, all_enabled: bool, mods: list[ModData], folder_path: Path, has_images: bool) -> QWidget:
        """Create a container with optional photo button and toggle button for a folder."""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(4)
        layout.addStretch()
        
        # Add photo button if folder has images
        if has_images:
            photo_btn = self.create_photo_button(folder_path)
            layout.addWidget(photo_btn)
        
        # Add toggle button
        toggle_btn = self.create_folder_button(folder_name, all_enabled, mods)
        layout.addWidget(toggle_btn)
        
        return container
    
    def open_image_preview(self, folder_path: Path) -> None:
        """Open the image preview dialog for a folder."""
        dlg = ImagePreviewDialog(folder_path, self)
        dlg.exec()

    def on_toggle_clicked(self, mod_path: Path, enable: bool) -> None:
        """Handle single mod toggle with conflict detection."""
        if enable:
            # Check for duplicate filename conflicts
            conflicts = self.vm.check_duplicate_conflict(mod_path)
            if conflicts:
                # Show confirmation dialog
                conflict_names = [c["path"] for c in conflicts]
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Question)
                msg.setWindowTitle("Mod Conflict")
                msg.setText(f"Another mod with the same filename is already enabled:")
                msg.setInformativeText(f"{', '.join(conflict_names)}\n\nDisable it and enable this mod instead?")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.No)
                
                if msg.exec() == QMessageBox.StandardButton.Yes:
                    # Disable conflicting mods first
                    for conflict in conflicts:
                        self.vm.disable_conflicting_mod(conflict["path"])
                    # Then enable this mod
                    self.vm.toggle_mod(mod_path, enable)
                # If No, do nothing
                return
        
        self.vm.toggle_mod(mod_path, enable)

    def on_folder_toggle_clicked(self, folder_name: str, enable: bool, mods: list[ModData]) -> None:
        """Handle folder toggle - toggle all mods in folder."""
        for mod in mods:
            if mod["enabled"] != enable:
                # Use on_toggle_clicked to handle conflict detection
                self.on_toggle_clicked(mod["path"], enable)

    def on_master_toggle(self, enable: bool) -> None:
        """Handle master enable/disable all mods."""
        self.vm.toggle_all_mods(enable)

    def append_log(self, msg: str) -> None:
        self.log_text.append(msg)

    def on_game_status_changed(self, is_running: bool) -> None:
        self.is_running = is_running
        self.launch_btn.setEnabled(not is_running)
        self.launch_btn.setText("Launch Game" if not is_running else "Game is running")
        self.settings_btn.setEnabled(not is_running)
        self.mod_tree_widget.setEnabled(not is_running)

        if is_running and self.vm.config.HideConsoleWhenRunning.get():
             self.hide()
             self.tray_icon.showMessage("Stella Sora Mod Launcher", "Game is running. Minimized to tray.", QSystemTrayIcon.MessageIcon.Information, 3000)
        elif not is_running and self.vm.config.HideConsoleWhenRunning.get():
             self.show_window()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Apply Fusion style and load QSS stylesheet
    app.setStyle("Fusion")
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())