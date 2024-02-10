# This Python file uses the following encoding: utf-8
import sys
from PySide6.QtCore import QRunnable, QThreadPool, QDirIterator
from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QFileDialog, QMessageBox
import os
import time
from PIL import Image as PILImage

class ImageFinder(QRunnable):
    def __init__(self, directory_path, output_stack):
        super().__init__()
        self.setAutoDelete(True)
        self.directory_path = directory_path
        self.output_stack = output_stack

    def run(self):
        it = QDirIterator(self.directory_path, ['*.png'])
        while it.hasNext():
            img_path = it.next()
            self.output_stack.append(img_path)

# Takes layer image's path, list of background images and folder name where to save the resulting images
class ImageGluer(QRunnable):
    def __init__(self, image_path, bg_images, temp_folder):
        super().__init__()
        self.setAutoDelete(True)
        self.img_path = image_path
        self.bg_images = bg_images
        self.temp_folder = temp_folder

    def run(self):
        for bg_path in self.bg_images:
            if os.name == "posix":
                new_image_path = os.path.join(self.temp_folder, os.path.split(bg_path)[1].split('.')[0] + "_" + os.path.split(self.img_path)[1].split('.')[0] + ".png")
            else:
                new_image_path = self.temp_folder + '/' + os.path.split(bg_path)[1].split('.')[0] + "_" + os.path.split(self.img_path)[1].split('.')[0] + ".png"
                # Check if img opened successfully
                with(PILImage.open(bg_path)) as bg_img:
                    with(PILImage.open(self.img_path)) as img:
                        new_img = PILImage.alpha_composite(bg_img, img)
                        new_img.save(new_image_path)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Picture Gluer")
        self.setFixedWidth(480)
        self.setFixedHeight(320)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.workspace_layout = QVBoxLayout()
        self.window_layout = QVBoxLayout()

        self.bg_image_dir_layout = QHBoxLayout()
        self.dest_selection_layout = QHBoxLayout()
        self.layer_image_dir_layout = QHBoxLayout()
        self.control_layout = QHBoxLayout()

        self.label_bg_section = QLabel("Select folder with background images")
        self.bg_directory_path = QLineEdit()
        self.bg_directory_path.textChanged.connect(lambda: self.btnRun.setEnabled(True))
        self.bg_directory_path.setReadOnly(True)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(lambda: self.select_folder(self.bg_directory_path, "Select background images location"))
        self.bg_image_dir_layout.addWidget(self.bg_directory_path)
        self.bg_image_dir_layout.addWidget(self.btn_browse)

        self.label_destination_section = QLabel("Select folder where to save images")
        self.dest_folder = QLineEdit()
        self.dest_folder.setReadOnly(True)
        self.btn_select_dest = QPushButton("Browse...")
        self.btn_select_dest.clicked.connect(lambda: self.select_folder(self.dest_folder, "Select a folder for result"))
        self.dest_selection_layout.addWidget(self.dest_folder)
        self.dest_selection_layout.addWidget(self.btn_select_dest)

        self.btn_add_layer = QPushButton("Add image layer")
        self.btn_add_layer.clicked.connect(self.add_layer_path_selection)

        self.btnClose = QPushButton("Close")
        self.btnRun = QPushButton("Run")
        self.btnRun.setEnabled(False);
        self.btnClose.clicked.connect(app.exit)
        self.btnRun.clicked.connect(self.run_gluer)
        self.control_layout.addWidget(self.btnClose)
        self.control_layout.addWidget(self.btnRun)

        self.workspace_layout.addWidget(self.label_bg_section)
        self.workspace_layout.addLayout(self.bg_image_dir_layout)
        self.workspace_layout.addStretch(1)
        self.workspace_layout.addWidget(self.btn_add_layer)
        self.workspace_layout.addWidget(self.label_destination_section)
        self.workspace_layout.addLayout(self.dest_selection_layout)

        self.central_widget.setLayout(self.window_layout)
        self.central_widget.layout().addLayout(self.workspace_layout)
        self.central_widget.layout().addLayout(self.control_layout)

        self.paths_of_layer_images = []
        self.bg_images = []
        self.list_layer_images = []

    def add_layer_path_selection(self):
        dir_path = QLineEdit()
        dir_path.setReadOnly(True)
        btn_browse = QPushButton("Browse...")
        btn_clear = QPushButton("Clear")
        btn_browse.clicked.connect(lambda: self.select_folder(dir_path, "Select layer images location"))
        btn_clear.clicked.connect(dir_path.clear)
        layout = QHBoxLayout()
        layout.addWidget(dir_path)
        layout.addWidget(btn_browse)
        layout.addWidget(btn_clear)
        self.workspace_layout.insertLayout(self.workspace_layout.indexOf(self.btn_add_layer), layout)
        self.paths_of_layer_images.append(dir_path)
        # Currently processing up to 10 layers due to UI ugly resizing
        if len(self.paths_of_layer_images) >= 10:
            self.btn_add_layer.setEnabled(False)

    def select_folder(self, line_edit, text="Select a folder"):
        folder_path = QFileDialog.getExistingDirectory(self, text, '/')
        if folder_path:
            line_edit.setText(folder_path)

    def run_gluer(self):
        thread_prepare_bg = ImageFinder(self.bg_directory_path.text(), self.bg_images)
        QThreadPool.globalInstance().start(thread_prepare_bg)
        for layer_path in self.paths_of_layer_images:
            if not layer_path.text():
                continue
            layer_images = []
            self.list_layer_images.append(layer_images)
            thread_prepare_images = ImageFinder(layer_path.text(), layer_images)
            QThreadPool.globalInstance().start(thread_prepare_images)
        QThreadPool.globalInstance().waitForDone()
        self.glue_images()

    def glue_images(self):
        time_start = time.perf_counter()
        temp_folder = self.create_temp_folder()
        for layer in self.list_layer_images:
            for img_path in layer:
                glue_img_layer = ImageGluer(img_path, self.bg_images, temp_folder)
                QThreadPool.globalInstance().start(glue_img_layer)
            QThreadPool.globalInstance().waitForDone()
            self.remove_temp_files(temp_folder)
        self.bg_images = []
        self.list_layer_images = []
        os.rmdir(temp_folder)
        time_end = time.perf_counter()
        message = QMessageBox()
        task_time_str = str(time_end - time_start)
        message.setText("Success! Processing time: " + task_time_str)
        message.setModal(True)
        message.show()

    def remove_temp_files(self, temp_folder):
        it = QDirIterator(self.dest_folder.text(), ['*.png'])
        while it.hasNext():
            name = it.next()
            print("Remove: " + name)
            os.remove(name)
        it = QDirIterator(temp_folder, ['*.png'])
        while it.hasNext():
            file_path = it.next()
            file_name = os.path.split(file_path)[1]
            new_path = ""
            if os.name == "posix":
                new_path = os.path.join(self.dest_folder.text(), file_name)
            else:
                new_path = self.dest_folder.text() + '/' + file_name
            os.replace(file_path, new_path)
        it = QDirIterator(self.dest_folder.text(), ['*.png'])
        self.bg_images = []
        while it.hasNext():
            self.bg_images.append(it.next())


    def create_temp_folder(self):
        os.chdir(self.dest_folder.text())
        folder_name = "temp"
        os.mkdir(folder_name)
        if os.name == "posix":
            return os.path.join(self.dest_folder.text(), folder_name)
        else:
            return self.dest_folder.text() + '/' + folder_name


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
