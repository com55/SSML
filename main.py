import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QLabel, QFileDialog, QCheckBox, QDialog,
                               QFormLayout, QLineEdit, QSystemTrayIcon, QMenu, QHeaderView,
                               QMessageBox)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QAction, QBrush, QColor, QFont
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

        self.hide_console_chk = QCheckBox("Minimize to Tray when running")
        self.hide_console_chk.setChecked(self.vm.get_hide_console())

        form.addRow("Game Executable:", game_path_layout)
        form.addRow("Mods Directory:", mods_dir_layout)
        form.addRow("Mod Extension:", self.mod_ext_edit)
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
        self.launch_btn.setIconSize(QSize(20, 20))
        self.launch_btn.setObjectName("launchButton")
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.clicked.connect(self.vm.launch_game)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(MaterialIcon('settings'))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(MaterialIcon('refresh'))
        self.refresh_btn.setIconSize(QSize(18, 18))
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.mod_tree_widget.header().resizeSection(1, 90)  # Fixed width for button column
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
        self.mod_tree_widget.clear()
        
        # Group mods by folder
        folder_items: dict[str, QTreeWidgetItem] = {}
        root_mods: list[ModData] = []
        folder_mods: dict[str, list[ModData]] = {}
        
        for mod in mods_data:
            parts = mod["relative_path"].split("/")
            if len(parts) == 1:
                # Root level mod
                root_mods.append(mod)
            else:
                # Mod in subfolder
                folder_name = parts[0]
                if folder_name not in folder_mods:
                    folder_mods[folder_name] = []
                folder_mods[folder_name].append(mod)
        
        # Create folder items first
        folder_text_color = QBrush(QColor("#6CB4EE"))  # Light blue for folder names
        folder_font = QFont()
        folder_font.setBold(True)
        folder_icon = MaterialIcon('folder', fill=True)
        folder_icon.set_color("#6CB4EE")
        for folder_name in sorted(folder_mods.keys()):
            folder_item = QTreeWidgetItem(self.mod_tree_widget)
            folder_item.setText(0, folder_name)
            folder_item.setIcon(0, folder_icon)
            folder_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "name": folder_name})
            # Set folder text color and bold font to distinguish from files
            folder_item.setForeground(0, folder_text_color)
            folder_item.setFont(0, folder_font)
            folder_items[folder_name] = folder_item
            
            # Add folder toggle button
            mods_in_folder = folder_mods[folder_name]
            all_enabled = all(m["enabled"] for m in mods_in_folder)
            folder_btn = self.create_folder_button(folder_name, all_enabled, mods_in_folder)
            self.mod_tree_widget.setItemWidget(folder_item, 1, folder_btn)
            
            # Add mod items under folder
            for mod in mods_in_folder:
                mod_item = QTreeWidgetItem(folder_item)
                mod_item.setText(0, mod["name"])
                mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
                
                # Add toggle button
                btn = self.create_status_button(mod["path"], mod["enabled"])
                self.mod_tree_widget.setItemWidget(mod_item, 1, btn)
            
            folder_item.setExpanded(True)
        
        # Create root level mod items
        for mod in root_mods:
            mod_item = QTreeWidgetItem(self.mod_tree_widget)
            mod_item.setText(0, mod["name"])
            mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
            
            # Add toggle button
            btn = self.create_status_button(mod["path"], mod["enabled"])
            self.mod_tree_widget.setItemWidget(mod_item, 1, btn)

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

    def create_folder_button(self, folder_name: str, all_enabled: bool, mods: list[ModData]) -> QWidget:
        """Create a toggle all button for a folder."""
        btn = QPushButton("Disable All" if all_enabled else "Enable All")
        btn.setObjectName("folderDisableButton" if all_enabled else "folderEnableButton")
        btn.setFixedSize(80, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.on_folder_toggle_clicked(folder_name, not all_enabled, mods))
        return self.create_button_container(btn)

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

    def append_log(self, msg: str) -> None:
        self.log_text.append(msg)

    def on_game_status_changed(self, is_running: bool) -> None:
        self.is_running = is_running
        self.launch_btn.setEnabled(not is_running)
        self.launch_btn.setText("Launch Game" if not is_running else "Game is running")
        self.refresh_btn.setEnabled(not is_running)
        self.settings_btn.setEnabled(not is_running)
        self.mod_tree_widget.setEnabled(not is_running)

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
