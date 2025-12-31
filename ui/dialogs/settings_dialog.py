"""Settings dialog for application configuration."""
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFormLayout, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox
)

from viewmodels import SettingsViewModel


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(500, 300)
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

        # Add form rows
        form.addRow("Game Executable:", game_path_layout)
        form.addRow("Mods Directory:", mods_dir_layout)
        form.addRow("Backups Directory:", backups_dir_layout)
        form.addRow("Mod Extension:", self.mod_ext_edit)
        form.addRow("", self.hide_console_chk)

        layout.addLayout(form)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

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

    def save_settings(self):
        self.vm.set_game_path(self.game_path_edit.text())
        self.vm.set_mods_dir(self.mods_dir_edit.text())
        self.vm.set_backups_dir(self.backups_dir_edit.text())
        self.vm.set_mod_ext(self.mod_ext_edit.text())
        self.vm.set_hide_console(self.hide_console_chk.isChecked())
        self.accept()
