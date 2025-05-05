# main.py
import sys
from PyQt6.QtWidgets import QApplication
from MainWindow import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Optional: Set App details
    app.setOrganizationName("MyCompany")
    app.setApplicationName("PyTakeoff")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())