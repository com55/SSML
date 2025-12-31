"""Main application window."""
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSystemTrayIcon, QMenu, QMessageBox,
    QApplication
)
from PySide6.QtCore import QSize, Qt, QFileSystemWatcher, QTimer
from PySide6.QtGui import QCloseEvent, QIcon, QAction

from core import get_resource_path
from viewmodels import MainViewModel, ModData

from .helpers import get_app_icon_path
from .dialogs import SettingsDialog, ImagePreviewDialog
from .widgets import ModTreeWidget


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stella Sora Mod Launcher")
        self.setMinimumSize(600, 500)

        self.vm = MainViewModel()
        self.is_running = False
        
        # Connect signals
        self.vm.mods_list_changed.connect(self._update_mod_list)
        self.vm.log_message.connect(self._append_log)
        self.vm.game_status_changed.connect(self._on_game_status_changed)
        
        # First run check
        if not self.vm.config.GameExePath.get():
            self._open_settings()
            
        self._setup_ui()
        self._setup_tray()
        self._setup_file_watcher()

        # Initial load
        self.vm.load_mods()
        
        # Check if game is already running when starting the program
        self.vm.check_game_running()

    def _setup_ui(self):
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
        self.settings_btn.clicked.connect(self._open_settings)

        self.open_folder_btn = QPushButton("Open Mods Folder")
        self.open_folder_btn.setIcon(QIcon(get_resource_path("resources/folder_open.svg").as_posix()))
        self.open_folder_btn.setIconSize(QSize(18, 18))
        self.open_folder_btn.setObjectName("openFolderButton")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._open_mods_folder)
        
        top_layout.addWidget(self.settings_btn)
        top_layout.addWidget(self.open_folder_btn)
        top_layout.addStretch(1)
        top_layout.addWidget(self.launch_btn)
        layout.addLayout(top_layout)
        
        layout.addSpacing(5)

        # Mods header with master toggle
        mods_header_layout = QHBoxLayout()
        mods_label = QLabel("Mods:")
        mods_label.setObjectName("sectionLabel")
        mods_header_layout.addWidget(mods_label)
        mods_header_layout.addStretch(1)
        
        self.enable_all_btn = QPushButton("Enable All")
        self.enable_all_btn.setObjectName("folderEnableButton")
        self.enable_all_btn.setFixedSize(80, 24)
        self.enable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enable_all_btn.clicked.connect(lambda: self._on_master_toggle(True))
        
        self.disable_all_btn = QPushButton("Disable All")
        self.disable_all_btn.setObjectName("folderDisableButton")
        self.disable_all_btn.setFixedSize(80, 24)
        self.disable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disable_all_btn.clicked.connect(lambda: self._on_master_toggle(False))
        
        mods_header_layout.addWidget(self.enable_all_btn)
        mods_header_layout.addWidget(self.disable_all_btn)
        layout.addLayout(mods_header_layout)

        # Mod tree
        self.mod_tree_widget = ModTreeWidget(
            on_toggle=self._on_toggle_clicked,
            on_folder_toggle=self._on_folder_toggle_clicked,
            on_image_preview=self._open_image_preview
        )
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
        
    def _setup_file_watcher(self):
        """Setup file system watcher for auto-refresh."""
        self.file_watcher = QFileSystemWatcher()
        mods_dir = self.vm.config.ModsDir.get()
        
        if mods_dir:
            mods_path = Path(mods_dir)
            if mods_path.exists():
                self.file_watcher.addPath(str(mods_path))
                for subdir in mods_path.rglob("*"):
                    if subdir.is_dir():
                        self.file_watcher.addPath(str(subdir))
        
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._on_files_changed)
        
        self.file_watcher.directoryChanged.connect(self._schedule_refresh)
        self.file_watcher.fileChanged.connect(self._schedule_refresh)

    def _schedule_refresh(self, path: str):
        """Debounce refresh."""
        self.refresh_timer.start(500)

    def _on_files_changed(self):
        if not self.is_running:
            self._update_file_watcher()
            self.vm.load_mods()

    def _update_file_watcher(self):
        """Add newly created subdirectories."""
        mods_dir = self.vm.config.ModsDir.get()
        if not mods_dir:
            return
        
        mods_path = Path(mods_dir)
        if not mods_path.exists():
            return
        
        watched_dirs = set(self.file_watcher.directories())
        for subdir in mods_path.rglob("*"):
            if subdir.is_dir() and str(subdir) not in watched_dirs:
                self.file_watcher.addPath(str(subdir))

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            pixmap = QIcon.fromTheme("system-run").pixmap(64, 64)
            self.tray_icon.setIcon(QIcon(pixmap))

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        quit_action = QAction("Quit", self)
        app_instance = QApplication.instance()
        if app_instance:
            quit_action.triggered.connect(app_instance.quit)

        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        self.tray_icon.show()

    def closeEvent(self, event: QCloseEvent) -> None:
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

    def _show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                if self.isMinimized():
                    self._show_window()
                else:
                    self.hide()
            else:
                self._show_window()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.vm.reload_config()
            self.vm.load_mods()
            self._append_log("Settings saved.")

    def _open_mods_folder(self):
        mods_dir = self.vm.config.ModsDir.get()
        if mods_dir:
            mods_path = Path(mods_dir)
            if mods_path.exists():
                os.startfile(mods_path)
            else:
                self._append_log(f"Mods folder not found: {mods_dir}")
        else:
            self._append_log("Mods folder not configured.")

    def _update_mod_list(self, mods_data: list[ModData]) -> None:
        mods_dir = Path(self.vm.config.ModsDir.get() or "")
        self.mod_tree_widget.populate(mods_data, mods_dir)

    def _open_image_preview(self, folder_path: Path) -> None:
        dlg = ImagePreviewDialog(folder_path, self)
        dlg.exec()

    def _on_toggle_clicked(self, mod_path: Path, enable: bool) -> None:
        """Handle mod toggle with conflict detection."""
        if enable:
            conflicts = self.vm.check_duplicate_conflict(mod_path)
            if conflicts:
                conflict_names = [c["path"] for c in conflicts]
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Question)
                msg.setWindowTitle("Mod Conflict")
                msg.setText("Another mod with the same filename is already enabled:")
                msg.setInformativeText(f"{', '.join(conflict_names)}\n\nDisable it and enable this mod instead?")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.No)
                
                if msg.exec() == QMessageBox.StandardButton.Yes:
                    for conflict in conflicts:
                        self.vm.disable_conflicting_mod(conflict["path"])
                    self.vm.toggle_mod(mod_path, enable)
                return
        
        self.vm.toggle_mod(mod_path, enable)

    def _on_folder_toggle_clicked(self, folder_name: str, enable: bool, mods: list[ModData]) -> None:
        for mod in mods:
            if mod["enabled"] != enable:
                self._on_toggle_clicked(mod["path"], enable)

    def _on_master_toggle(self, enable: bool) -> None:
        self.vm.toggle_all_mods(enable)

    def _append_log(self, msg: str) -> None:
        self.log_text.append(msg)

    def _on_game_status_changed(self, is_running: bool) -> None:
        self.is_running = is_running
        self.launch_btn.setEnabled(not is_running)
        self.launch_btn.setText("Launch Game" if not is_running else "Game is running")
        self.settings_btn.setEnabled(not is_running)
        self.mod_tree_widget.setEnabled(not is_running)
        self.enable_all_btn.setEnabled(not is_running)
        self.disable_all_btn.setEnabled(not is_running)

        if is_running and self.vm.config.HideConsoleWhenRunning.get():
            self.hide()
            self.tray_icon.showMessage(
                "Stella Sora Mod Launcher", 
                "Game is running. Minimized to tray.", 
                QSystemTrayIcon.MessageIcon.Information, 
                3000
            )
        elif not is_running and self.vm.config.HideConsoleWhenRunning.get():
            self._show_window()
