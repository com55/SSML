"""Custom tree widget for displaying mod list."""
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QHBoxLayout, QPushButton, QHeaderView,
    QTreeWidgetItemIterator
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QIcon

from utils import get_resource_path
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
        """Populate the tree with mod data, reusing existing items."""
        # Save current scroll position
        current_scroll = self.verticalScrollBar().value()
        
        # Index existing items by path
        items_map = self._get_items_map()
        
        root_mods, folder_tree = build_folder_tree(mods_data)
        
        # Style settings
        folder_text_color = QBrush(QColor("#6CB4EE"))
        folder_font = QFont()
        folder_font.setBold(True)
        folder_icon = QIcon(get_resource_path("resources/folder.svg").as_posix())
        
        # 1. Process Folders
        for folder_name in sorted(k for k in folder_tree.keys() if k != "_mods"):
            folder_path = mods_dir / folder_name
            self._update_or_create_folder_item(
                self, folder_name, folder_tree[folder_name],
                folder_text_color, folder_font, folder_icon, folder_path,
                items_map
            )
        
        # 2. Process Root Files
        for mod in root_mods:
            mod_path = mod["path"]
            if mod_path in items_map:
                # Update existing
                item = items_map.pop(mod_path)
                # If parent changed, move it (unlikely but possible)
                if item.parent() is not None:
                     # It was in a folder, now it's root. Retaking ownership is tricky in Qt.
                     # Easiest way: takeFromParent if we really supported move.
                     # For now, let's assume structure is relatively static or handle simple reparent.
                     item.parent().removeChild(item)
                     self.addTopLevelItem(item)
                
                self._update_file_item(item, mod)
            else:
                # Create new
                mod_item = QTreeWidgetItem(self)
                self._update_file_item(mod_item, mod, is_new=True)

        # 3. Cleanup items that are no longer present
        for path, item in items_map.items():
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))
                
        # Restore scroll position
        self.verticalScrollBar().setValue(current_scroll)

    def _get_items_map(self) -> dict[Path, QTreeWidgetItem]:
        """Map all current items by their path."""
        items = {}
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and "path" in data:
                items[data["path"]] = item
            iterator += 1
        return items

    def _update_or_create_folder_item(
        self,
        parent: "QTreeWidget | QTreeWidgetItem",
        folder_name: str,
        folder_node: FolderNode,
        folder_text_color: QBrush,
        folder_font: QFont,
        folder_icon: QIcon,
        folder_path: Path,
        items_map: dict[Path, QTreeWidgetItem]
    ) -> None:
        """Recursively update or create folder items."""
        # Find or create item
        if folder_path in items_map:
            folder_item = items_map.pop(folder_path)
            # Handle move/reparent if necessary
            current_parent = folder_item.parent() or self
            if current_parent != parent:
                if isinstance(current_parent, QTreeWidget):
                    current_parent.takeTopLevelItem(current_parent.indexOfTopLevelItem(folder_item))
                else:
                    current_parent.removeChild(folder_item)
                
                if isinstance(parent, QTreeWidget):
                    parent.addTopLevelItem(folder_item)
                else:
                    parent.addChild(folder_item)
        else:
            folder_item = QTreeWidgetItem(parent)
            folder_item.setExpanded(True) # Default expand for new folders

        # Update visuals
        folder_item.setText(0, folder_name)
        folder_item.setIcon(0, folder_icon)
        folder_item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "folder", "name": folder_name, "path": folder_path
        })
        folder_item.setForeground(0, folder_text_color)
        folder_item.setFont(0, folder_font)
        
        # Calculate stats
        all_mods = collect_all_mods_from_folder(folder_node)
        all_enabled = all(m["enabled"] for m in all_mods) if all_mods else False
        has_images = folder_has_images(folder_path)
        
        # Update/Create Widget
        self._update_folder_widget(folder_item, folder_name, all_enabled, all_mods, folder_path, has_images)
        
        # Process Children (Subfolders)
        for subfolder_name in sorted(k for k in folder_node.keys() if k != "_mods"):
            self._update_or_create_folder_item(
                folder_item, subfolder_name, folder_node[subfolder_name],
                folder_text_color, folder_font, folder_icon, folder_path / subfolder_name,
                items_map
            )
            
        # Process Children (Files)
        if "_mods" in folder_node:
            for mod in folder_node["_mods"]:
                mod_path = mod["path"]
                if mod_path in items_map:
                    mod_item = items_map.pop(mod_path)
                    # Reparent check
                    if mod_item.parent() != folder_item:
                        if mod_item.parent():
                            mod_item.parent().removeChild(mod_item)
                        else:
                            self.takeTopLevelItem(self.indexOfTopLevelItem(mod_item))
                        folder_item.addChild(mod_item)
                    
                    self._update_file_item(mod_item, mod)
                else:
                    mod_item = QTreeWidgetItem(folder_item)
                    self._update_file_item(mod_item, mod, is_new=True)

    def _update_file_item(self, item: QTreeWidgetItem, mod: ModData, is_new: bool = False) -> None:
        """Update a file item's content and widget."""
        item.setText(0, mod["name"])
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "path": mod["path"]})
        
        # Widget
        if is_new:
            btn = self._create_status_button(mod["path"], mod["enabled"])
            self.setItemWidget(item, 1, btn)
        else:
            container = self.itemWidget(item, 1)
            if container:
                self._update_status_button(container, mod["path"], mod["enabled"])
            else:
                # Fallback if widget is missing for some reason
                btn = self._create_status_button(mod["path"], mod["enabled"])
                self.setItemWidget(item, 1, btn)

    def _update_status_button(self, container: QWidget, mod_path: Path, enabled: bool) -> None:
        """Update existing status button widget."""
        # The container has a layout with stretch and the button
        # We need to find the button. It should be the last item or specific type.
        # Based on _create_button_container, layout.addWidget(btn) is last.
        
        btn = container.findChild(QPushButton)
        if not btn:
            return

        text = "Enabled" if enabled else "Disabled"
        obj_name = "enabledButton" if enabled else "disabledButton"
        
        # Only update if changed to avoid unnecessary repaints/flickers? 
        # Actually we should update always to ensure state correctness, 
        # but setText shouldn't reset cursor unless layout shifts.
        if btn.text() != text:
            btn.setText(text)
        
        if btn.objectName() != obj_name:
            btn.setObjectName(obj_name)
            # Force style refresh might be needed if using qss by ID
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
        # Reconnect signal to capture new state? 
        # The old lambda captured old 'enabled' state.
        try:
            btn.clicked.disconnect()
        except Exception:
            pass # No connections
            
        btn.clicked.connect(lambda: self.on_toggle(mod_path, not enabled))

    def _update_folder_widget(
        self, item: QTreeWidgetItem, folder_name: str, all_enabled: bool,
        mods: list[ModData], folder_path: Path, has_images: bool
    ) -> None:
        """Update or create the folder widget container."""
        container = self.itemWidget(item, 1)
        
        # If widget structure requirements changed (e.g. image button appeared/disappeared),
        # it might be easier to recreate. But let's try to reuse if possible.
        # Container structure: [Stretch, PhotoButton (opt), ToggleButton]
        
        needs_recreate = False
        if not container:
            needs_recreate = True
        else:
            # Check if photo button presence matches has_images
            photo_btn = container.findChild(QPushButton, "photoButton")
            if (has_images and not photo_btn) or (not has_images and photo_btn):
                needs_recreate = True
        
        if needs_recreate:
            new_widget = self._create_folder_buttons_widget(folder_name, all_enabled, mods, folder_path, has_images)
            self.setItemWidget(item, 1, new_widget)
            return

        # Reuse existing
        # Update Toggle Button
        toggle_btn = container.findChild(QPushButton, "folderEnableButton") or \
                     container.findChild(QPushButton, "folderDisableButton")
                     
        if toggle_btn:
            text = "Disable All" if all_enabled else "Enable All"
            obj_name = "folderDisableButton" if all_enabled else "folderEnableButton"
            
            if toggle_btn.text() != text:
                toggle_btn.setText(text)
            
            if toggle_btn.objectName() != obj_name:
                toggle_btn.setObjectName(obj_name)
                toggle_btn.style().unpolish(toggle_btn)
                toggle_btn.style().polish(toggle_btn)
            
            try:
                toggle_btn.clicked.disconnect()
            except Exception:
                pass
            toggle_btn.clicked.connect(lambda: self.on_folder_toggle(folder_name, not all_enabled, mods))
            
        # Photo button path update (unlikely to change for same folder, but for safety)
        if has_images:
            photo_btn = container.findChild(QPushButton, "photoButton")
            if photo_btn:
                 try:
                    photo_btn.clicked.disconnect()
                 except Exception:
                    pass
                 photo_btn.clicked.connect(lambda: self.on_image_preview(folder_path))

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
