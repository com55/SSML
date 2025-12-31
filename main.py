"""Stella Sora Mod Launcher - Entry Point."""
import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow, load_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Apply Fusion style and load QSS stylesheet
    app.setStyle("Fusion")
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()