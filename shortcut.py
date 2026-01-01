"""Windows shortcut creation utilities."""
import sys
import os
from pathlib import Path

from updater import is_running_as_exe
from utils import get_resource_path


def create_quicklaunch_shortcut() -> tuple[bool, str]:
    """
    Create a Desktop shortcut for Quick Launch mode.
    
    The shortcut will launch the application with --quicklaunch argument,
    which skips the UI and launches the game directly.
    
    Returns:
        (success: bool, message: str)
    """
    # Only works when running as Nuitka-compiled executable
    if not is_running_as_exe():
        return False, "Quick Launch shortcut can only be created from the .exe version"
    
    try:
        import win32com.client
        
        # Get desktop path
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if not desktop.exists():
            return False, f"Desktop folder not found: {desktop}"
        
        # Get current exe path (use sys.argv[0] for Nuitka)
        exe_path = Path(sys.argv[0]).resolve()
        icon_path = get_resource_path("icon.ico")
        
        # Create shortcut
        shortcut_path = desktop / "SSML Quick Start.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        
        shortcut.TargetPath = str(exe_path)
        shortcut.Arguments = "--quicklaunch"
        shortcut.WorkingDirectory = str(exe_path.parent)
        
        if icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        else:
            shortcut.IconLocation = str(exe_path)
        
        shortcut.Description = "Launch Stella Sora with mods (Quick Launch - No UI)"
        shortcut.save()
        
        return True, f"Shortcut created on Desktop: {shortcut_path.name}"
        
    except ImportError:
        return False, "pywin32 is not installed. Cannot create shortcut."
    except Exception as e:
        return False, f"Failed to create shortcut: {e}"


def create_normal_shortcut() -> tuple[bool, str]:
    """
    Create a normal Desktop shortcut for the application.
    
    Returns:
        (success: bool, message: str)
    """
    if not is_running_as_exe():
        return False, "Shortcut can only be created from the .exe version"
    
    try:
        import win32com.client
        
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if not desktop.exists():
            return False, f"Desktop folder not found: {desktop}"
        
        exe_path = Path(sys.argv[0]).resolve()
        icon_path = get_resource_path("icon.ico")
        
        shortcut_path = desktop / "SSML.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        
        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        
        if icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        else:
            shortcut.IconLocation = str(exe_path)
        
        shortcut.Description = "Stella Sora Mod Launcher"
        shortcut.save()
        
        return True, f"Shortcut created on Desktop: {shortcut_path.name}"
        
    except ImportError:
        return False, "pywin32 is not installed. Cannot create shortcut."
    except Exception as e:
        return False, f"Failed to create shortcut: {e}"
