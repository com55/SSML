"""Update dialog for showing available updates."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QProgressBar,
    QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

from updater import UpdateInfo, download_update, apply_update


class DownloadWorker(QThread):
    """Worker thread for downloading updates."""
    progress = Signal(int, int)  # downloaded, total
    finished = Signal(object)  # Path or None
    error = Signal(str)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
    
    def run(self):
        try:
            result = download_update(
                self.url,
                progress_callback=lambda d, t: self.progress.emit(d, t)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """Dialog for displaying update information and handling the update process."""
    
    def __init__(self, update_info: UpdateInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_worker = None
        self.downloaded_path = None
        
        self.setWindowTitle("Update Available")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(f"<h2>🎉 New Version Available!</h2>")
        header_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_label)
        
        # Version info
        version_layout = QHBoxLayout()
        current_label = QLabel(f"Current: <b>{self.update_info.current_version}</b>")
        current_label.setTextFormat(Qt.TextFormat.RichText)
        arrow_label = QLabel("  →  ")
        new_label = QLabel(f"New: <b style='color: #4CAF50;'>{self.update_info.latest_version}</b>")
        new_label.setTextFormat(Qt.TextFormat.RichText)
        
        version_layout.addWidget(current_label)
        version_layout.addWidget(arrow_label)
        version_layout.addWidget(new_label)
        version_layout.addStretch()
        layout.addLayout(version_layout)
        
        layout.addSpacing(10)
        
        # Release notes
        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notes_label)
        
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMarkdown(self.update_info.release_notes or "*No release notes available.*")
        layout.addWidget(self.notes_text)
        
        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.skip_btn = QPushButton("Skip This Version")
        self.skip_btn.clicked.connect(self.reject)
        
        self.later_btn = QPushButton("Remind Me Later")
        self.later_btn.clicked.connect(self.reject)
        
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setObjectName("updateButton")
        self.update_btn.setStyleSheet("""
            QPushButton#updateButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#updateButton:hover {
                background-color: #45a049;
            }
        """)
        self.update_btn.clicked.connect(self._start_download)
        
        button_layout.addWidget(self.skip_btn)
        button_layout.addWidget(self.later_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.update_btn)
        layout.addLayout(button_layout)
    
    def _start_download(self):
        """Start downloading the update."""
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Downloading update...")
        
        self.download_worker = DownloadWorker(self.update_info.download_url)
        self.download_worker.progress.connect(self._on_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()
    
    def _on_progress(self, downloaded: int, total: int):
        """Update progress bar."""
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.setValue(percent)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_label.setText(f"Downloading... {mb_downloaded:.1f} / {mb_total:.1f} MB")
    
    def _on_download_finished(self, path: Path | None):
        """Handle download completion."""
        if path:
            self.downloaded_path = path
            self.status_label.setText("Download complete! Applying update...")
            self.progress_bar.setValue(100)
            
            # Apply the update
            if apply_update(path):
                QMessageBox.information(
                    self,
                    "Update Ready",
                    "The update has been downloaded. The application will now restart to complete the update."
                )
                # Close the application to allow update
                self.accept()
                import sys
                sys.exit(0)
            else:
                QMessageBox.warning(
                    self,
                    "Update Failed",
                    "Failed to apply update automatically. Please download the update from the releases page manually."
                )
                self._reset_ui()
        else:
            self._on_download_error("Download failed - no file received")
    
    def _on_download_error(self, error_msg: str):
        """Handle download error."""
        QMessageBox.critical(
            self,
            "Download Error",
            f"Failed to download update:\n{error_msg}"
        )
        self._reset_ui()
    
    def _reset_ui(self):
        """Reset UI after error."""
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
