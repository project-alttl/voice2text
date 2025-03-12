import sys
from PySide6.QtWidgets import QApplication
import filedropwidget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = filedropwidget.VideoDropWidget()
    window.show()
    sys.exit(app.exec())
