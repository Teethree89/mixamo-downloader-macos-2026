# Stdlib modules
import json

# Third-party modules
from PySide6 import QtCore, QtGui, QtWebEngineWidgets, QtWidgets

# Local modules
from downloader import HEADERS
from downloader import MixamoDownloader
from webpage import CustomWebPage


class MixamoDownloaderUI(QtWidgets.QMainWindow):
    """Main UI that allows users to bulk download animations from Mixamo."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Mixamo Downloader — macOS 2026')
        self.setGeometry(100, 100, 1200, 840)

        self.browser = QtWebEngineWidgets.QWebEngineView()
        page = CustomWebPage()
        page.setUrl(QtCore.QUrl('https://www.mixamo.com'))
        self.browser.setPage(page)
        page.retrieved_token.connect(self.apply_token)

        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(14)
        central_widget.setLayout(layout)
        layout.addWidget(self.browser)

        footer_lyt = QtWidgets.QVBoxLayout()
        layout.addLayout(footer_lyt)

        anim_opt_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(anim_opt_lyt)

        self.rb_all = QtWidgets.QRadioButton("All animations")
        self.rb_all.setChecked(True)
        self.rb_query = QtWidgets.QRadioButton("Animations containing the word:")
        self.le_query = QtWidgets.QLineEdit()
        self.le_query.setEnabled(False)
        self.rb_tpose = QtWidgets.QRadioButton("T-Pose (with skin)")

        self.rb_query.toggled.connect(lambda checked: self.le_query.setEnabled(checked))
        self.rb_all.toggled.connect(lambda checked: checked and self.le_query.setEnabled(False))
        self.rb_tpose.toggled.connect(lambda checked: checked and self.le_query.setEnabled(False))

        anim_opt_lyt.addWidget(self.rb_all)
        anim_opt_lyt.addWidget(self.rb_query)
        anim_opt_lyt.addWidget(self.le_query)
        anim_opt_lyt.addWidget(self.rb_tpose)

        self.cb_in_place = QtWidgets.QCheckBox("Prefer native Mixamo In Place when available")
        self.cb_in_place.setChecked(True)
        self.cb_in_place.setToolTip(
            "For animations whose Mixamo metadata exposes an In Place control, "
            "request that native variant. Other clips are downloaded unchanged."
        )
        footer_lyt.addWidget(self.cb_in_place)

        output_dir_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(output_dir_lyt)

        gbox_output = QtWidgets.QGroupBox("Output Folder")
        gbox_output.setMaximumHeight(72)
        gbox_output_lyt = QtWidgets.QHBoxLayout()
        gbox_output.setLayout(gbox_output_lyt)

        self.le_path = QtWidgets.QLineEdit()
        tb_path = QtWidgets.QToolButton()
        icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
        tb_path.setIcon(icon)
        tb_path.clicked.connect(self.set_path)
        gbox_output_lyt.addWidget(self.le_path)
        gbox_output_lyt.addWidget(tb_path)
        output_dir_lyt.addWidget(gbox_output)

        self.get_btn = QtWidgets.QPushButton('Start download')
        self.get_btn.clicked.connect(self.get_access_token)
        footer_lyt.addWidget(self.get_btn)

        prog_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(prog_lyt)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFormat("Downloading %v/%m")
        self.progress_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        prog_lyt.addWidget(self.progress_bar)

        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_download)
        prog_lyt.addWidget(self.stop_btn)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(500)
        self.log_box.setPlaceholderText("Downloader status will appear here…")
        self.log_box.setMaximumHeight(130)
        footer_lyt.addWidget(self.log_box)

        self.setCentralWidget(central_widget)

    def append_log(self, message):
        self.log_box.appendPlainText(message)

    def get_access_token(self):
        script = """
        var token = localStorage.getItem('access_token');
        console.log('ACCESS TOKEN:', token);
        """
        self.browser.page().runJavaScript(script)

    def apply_token(self, token):
        if not token or token == 'null':
            self.append_log('Could not read a Mixamo access token. Log in inside the app first.')
            return
        HEADERS["Authorization"] = f"Bearer {token}"
        self.run_downloader()

    def run_downloader(self):
        self.thread = QtCore.QThread()

        mode = self.get_mode()
        query = self.le_query.text().strip()
        path = self.le_path.text().strip()
        prefer_in_place = self.cb_in_place.isChecked()

        self.worker = MixamoDownloader(path, mode, query, prefer_in_place)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(lambda: self.stop_btn.setEnabled(True))
        self.thread.started.connect(lambda: self.get_btn.setEnabled(False))

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self.stop_btn.setEnabled(False))
        self.thread.finished.connect(lambda: self.get_btn.setEnabled(True))

        self.worker.total_tasks.connect(self.set_progress_bar)
        self.worker.current_task.connect(self.update_progress_bar)
        self.worker.log.connect(self.append_log)

        self.append_log(
            f"Starting {mode} download"
            + (" with native In Place preference." if prefer_in_place else ".")
        )
        self.thread.start()

    def set_progress_bar(self, total_tasks):
        self.progress_bar.reset()
        self.progress_bar.setRange(0, total_tasks)

    def update_progress_bar(self, step):
        self.progress_bar.setValue(step)

    def stop_download(self):
        if hasattr(self, 'worker'):
            self.worker.stop = True
            self.append_log('Stopping after the current request…')

    def set_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select the output folder')
        if path:
            self.le_path.setText(path)

    def get_mode(self):
        if self.rb_all.isChecked():
            return "all"
        if self.rb_query.isChecked():
            return "query"
        return "tpose"
