"""Image preview dialog for viewing mod images."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QKeyEvent, QResizeEvent

from ..helpers import IMAGE_EXTENSIONS


class ImagePreviewDialog(QDialog):
    """Dialog to preview images in a folder."""
    
    def __init__(self, folder_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.folder_path = folder_path
        self.image_files: list[Path] = []
        self.current_index = 0
        self.is_fullscreen = False
        
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
        self.fullscreen_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        top_layout.addWidget(self.fullscreen_btn)
        
        layout.addLayout(top_layout)
        
        # Image display area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #1a1a2e;")
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("padding: 10px;")
        self.scroll_area.setWidget(self.image_label)
        
        layout.addWidget(self.scroll_area, 1)
        
        # Navigation
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self._prev_image)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
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
        
        current_file = self.image_files[self.current_index]
        pixmap = QPixmap(str(current_file))
        
        if pixmap.isNull():
            self.image_label.setText(f"Failed to load: {current_file.name}")
        else:
            scaled = pixmap.scaled(
                self.scroll_area.width() - 30,
                self.scroll_area.height() - 30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        
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
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
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
    
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.image_files:
            self._update_display()
