"""Custom tree widget for displaying mod list."""
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QHBoxLayout, QPushButton, QHeaderView
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QIcon

from core import get_resource_path
from viewmodels import ModData
from ..helpers import (
    FolderNode, build_folder_tree, collect_all_mods_from_folder, folder_has_images
)


class ModTreeWidget(QTreeWidget):
    """Tree widget for displaying and managing mods."""
    
    def __init__(
        self,
        on_toggle: Callable[[Path, bool], None],
        on_folder_toggle: Callable[[str, bool, list[ModData]], None],
        on_image_preview: Callable[[Path], None],
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.on_toggle = on_toggle
        self.on_folder_toggle = on_folder_toggle
        self.on_image_preview = on_image_preview
        
        self._setup_widget()
    
    def _setup_widget(self) -> None:
        self.setObjectName("modTreeWidget")
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setAutoScroll(False)
        self.setMouseTracking(False)
        self.setIndentation(20)
        self.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.header().resizeSection(1, 120)

    def populate(self, mods_data: list[ModData], mods_dir: Path) -> None:
        """Populate the tree with mod data."""
        self.clear()
        
        root_mods, folder_tree = build_folder_tree(mods_data)
        
        # Style settings
        folder_text_color = QBrush(QColor("#6CB4EE"))
        folder_font = QFont()
        folder_font.setBold(True)
        folder_icon = QIcon(get_resource_path("resources/folder.svg").as_posix())
        
        # Create folder items
        for folder_name in sorted(k for k in folder_tree.keys() if k != "_mods"):
            folder_path = mods_dir / folder_name
            self._populate_folder_item(
                self, folder_name, folder_tree[folder_name],
                folder_text_color, folder_font, folder_icon, folder_path
            )
        
        # Create root level items
        for mod in root_mods:
            mod_item = QTreeWidgetItem(self)
            mod_item.setText(0, mod["name"])
            mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
            btn = self._create_status_button(mod["path"], mod["enabled"])
            self.setItemWidget(mod_item, 1, btn)

    def _populate_folder_item(
        self,
        parent: "QTreeWidget | QTreeWidgetItem",
        folder_name: str,
        folder_node: FolderNode,
        folder_text_color: QBrush,
        folder_font: QFont,
        folder_icon: QIcon,
        folder_path: Path
    ) -> None:
        """Recursively create tree items for folders."""
        folder_item = QTreeWidgetItem(parent)
        folder_item.setText(0, folder_name)
        folder_item.setIcon(0, folder_icon)
        folder_item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "folder", "name": folder_name, "path": folder_path
        })
        folder_item.setForeground(0, folder_text_color)
        folder_item.setFont(0, folder_font)
        
        all_mods = collect_all_mods_from_folder(folder_node)
        all_enabled = all(m["enabled"] for m in all_mods) if all_mods else False
        has_images = folder_has_images(folder_path)
        
        folder_btn = self._create_folder_buttons_widget(
            folder_name, all_enabled, all_mods, folder_path, has_images
        )
        self.setItemWidget(folder_item, 1, folder_btn)
        
        # Subfolders
        for subfolder_name in sorted(k for k in folder_node.keys() if k != "_mods"):
            self._populate_folder_item(
                folder_item, subfolder_name, folder_node[subfolder_name],
                folder_text_color, folder_font, folder_icon, folder_path / subfolder_name
            )
        
        # Files
        if "_mods" in folder_node:
            for mod in folder_node["_mods"]:
                mod_item = QTreeWidgetItem(folder_item)
                mod_item.setText(0, mod["name"])
                mod_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
                btn = self._create_status_button(mod["path"], mod["enabled"])
                self.setItemWidget(mod_item, 1, btn)
        
        folder_item.setExpanded(True)

    def _create_button_container(self, btn: QPushButton) -> QWidget:
        """Wrap button in container aligned right."""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(btn)
        return container

    def _create_status_button(self, mod_path: Path, enabled: bool) -> QWidget:
        """Create a status button for a mod file."""
        btn = QPushButton("Enabled" if enabled else "Disabled")
        btn.setObjectName("enabledButton" if enabled else "disabledButton")
        btn.setFixedSize(65, 22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.on_toggle(mod_path, not enabled))
        return self._create_button_container(btn)

    def _create_folder_button(self, folder_name: str, all_enabled: bool, mods: list[ModData]) -> QPushButton:
        """Create toggle button for folder."""
        btn = QPushButton("Disable All" if all_enabled else "Enable All")
        btn.setObjectName("folderDisableButton" if all_enabled else "folderEnableButton")
        btn.setFixedSize(80, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.on_folder_toggle(folder_name, not all_enabled, mods))
        return btn
    
    def _create_photo_button(self, folder_path: Path) -> QPushButton:
        """Create photo preview button."""
        btn = QPushButton()
        btn.setIcon(QIcon(get_resource_path("resources/photo_library.svg").as_posix()))
        btn.setIconSize(QSize(18, 18))
        btn.setObjectName("photoButton")
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Preview images")
        btn.clicked.connect(lambda: self.on_image_preview(folder_path))
        return btn
    
    def _create_folder_buttons_widget(
        self, folder_name: str, all_enabled: bool,
        mods: list[ModData], folder_path: Path, has_images: bool
    ) -> QWidget:
        """Create container with photo and toggle buttons."""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(4)
        layout.addStretch()
        
        if has_images:
            layout.addWidget(self._create_photo_button(folder_path))
        
        layout.addWidget(self._create_folder_button(folder_name, all_enabled, mods))
        return container
