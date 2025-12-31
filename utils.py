"""Utility functions for path handling and other common tasks."""
import sys
from pathlib import Path

def get_resource_path(path: str) -> Path:
    """
    Get the absolute path to a resource file.
    
    Use this for files that are embedded within the executable (in onefile mode)
    or distributed with the source code.
    
    Args:
        path: Relative path to the resource (e.g., "resources/icon.ico")
        
    Returns:
        Absolute Path object
    """
    # When running as Nuitka onefile, __file__ points to the temporary directory
    # where resources are unpacked.
    return Path(__file__).parent / path


def get_exe_path(path: str = "") -> Path:
    """
    Get the absolute path relative to the executable directory.
    
    Use this for external files that should live next to the executable,
    such as config.ini, Mods/, Backups/, etc.
    
    Args:
        path: Relative path from the executable directory
        
    Returns:
        Absolute Path object
    """
    # sys.argv[0] is reliable for Nuitka compiled exe
    return Path(sys.argv[0]).resolve().parent.joinpath(path)
