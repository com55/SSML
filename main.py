import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
                               QTextEdit, QLabel, QFileDialog, QCheckBox, QDialog,
                               QFormLayout, QLineEdit, QSystemTrayIcon, QMenu, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction

from viewmodel import MainViewModel, SettingsViewModel

# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 300)
        self.vm = SettingsViewModel()
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.game_path_edit = QLineEdit(self.vm.get_game_path())
        game_path_btn = QPushButton("Browse")
        game_path_btn.clicked.connect(self.browse_game_path)
        game_path_layout = QHBoxLayout()
        game_path_layout.addWidget(self.game_path_edit)
        game_path_layout.addWidget(game_path_btn)
        
        self.mods_dir_edit = QLineEdit(self.vm.get_mods_dir())
        mods_dir_btn = QPushButton("Browse")
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
        self.resize(600, 500)

        self.vm = MainViewModel()

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
        self.launch_btn.clicked.connect(self.vm.launch_game)
        self.launch_btn.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #4CAF50; color: white;")

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings)

        refresh_btn = QPushButton("Refresh Mods")
        refresh_btn.clicked.connect(self.vm.load_mods)

        top_layout.addWidget(self.launch_btn)
        top_layout.addWidget(settings_btn)
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        # Mod List
        layout.addWidget(QLabel("Mods:"))
        self.mod_list_widget = QListWidget()
        self.mod_list_widget.itemChanged.connect(self.on_mod_item_changed)
        layout.addWidget(self.mod_list_widget)
        
        # Log
        layout.addWidget(QLabel("Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(150)
        layout.addWidget(self.log_text)
        
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        if os.path.exists("icon.ico"):
            self.tray_icon.setIcon(QIcon("icon.ico"))
        else:
            pixmap = QIcon.fromTheme("system-run").pixmap(64, 64)
            self.tray_icon.setIcon(QIcon(pixmap))

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        self.tray_icon.show()

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
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

    def update_mod_list(self, mods_data):
        self.mod_list_widget.blockSignals(True)
        self.mod_list_widget.clear()

        for mod in mods_data:
            item = QListWidgetItem(mod["name"])
            item.setData(Qt.UserRole, mod["path"])
            item.setCheckState(Qt.Checked if mod["enabled"] else Qt.Unchecked)
            self.mod_list_widget.addItem(item)

        self.mod_list_widget.blockSignals(False)

    def on_mod_item_changed(self, item):
        mod_path = item.data(Qt.UserRole)
        checked = item.checkState() == Qt.Checked
        # Delegate to ViewModel
        self.vm.toggle_mod(mod_path, checked)

    def append_log(self, msg):
        self.log_text.append(msg)

    def on_game_status_changed(self, is_running):
        self.launch_btn.setEnabled(not is_running)
        self.mod_list_widget.setEnabled(not is_running)

        if is_running and self.vm.config.HideConsoleWhenRunning.get():
             self.hide()
             self.tray_icon.showMessage("StellaSora Mod Loader", "Game is running. Minimized to tray.", QSystemTrayIcon.Information, 3000)
        elif not is_running and self.vm.config.HideConsoleWhenRunning.get():
             self.show_window()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Dark Theme
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(palette.Window, Qt.Color("#2b2b2b"))
    palette.setColor(palette.WindowText, Qt.Color("#ffffff"))
    palette.setColor(palette.Base, Qt.Color("#1e1e1e"))
    palette.setColor(palette.AlternateBase, Qt.Color("#2b2b2b"))
    palette.setColor(palette.ToolTipBase, Qt.Color("#ffffff"))
    palette.setColor(palette.ToolTipText, Qt.Color("#ffffff"))
    palette.setColor(palette.Text, Qt.Color("#ffffff"))
    palette.setColor(palette.Button, Qt.Color("#323232"))
    palette.setColor(palette.ButtonText, Qt.Color("#ffffff"))
    palette.setColor(palette.BrightText, Qt.Color("#ff0000"))
    palette.setColor(palette.Link, Qt.Color("#42a5f5"))
    palette.setColor(palette.Highlight, Qt.Color("#42a5f5"))
    palette.setColor(palette.HighlightedText, Qt.Color("#000000"))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
