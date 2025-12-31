"""Shared type definitions for viewmodels."""
from pathlib import Path
from typing import TypedDict


class ModData(TypedDict):
    """Type definition for mod data dictionary."""
    name: str
    enabled: bool
    path: Path
    relative_path: str  # e.g. "Chitose/char_2d_14401.unity3d"
