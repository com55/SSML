"""Stella Sora Mod Launcher - Entry Point."""
import sys
import traceback
import logging
import argparse
from types import TracebackType
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QLocale

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from instance_lock import SingleInstanceLock, find_and_focus_existing_window
from updater import is_running_as_exe

# Force English locale for consistent number formatting (prevent ๘๙% instead of 89%)
QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))


def setup_logging():
    log_file = "LatestLog.txt"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file


def global_exception_handler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None
):
    """Global handler for uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logging.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    error_msg = f"Uncaught exception:\n{exc_value}\n\nSee LatestLog.txt for details."
    show_error_dialog("Stella Sora Mod Launcher - Fatal Error", error_msg)


def show_error_dialog(title: str, message: str):
    """Show error dialog even if QApplication is not yet created"""
    try:
        # Try to get existing QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setDetailedText(traceback.format_exc())
        msg_box.exec()
    except Exception:
        # If Qt fails, print to console
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"ERROR: {title}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(message, file=sys.stderr)
        print(f"\nDetails:\n{traceback.format_exc()}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)


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
    log_file = setup_logging()
    sys.excepthook = global_exception_handler
    
    try:
        logging.info("Application starting...")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Stella Sora Mod Launcher")
        parser.add_argument('--quicklaunch', action='store_true', 
                            help='Launch game directly without showing UI')
        parser.add_argument('--after-update', action='store_true',
                            help='Skip update check (used after auto-update)')
        args = parser.parse_args()
        
        # Single instance check
        lock = SingleInstanceLock()
        if not lock.acquire():
            logging.info("Another instance is already running")
            # Another instance is running - try to focus it and exit
            find_and_focus_existing_window("Stella Sora Mod Launcher")
            sys.exit(0)
        
        # Quick launch mode
        if args.quicklaunch:
            logging.info("Quick launch mode activated")
            if quick_launch_mode():
                logging.info("Game launched successfully via quick launch")
                # Game launched successfully - exit
                lock.release()
                sys.exit(0)
            logging.warning("Quick launch failed, showing UI")
            # Fall through to show UI if quick launch failed
        
        # Normal startup - create Qt application
        logging.info("Creating Qt application")
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        # Apply Fusion style and load QSS stylesheet
        app.setStyle("Fusion")
        logging.info("Applied Fusion style")
        
        from ui import load_stylesheet
        stylesheet = load_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
            logging.info("Loaded custom stylesheet")
        
        # Check for updates (only when running as exe, skip after auto-update)
        if is_running_as_exe() and not args.after_update:
            logging.info("Checking for updates...")
            try:
                check_for_updates_dialog()
            except Exception as e:
                logging.error(f"Update check failed: {e}", exc_info=True)
        elif args.after_update:
            logging.info("Skipping update check (started after auto-update)")
        
        # Show main window
        logging.info("Creating main window")
        from ui import MainWindow
        window = MainWindow()
        window.show()
        logging.info("Main window shown")
        
        result = app.exec()
        logging.info(f"Application exited with code: {result}")
        lock.release()
        sys.exit(result)
        
    except Exception as e:
        error_msg = f"Fatal error occurred:\n{str(e)}\n\nLog file: {log_file}"
        logging.critical(f"Fatal error: {e}", exc_info=True)
        show_error_dialog("Stella Sora Mod Launcher - Fatal Error", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()