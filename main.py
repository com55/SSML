import sys
from pathlib import Path
from typing import Any
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
                               QTextEdit, QLabel, QFileDialog, QCheckBox, QDialog,
                               QFormLayout, QLineEdit, QSystemTrayIcon, QMenu)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QAction
from qt_material_icons import MaterialIcon

from viewmodel import MainViewModel, SettingsViewModel, ModData
from core import get_resource_path

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

        self.mod_ext_edit = QLineEdit(self.vm.get_mod_ext())

        self.restore_chk = QCheckBox("Restore original files when game closed")
        self.restore_chk.setChecked(self.vm.get_restore())

        self.hide_console_chk = QCheckBox("Minimize to Tray when running")
        self.hide_console_chk.setChecked(self.vm.get_hide_console())

        form.addRow("Game Executable:", game_path_layout)
        form.addRow("Mods Directory:", mods_dir_layout)
        form.addRow("Mod Extension:", self.mod_ext_edit)
        form.addRow("", self.restore_chk)
        form.addRow("", self.hide_console_chk)

        layout.addLayout(form)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

    def browse_game_path(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Game Executable", "", "Executable (*.exe)")
        if f:
            self.game_path_edit.setText(f)
            
    def browse_mods_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Mods Directory")
        if d:
            self.mods_dir_edit.setText(d)

    def save_settings(self):
        self.vm.set_game_path(self.game_path_edit.text())
        self.vm.set_mods_dir(self.mods_dir_edit.text())
        self.vm.set_mod_ext(self.mod_ext_edit.text())
        self.vm.set_restore(self.restore_chk.isChecked())
        self.vm.set_hide_console(self.hide_console_chk.isChecked())
        self.accept()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StellaSora Mod Launcher")
        self.setMinimumSize(600, 500)

        self.vm = MainViewModel()
        self.is_running = False
        
        # Connect Signals
        self.vm.mods_list_changed.connect(self.update_mod_list)
        self.vm.log_message.connect(self.append_log)
        self.vm.game_status_changed.connect(self.on_game_status_changed)

        self.setup_ui()
        self.setup_tray()

        # Initial Load
        self.vm.load_mods()

        # Check if first run
        if not self.vm.config.GameExePath.get():
             self.open_settings()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top buttons
        top_layout = QHBoxLayout()
        
        self.launch_btn = QPushButton("Launch Game")
        self.launch_btn.setIcon(MaterialIcon('play_arrow', fill=True))
        self.launch_btn.setIconSize(QSize(30, 30))
        self.launch_btn.setObjectName("launchButton")
        self.launch_btn.clicked.connect(self.vm.launch_game)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(MaterialIcon('settings'))
        self.settings_btn.setIconSize(QSize(30, 30))
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.clicked.connect(self.open_settings)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(MaterialIcon('refresh'))
        self.refresh_btn.setIconSize(QSize(30, 30))
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.clicked.connect(self.vm.load_mods)
        
        top_layout.addWidget(self.settings_btn)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addStretch(1)
        top_layout.addWidget(self.launch_btn)
        layout.addLayout(top_layout)

        # Mod List
        mods_label = QLabel("Mods:")
        mods_label.setObjectName("sectionLabel")
        layout.addWidget(mods_label)
        self.mod_list_widget = QListWidget()
        self.mod_list_widget.setObjectName("modListWidget")
        self.mod_list_widget.itemChanged.connect(self.on_mod_item_changed)
        layout.addWidget(self.mod_list_widget)
        
        # Log
        log_label = QLabel("Log:")
        log_label.setObjectName("sectionLabel")
        layout.addWidget(log_label)
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logTextEdit")
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(150)
        layout.addWidget(self.log_text)
        
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
                "StellaSora Mod Loader", 
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

    def update_mod_list(self, mods_data: list[ModData]) -> None:
        self.mod_list_widget.blockSignals(True)
        self.mod_list_widget.clear()

        for mod in mods_data:
            item = QListWidgetItem(mod["name"])
            item.setData(Qt.ItemDataRole.UserRole, mod["path"])
            item.setCheckState(Qt.CheckState.Checked if mod["enabled"] else Qt.CheckState.Unchecked)
            self.mod_list_widget.addItem(item)

        self.mod_list_widget.blockSignals(False)

    def on_mod_item_changed(self, item: QListWidgetItem) -> None:
        mod_path: Any = item.data(Qt.ItemDataRole.UserRole)
        checked = item.checkState() == Qt.CheckState.Checked
        # Delegate to ViewModel
        self.vm.toggle_mod(mod_path, checked)

    def append_log(self, msg: str) -> None:
        self.log_text.append(msg)

    def on_game_status_changed(self, is_running: bool) -> None:
        self.is_running = is_running
        self.launch_btn.setEnabled(not is_running)
        self.launch_btn.setText("Launch Game" if not is_running else "Game is running")
        self.refresh_btn.setEnabled(not is_running)
        self.settings_btn.setEnabled(not is_running)
        self.mod_list_widget.setEnabled(not is_running)

        if is_running and self.vm.config.HideConsoleWhenRunning.get():
             self.hide()
             self.tray_icon.showMessage("StellaSora Mod Loader", "Game is running. Minimized to tray.", QSystemTrayIcon.MessageIcon.Information, 3000)
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
