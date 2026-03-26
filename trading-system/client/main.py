#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 is not installed. Installing...")
        os.system("pip install PyQt6")
        from PyQt6.QtWidgets import QApplication

    from client.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
