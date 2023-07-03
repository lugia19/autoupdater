import locale
import os
import sys
import threading
import subprocess

import googletrans
from PyQt6 import QtWidgets
from dulwich import porcelain
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, QObject

repoURL = 'https://github.com/lugia19/Echo-XI.git'

colors_dict = {
    "primary_color":"#1A1D22",
    "secondary_color":"#282C34",
    "hover_color":"#596273",
    "text_color":"#FFFFFF",
    "toggle_color":"#4a708b",
    "green":"#3a7a3a",
    "yellow":"#7a7a3a",
    "red":"#7a3a3a"
}

translator = googletrans.Translator()

class SignalEmitter(QObject):
    signal = pyqtSignal()

class BoolSignalEmitter(QObject):
    signal = pyqtSignal(bool)
def translate_ui_text(text):
    if text is None or text == "":
        return text

    langCode = locale.getdefaultlocale()[0].split("_")[0]

    counter = 0
    translatedText = None
    while counter < 10:
        try:
            if "en" in langCode.lower():
                translatedText = text
            else:
                translatedText = translator.translate(text, dest=langCode).text
            break
        except TypeError:
            counter += 1
        except Exception:
            print("Timeout error when trying to use google translate. Not going to translate.")
            break

    if translatedText is None:
        print("Failed to get translation. Not translating.")
        translatedText = text
        translatedText = translatedText[0].upper() + translatedText[1:]

    if langCode not in ['ja', 'zh-cn', 'zh-tw']:  # Add more if needed
        translatedText = translatedText[0].upper() + translatedText[1:]

    translatedText = translatedText.strip()

    return translatedText

normalInstallText = translate_ui_text("Installing packages...")
torchInstallText = translate_ui_text("Installing pytorch, this may take a while...")

def get_stylesheet():
    styleSheet = """
    * {
        background-color: {primary_color};
        color: {secondary_color};
    }
    
    QLabel {
        color: {text_color};
    }
    
    QMessageBox {
        background-color: {primary_color};
        color: {text_color};
    }
    
    QProgressBar {
            border: 0px solid {hover_color};
            text-align: center;
            background-color: {secondary_color};
            color: {text_color};
    }
    QProgressBar::chunk {
        background-color: {toggle_color};
    }
    """

    for colorKey, colorValue in colors_dict.items():
        styleSheet = styleSheet.replace("{" + colorKey + "}", colorValue)
    return styleSheet


class DownloadDialog(QtWidgets.QDialog):
    def __init__(self, packages):
        super().__init__()
        self.setWindowTitle(translate_ui_text('Download Progress'))
        self.packages = packages
        self.signalEmitter = SignalEmitter()
        self.signalEmitter.signal.connect(lambda: self.done(0))

        self.boolSignalEmitter = BoolSignalEmitter()
        self.boolSignalEmitter.signal.connect(self.setpytorch)

        self.layout = QtWidgets.QVBoxLayout()
        self.label = QtWidgets.QLabel(translate_ui_text("Installing packages..."))
        self.layout.addWidget(self.label)

        self.progress = QtWidgets.QProgressBar(self)
        self.layout.addWidget(self.progress)

        self.setLayout(self.layout)

        self.download_thread = threading.Thread(target=self.install_packages)

    def install_packages(self):
        total_packages = len(self.packages)
        self.progress.setMaximum(100)

        for i, package in enumerate(self.packages):
            self.boolSignalEmitter.signal.emit("-r" in package)

            if "-r" in package:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', "-r", package.replace("-r","").strip()])
            else:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', package])
            self.update_progress_bar(i + 1, total_packages)

        self.signalEmitter.signal.emit()

    def setpytorch(self, isPytorch:bool):
        newText = torchInstallText if isPytorch else normalInstallText
        if self.label.text() != newText:
            self.label.setText(newText)


    def finish(self):
        self.done(0)

    def update_progress_bar(self, progress_tracker, total_size_in_bytes):
        percent_completed = (progress_tracker / total_size_in_bytes) * 100
        self.progress.setValue(int(percent_completed))

    def exec(self):
        self.download_thread.start()
        super().exec()

    def show(self):
        self.download_thread.start()
        super().show()

def clone_or_pull(gitUrl, targetDirectory):
    if not os.path.exists(targetDirectory):
        porcelain.clone(gitUrl, target=targetDirectory)
    else:
        porcelain.pull(targetDirectory, gitUrl)

def check_and_run_setup(repo_dir):
    setup_file = os.path.join(repo_dir, 'setup.py')
    if os.path.exists(setup_file):
        subprocess.check_call([sys.executable, setup_file])


def check_requirements(repo_dir):
    req_file = os.path.join(repo_dir, 'requirements.txt')
    packages = []
    torch_req_file = os.path.join(repo_dir, 'requirements-torch.txt')
    if os.path.exists(torch_req_file):
        packages.append('-r ' + torch_req_file)

    if os.path.exists(req_file):
        with open(req_file, 'r') as f:
            lines = f.read().splitlines()

        # Strip out comments and whitespace, ignore empty lines
        packages += [line.split('#', 1)[0].strip() for line in lines if line.split('#', 1)[0].strip()]



    return packages

def main():
    app = QApplication([])
    app.setStyleSheet(get_stylesheet())
    repoDir = os.path.basename(repoURL).replace(".git", "")
    clone_or_pull(repoURL,repoDir)
    packages = check_requirements(repoDir)

    if len(packages) > 0:
        dialog = DownloadDialog(packages)
        dialog.exec()

    check_and_run_setup(repoDir)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
