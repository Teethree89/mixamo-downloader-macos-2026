# Third-party modules
from PySide6 import QtWidgets

# Local modules
from ui import MixamoDownloaderUI


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MixamoDownloaderUI()
    window.show()
    app.exec()
