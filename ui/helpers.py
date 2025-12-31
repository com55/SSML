"""UI helper functions and utilities."""
from pathlib import Path
from typing import Any

from core import get_resource_path
from viewmodels import ModData


# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

# Type alias for nested folder structure
FolderNode = dict[str, Any]  # {"_mods": list[ModData], "subfolder_name": FolderNode, ...}


def load_stylesheet() -> str:
    """Load the QSS stylesheet from embedded resource."""
    style_path = get_resource_path("style.qss")
    if style_path.exists():
        return style_path.read_text(encoding="utf-8")
    return ""


def get_app_icon_path() -> Path:
    """Get the path to the application icon from embedded resource."""
    return get_resource_path("icon.ico")


def build_folder_tree(mods_data: list[ModData]) -> tuple[list[ModData], FolderNode]:
    """Build nested folder structure from flat mod list.
    
    Returns:
        Tuple of (root_mods, folder_tree) where:
        - root_mods: list of mods at root level
        - folder_tree: nested dict structure for subfolders
    """
    root_mods: list[ModData] = []
    tree: FolderNode = {}
    
    for mod in mods_data:
        parts = mod["relative_path"].split("/")
        if len(parts) == 1:
            # Root level mod (no subfolder)
            root_mods.append(mod)
        else:
            # Mod in subfolder - navigate/create path in tree
            current = tree
            for folder in parts[:-1]:  # All folders except filename
                if folder not in current:
                    current[folder] = {"_mods": []}
                current = current[folder]
            # Ensure _mods key exists
            if "_mods" not in current:
                current["_mods"] = []
            current["_mods"].append(mod)
    
    return root_mods, tree


def collect_all_mods_from_folder(folder_node: FolderNode) -> list[ModData]:
    """Recursively collect all mods from a folder and its subfolders."""
    mods: list[ModData] = []
    
    # Add mods directly in this folder
    if "_mods" in folder_node:
        mods.extend(folder_node["_mods"])
    
    # Recursively add mods from subfolders
    for key, value in folder_node.items():
        if key != "_mods" and isinstance(value, dict):
            mods.extend(collect_all_mods_from_folder(value))
    
    return mods


def folder_has_images(folder_path: Path) -> bool:
    """Check if a folder contains any image files."""
    if not folder_path.exists() or not folder_path.is_dir():
        return False
    for file in folder_path.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
            return True
    return False

