"""Stella Sora Mod Launcher - Entry Point."""
import sys
import argparse
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from instance_lock import SingleInstanceLock, find_and_focus_existing_window
from updater import is_running_as_exe


def quick_launch_mode() -> bool:
    """
    Quick Launch Mode - Launch game immediately without UI.
    
    Returns:
        True if game was launched successfully, False if should fall back to UI
    """
    from core import Config
    from launcher import GameLauncher
    
    config = Config('config.ini')
    launcher = GameLauncher(config)
    
    success, error = launcher.quick_launch()
    return success


def check_for_updates_dialog(parent: "QWidget | None" = None) -> bool:
    """
    Check for updates and show dialog if available.
    
    Returns:
        True if user chose to update (app will exit), False otherwise
    """
    from updater import check_for_updates
    from ui.dialogs import UpdateDialog
    
    update_info = check_for_updates()
    if update_info:
        dialog = UpdateDialog(update_info, parent)
        result = dialog.exec()
        return result == 1  # QDialog.Accepted
    
    return False


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Stella Sora Mod Launcher")
    parser.add_argument('--quicklaunch', action='store_true', 
                        help='Launch game directly without showing UI')
    args = parser.parse_args()
    
    # Single instance check
    lock = SingleInstanceLock()
    if not lock.acquire():
        # Another instance is running - try to focus it and exit
        find_and_focus_existing_window("Stella Sora Mod Launcher")
        sys.exit(0)
    
    # Quick launch mode
    if args.quicklaunch:
        if quick_launch_mode():
            # Game launched successfully - exit
            lock.release()
            sys.exit(0)
        # Fall through to show UI if quick launch failed
    
    # Normal startup - create Qt application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Apply Fusion style and load QSS stylesheet
    app.setStyle("Fusion")
    
    from ui import load_stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
    
    # Check for updates (only when running as exe)
    if is_running_as_exe():
        try:
            check_for_updates_dialog()
        except Exception:
            pass  # Ignore update check errors
    
    # Show main window
    from ui import MainWindow
    window = MainWindow()
    window.show()
    
    result = app.exec()
    lock.release()
    sys.exit(result)


if __name__ == "__main__":
    main()