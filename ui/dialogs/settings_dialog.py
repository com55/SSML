"""Settings dialog for application configuration."""
from PySide6.QtGui import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFormLayout, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QLabel, QFrame
)

from viewmodels import SettingsViewModel
from updater import get_current_version, is_running_as_exe


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(500, 420)
        self.vm = SettingsViewModel()
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Game path
        self.game_path_edit = QLineEdit(self.vm.get_game_path())
        self.game_path_edit.setCursorPosition(0)
        game_path_btn = QPushButton("Browse")
        game_path_btn.setObjectName("browseButton")
        game_path_btn.clicked.connect(self.browse_game_path)
        game_path_layout = QHBoxLayout()
        game_path_layout.addWidget(self.game_path_edit)
        game_path_layout.addWidget(game_path_btn)
        
        # Mods directory
        self.mods_dir_edit = QLineEdit(self.vm.get_mods_dir())
        self.mods_dir_edit.setCursorPosition(0)
        mods_dir_btn = QPushButton("Browse")
        mods_dir_btn.setObjectName("browseButton")
        mods_dir_btn.clicked.connect(self.browse_mods_dir)
        mods_dir_layout = QHBoxLayout()
        mods_dir_layout.addWidget(self.mods_dir_edit)
        mods_dir_layout.addWidget(mods_dir_btn)

        # Backups directory
        self.backups_dir_edit = QLineEdit(self.vm.get_backups_dir())
        self.backups_dir_edit.setCursorPosition(0)
        backups_dir_btn = QPushButton("Browse")
        backups_dir_btn.setObjectName("browseButton")
        backups_dir_btn.clicked.connect(self.browse_backups_dir)
        backups_dir_layout = QHBoxLayout()
        backups_dir_layout.addWidget(self.backups_dir_edit)
        backups_dir_layout.addWidget(backups_dir_btn)

        # Mod extension
        self.mod_ext_edit = QLineEdit(self.vm.get_mod_ext())

        # Hide console checkbox
        self.hide_console_chk = QCheckBox("Minimize to Tray when running")
        self.hide_console_chk.setChecked(self.vm.get_hide_console())

        # Non-permanent mode checkbox
        self.non_permanent_chk = QCheckBox("Non-permanent mode (restore when exit game)")
        self.non_permanent_chk.setToolTip(
            "Mods are applied only when launching game and restored when game closes.\n"
            "Allows easy switching between modded and official launcher."
        )
        self.non_permanent_chk.setChecked(self.vm.get_non_permanent_mode())

        # Add form rows
        form.addRow("Game Executable:", game_path_layout)
        form.addRow("Mods Directory:", mods_dir_layout)
        form.addRow("Backups Directory:", backups_dir_layout)
        form.addRow("Mod Extension:", self.mod_ext_edit)
        form.addRow("", self.hide_console_chk)
        form.addRow("", self.non_permanent_chk)

        layout.addLayout(form)
        
        # Separator - Shortcuts section
        self._add_separator(layout, "Shortcuts")
        
        # Quick Launch Shortcut button
        shortcut_layout = QHBoxLayout()
        
        self.normal_shortcut_btn = QPushButton("Create Normal Shortcut")
        self.normal_shortcut_btn.setObjectName("normalShortcutButton")
        self.normal_shortcut_btn.setToolTip("Creates a standard Desktop shortcut for the application")
        self.normal_shortcut_btn.clicked.connect(self.create_normal_shortcut)

        self.shortcut_btn = QPushButton("Create Quick Launch Shortcut")
        self.shortcut_btn.setObjectName("quickLaunchButton")
        self.shortcut_btn.setToolTip("Creates a Desktop shortcut that launches the game directly without showing UI")
        self.shortcut_btn.clicked.connect(self.create_quicklaunch_shortcut)
        
        # Disable buttons if not running as exe
        if not is_running_as_exe():
            self.normal_shortcut_btn.setEnabled(False)
            self.normal_shortcut_btn.setToolTip("Shortcut can only be created from the .exe version")
            self.shortcut_btn.setEnabled(False)
            self.shortcut_btn.setToolTip("Quick Launch shortcut can only be created from the .exe version")
        
        shortcut_layout.addWidget(self.normal_shortcut_btn)
        shortcut_layout.addWidget(self.shortcut_btn)
        shortcut_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(shortcut_layout)
        
        # Separator - Updates section  
        self._add_separator(layout, "Updates")
        
        # Version and check updates
        update_layout = QHBoxLayout()
        self.update_btn = QPushButton("Check for Updates")
        self.update_btn.setObjectName("checkUpdatesButton")
        self.update_btn.setFixedWidth(145)
        self.update_btn.clicked.connect(self.check_for_updates)
        
        # Disable button if not running as exe
        if not is_running_as_exe():
            self.update_btn.setEnabled(False)
            self.update_btn.setToolTip("Update check only works from the .exe version")
        
        update_layout.addWidget(self.update_btn)
        
        # Include Beta Releases checkbox
        self.include_beta_chk = QCheckBox("Include Beta Releases")
        self.include_beta_chk.setToolTip("When checked, manual update check will also look for pre-release versions (alpha, beta, rc)")
        
        if not is_running_as_exe():
            self.include_beta_chk.setEnabled(False)
            self.include_beta_chk.setToolTip("Include Beta Releases only works from the .exe version")
        
        update_layout.addWidget(self.include_beta_chk)
        
        update_layout.addStretch()
        
        version_label = QLabel(f"Current Version: {get_current_version()}")
        update_layout.addWidget(version_label)
        

        layout.addLayout(update_layout)
        
        layout.addStretch()

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
    
    def _add_separator(self, layout: QVBoxLayout, title: str) -> None:
        """Add a separator with title."""
        separator_layout = QHBoxLayout()
        
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        
        label = QLabel(title)
        label.setStyleSheet("color: #888; font-weight: bold;")
        
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        
        separator_layout.addWidget(line1, 1)
        separator_layout.addWidget(label)
        separator_layout.addWidget(line2, 1)
        
        layout.addSpacing(10)
        layout.addLayout(separator_layout)
        layout.addSpacing(5)

    def browse_game_path(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "", "StellaSora (StellaSora.exe)"
        )
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
    
    def create_normal_shortcut(self):
        """Create a normal Desktop shortcut."""
        from shortcut import create_normal_shortcut
        
        success, message = create_normal_shortcut()
        if success:
            QMessageBox.information(self, "Shortcut Created", message)
        else:
            QMessageBox.warning(self, "Shortcut Failed", message)
    
    def create_quicklaunch_shortcut(self):
        """Create a Quick Launch desktop shortcut."""
        from shortcut import create_quicklaunch_shortcut
        
        success, message = create_quicklaunch_shortcut()
        if success:
            QMessageBox.information(self, "Shortcut Created", message)
        else:
            QMessageBox.warning(self, "Shortcut Failed", message)
    
    def check_for_updates(self):
        """Check for updates and show dialog if available."""
        from updater import check_for_updates
        from .update_dialog import UpdateDialog
        
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Checking...")
        
        try:
            update_info = check_for_updates(include_prerelease=self.include_beta_chk.isChecked())
            
            if update_info:
                dialog = UpdateDialog(update_info, self)
                dialog.exec()
            else:
                QMessageBox.information(
                    self,
                    "No Updates",
                    "You are running the latest version."
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Update Check Failed",
                f"Failed to check for updates:\n{e}"
            )
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("Check for Updates")

    def save_settings(self):
        self.vm.set_game_path(self.game_path_edit.text())
        self.vm.set_mods_dir(self.mods_dir_edit.text())
        self.vm.set_backups_dir(self.backups_dir_edit.text())
        self.vm.set_mod_ext(self.mod_ext_edit.text())
        self.vm.set_hide_console(self.hide_console_chk.isChecked())
        self.vm.set_non_permanent_mode(self.non_permanent_chk.isChecked())
        self.accept()

