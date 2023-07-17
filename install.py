import io
import json
import locale
import os
import sys
import threading
import subprocess
import time

baserequirements = [
    "requests",
    "googletrans~=4.0.0rc1",
    "PyQt6~=6.5.1",
    "dulwich~=0.21.5"
]

subprocess_flags = 0
if os.name == 'nt':  # Check if the operating system is Windows
    subprocess_flags = subprocess.CREATE_NO_WINDOW  # Prevent the command prompt from appearing on Windows

def install_base_requirements(installDoneEvent:threading.Event):
    print("Thread started...")
    try:
        pipargs = [sys.executable, '-m', 'pip', 'install', '--upgrade']
        pipargs.extend(baserequirements)
        subprocess.check_call(pipargs, creationflags=subprocess_flags)
    except subprocess.CalledProcessError as e:
        print(f"Failed to install packages: {e.output}")
    finally:
        # Close the messagebox when done
        print("Quitting...")
        installDoneEvent.set()

print("Checking prerequisites...")
try:
    import googletrans
    from PyQt6 import QtWidgets, QtCore, QtGui
    import dulwich
    from dulwich import porcelain, client, repo
    import requests
except ImportError:
    #Prerequisite not found, need to install the base requirements
    import tkinter as tk
    from tkinter import messagebox
    import importlib

    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Show a custom message window
    top = tk.Toplevel()
    top.title('Install')
    msg = tk.Message(top, text="Installing prerequisites.\nPlease wait...", padx=20, pady=20)
    msg.pack()

    # Start the installation in a separate thread
    install_done = threading.Event()
    thread = threading.Thread(target=install_base_requirements, args=(install_done,))
    thread.start()

    def check_event():
        if install_done.is_set():
            root.destroy()
        else:
            root.after(100, check_event)


    check_event()  # start checking event

    root.mainloop()
    print("Done - exiting with errorcode 99 to signal the go exe to restart.")
    print("Also, creating the 'installing' file, as I'm gonna go ahead and assume we need to do some cleanup.")
    open("installing", 'w').close()
    exit(99)
print("Prerequisites checked.")
repoData = json.load(open("repo.json"))

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

class SignalEmitter(QtCore.QObject):
    signal = QtCore.pyqtSignal()

class StrSignalEmitter(QtCore.QObject):
    signal = QtCore.pyqtSignal(str)

class BoolSignalEmitter(QtCore.QObject):
    signal = QtCore.pyqtSignal(bool)

class IntSignalEmitter(QtCore.QObject):
    signal = QtCore.pyqtSignal(int)

def translate_ui_text(text):
    if text is None or text == "":
        return text

    if os.name == "nt":
        # windows-specific
        import ctypes
        windll = ctypes.windll.kernel32
        import locale
        langCode = locale.windows_locale[windll.GetUserDefaultUILanguage()]
        if "_" in langCode:
            langCode = langCode.split("_")[0]
    else:
        # macos or linux
        import locale
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

normalInstallText = translate_ui_text("Updating packages")
torchInstallText = translate_ui_text("Updating pytorch, this may take a while...\nNote: The bar not moving is normal.")

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
    
    QPushButton {
        background-color: {secondary_color};
        color: {text_color};
    }
    
    QPushButton:hover {
        background-color: {hover_color};
    }
    """

    for colorKey, colorValue in colors_dict.items():
        styleSheet = styleSheet.replace("{" + colorKey + "}", colorValue)
    return styleSheet

#Yes, a bunch of this code was done with GPT-4's help because I'm lazy like that.
def format_eta(seconds) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{int(hours)}h {int(minutes)}m"
    elif minutes:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

class DownloadThread(QtCore.QThread):
    setProgressBarTotalSignal = QtCore.pyqtSignal(int)
    updateProgressSignal = QtCore.pyqtSignal(int)
    labelTextSignal = QtCore.pyqtSignal(int)
    doneSignal = QtCore.pyqtSignal()

    def __init__(self, url, location):
        super().__init__()
        self.url = url
        self.location = location

    def run(self):
        response = requests.get(self.url, stream=True)
        total_size_in_bytes = response.headers.get('content-length')

        if total_size_in_bytes is None:  # If 'content-length' is not found in headers
            self.setProgressBarTotalSignal.emit(-1)  # Set progress bar to indeterminate state
        else:
            total_size_in_bytes = int(total_size_in_bytes)
            self.setProgressBarTotalSignal.emit(total_size_in_bytes)

        block_size = 1024 * 16
        print(-1)
        try:
            response.raise_for_status()
            file = open(self.location, 'wb')

            start_time = time.time()
            total_data_received = 0
            last_emit_time = start_time  # Initialize last_emit_time to start_time
            data_received_since_last_emit = 0

            for data in response.iter_content(block_size):
                total_data_received += len(data)
                data_received_since_last_emit += len(data)

                file.write(data)
                if total_size_in_bytes is not None:  # Only update if 'content-length' was found
                    current_time = time.time()
                    if current_time - last_emit_time >= 1:
                        elapsed_time_since_last_emit = current_time - last_emit_time
                        download_speed = data_received_since_last_emit / elapsed_time_since_last_emit
                        print(f"Download speed: {download_speed / 1024 / 1024:.2f} MBps")

                        # Calculate ETA
                        remaining_data = total_size_in_bytes - total_data_received
                        if download_speed != 0:  # Avoid division by zero
                            eta = int(remaining_data / download_speed)
                            print(f"ETA: {eta} seconds")
                            self.labelTextSignal.emit(eta)
                        self.updateProgressSignal.emit(int((total_data_received / total_size_in_bytes) * 100))
                        # Reset tracking variables for the next X seconds
                        last_emit_time = current_time  # Update last_emit_time
                        data_received_since_last_emit = 0  # Reset data_received_since_last_emit

            file.flush()
            file.close()

        except requests.exceptions.RequestException as e:
            print(e)
            if os.path.exists(self.location):
                os.remove(self.location)
            raise

        self.doneSignal.emit()


class DownloadDialog(QtWidgets.QDialog):
    def __init__(self, baseLabelText, url, location):
        super().__init__()
        self.setWindowTitle(translate_ui_text('Download'))
        self.previous_percent_completed = -1

        self.download_thread = DownloadThread(url, location)

        self.download_thread.setProgressBarTotalSignal.connect(self.set_progress_bar)
        self.download_thread.doneSignal.connect(lambda: self.done(0))
        self.download_thread.labelTextSignal.connect(self.set_eta)
        self.download_thread.updateProgressSignal.connect(self.update_progress_bar)

        self.layout = QtWidgets.QVBoxLayout()
        self.baseLabelText = translate_ui_text(baseLabelText)
        self.label = QtWidgets.QLabel(self.baseLabelText)

        self.layout.addWidget(self.label)
        self.progress = QtWidgets.QProgressBar(self)
        self.layout.addWidget(self.progress)
        self.setLayout(self.layout)

    def set_eta(self, ETASeconds):
        self.label.setText(f"{self.baseLabelText} ({format_eta(ETASeconds)})")

    def set_progress_bar(self, amount):
        if amount == -1:
            self.progress.setRange(0, 0)
        else:
            self.progress.setMaximum(100)

    def update_progress_bar(self, percent_completed):
        if percent_completed != self.previous_percent_completed:
            self.progress.setValue(percent_completed)
            self.previous_percent_completed = percent_completed

    def showEvent(self, event):
        super().showEvent(event)
        self.download_thread.start()

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self,
            translate_ui_text('Confirmation'),
            translate_ui_text('Are you sure you want to quit?'),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.download_thread.terminate()
            event.accept()
            app.exit(0)
            sys.exit(0)
        else:
            event.ignore()

class PackageThread(QtCore.QThread):
    setLabelTextSignal = QtCore.pyqtSignal(str)
    setProgressMaxSignal = QtCore.pyqtSignal(int)
    updateProgressSignal = QtCore.pyqtSignal(int)
    doneSignal = QtCore.pyqtSignal()
    showErrorSignal = QtCore.pyqtSignal(str)
    downloadSignal = QtCore.pyqtSignal(str, str)
    def __init__(self, packages):
        super().__init__()
        self.packages = packages
        self.downloadDone = threading.Event()
    def run(self):
        total_packages = len(self.packages)

        for i, package in enumerate(self.packages):
            package: str
            try:
                # This is all pytorch-specific stuff.
                if package.startswith("-r"):
                    print(f"Installing {package}")
                    self.setLabelTextSignal.emit(torchInstallText)
                    # process = subprocess.Popen([sys.executable, '-m', 'pip', 'install', '--upgrade', "elevenlabslib"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    #                           creationflags=subprocess_flags)
                    process = subprocess.Popen([sys.executable, '-m', 'pip', 'install', '--no-cache-dir','--upgrade', "-r", package[2:].strip()], stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT,
                                               creationflags=subprocess_flags)
                    url = None
                    isCollecting = False
                    for line in iter(process.stdout.readline, b''):  # Reads the output line by line.
                        line = line.decode('utf-8').strip().lower()  # Decodes the bytes to string and removes newline character at the end.
                        print(line)  # Logs the line.
                        if "collecting torch" in line:
                            # It's collecting torch
                            isCollecting = True
                        if isCollecting and "using cached" in line:
                            # It's using the cached one. No need to do anything then.
                            isCollecting = False

                        if isCollecting and "downloading" in line:
                            url = line[len("downloading"):]
                            url = url[:url.rindex("(")].strip()
                            print("Installing it so we add it to the cache again...")
                            # Pip has selected the wheel to download. Kill it.
                            process.stdout.close()  # Closes the stdout pipe.
                            process.terminate()
                            process.wait()
                            break

                    if url is not None:
                        print(f"URL found: {url}")
                        import urllib.parse
                        filename = urllib.parse.unquote(url[url.rindex("/") + 1:])
                        print(f"Filename: {filename}")

                        if os.path.exists(filename):
                            print("Deleting file...")
                            os.remove(filename)

                        if self.downloadDone.is_set():
                            self.downloadDone.clear()

                        self.downloadSignal.emit(url, filename)
                        self.downloadDone.wait()

                        if not os.path.exists(filename):
                            self.showErrorSignal.emit(f"An error occurred while installing package '{package}', we were unable to download the corresponding wheel.")
                            return  # Something went wrong. Throw an error and exit.
                        # Done downloading it - install it
                        completed_process = subprocess.run([sys.executable, '-m', 'pip', 'install', filename], check=True, text=True, capture_output=True, creationflags=subprocess_flags)
                        print(completed_process.stdout)

                        # Remove the file
                        os.remove(filename)
                        # Now we re-install the file.
                        completed_process = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', "-r", package[2:].strip()], check=True, text=True, capture_output=True,
                                                           creationflags=subprocess_flags)
                        print(completed_process.stdout)
                        print("HUH")
                    else:
                        print("We used the cached one or it was already installed. Just continue.")
                    # subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', "-r", package[2:].strip()], check=True, text=True, capture_output=True, creationflags=subprocess_flags)
                else:
                    index = min([package.find(char) for char in ['=', '~', '>'] if package.find(char) != -1], default=-1)
                    packageName = package if index == -1 else package[:index]
                    print(f"Installing {packageName}")
                    self.setLabelTextSignal.emit(f"{normalInstallText} ({packageName})")

                    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', package], check=True, text=True, capture_output=True, creationflags=subprocess_flags)
                print(f"Current progress: {int((i + 1) / total_packages * 100)}%")
                self.updateProgressSignal.emit(int((i + 1) / total_packages * 100))
            except subprocess.CalledProcessError as e:
                self.showErrorSignal.emit(f"An error occurred while installing package '{package}':\n{e.stderr}")
                return

        self.doneSignal.emit()

class PackageDownloadDialog(QtWidgets.QDialog):
    def __init__(self, packages):
        super().__init__()
        self.setWindowTitle(translate_ui_text('Download Progress'))
        self.packages = packages

        self.previous_percent_completed = -1

        self.layout = QtWidgets.QVBoxLayout()
        self.label = QtWidgets.QLabel(normalInstallText)
        self.layout.addWidget(self.label)

        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setMaximum(100)

        self.layout.addWidget(self.progress)

        self.setLayout(self.layout)

        self.packageThread = PackageThread(packages)
        self.packageThread.doneSignal.connect(lambda: self.done(0))
        self.packageThread.setLabelTextSignal.connect(self.setText)
        self.packageThread.updateProgressSignal.connect(self.update_progress_bar)
        self.packageThread.showErrorSignal.connect(self.showErrorAndExit)
        self.packageThread.downloadSignal.connect(self.downloadFile)

    def downloadFile(self, url, location):
        DownloadDialog("Downloading PyTorch", url, location).exec()
        self.packageThread.downloadDone.set()

    def showErrorAndExit(self, error):
        QtWidgets.QMessageBox.critical(self, 'Error', error)
        sys.exit(1)

    def showEvent(self, event):
        super().showEvent(event)
        self.packageThread.start()

    def setText(self, newText:str):
        if self.label.text() != newText:
            self.label.setText(newText)


    def finish(self):
        self.done(0)

    def update_progress_bar(self, percent_completed):
        if percent_completed != self.previous_percent_completed:
            self.progress.setValue(percent_completed)
            self.previous_percent_completed = percent_completed

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self,
            translate_ui_text('Confirmation'),
            translate_ui_text('Are you sure you want to quit?'),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.packageThread.terminate()
            event.accept()
            app.exit(0)
            sys.exit(0)
        else:
            event.ignore()

def clone_or_pull(gitUrl, targetDirectory):
    if not os.path.exists(targetDirectory):
        porcelain.clone(gitUrl, target=targetDirectory)
    else:
        porcelain.pull(targetDirectory, gitUrl)

def run_startup(repo_dir, script):
    if os.path.exists(os.path.join(repo_dir, script)):
        os.chdir(repo_dir)
        subprocess.check_call([sys.executable, script], creationflags=subprocess_flags)


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


def check_if_latest(repo_path, remote_url) -> bool:
    # Open the local repository
    gitRepo = dulwich.repo.Repo(repo_path)

    # Get the current commit
    head = gitRepo[b"HEAD"]

    # Open the remote repository
    gitClient, path = client.get_transport_and_path(remote_url)
    remote_refs = gitClient.get_refs(path)

    # Check if current commit is the latest one
    return head.id == remote_refs[b"HEAD"]

app = QtWidgets.QApplication([])
def main():
    if "icon" in repoData:
        app.setWindowIcon(QtGui.QIcon(repoData["icon"]))
    app.setStyleSheet(get_stylesheet())
    repoURL = repoData["repo_url"]
    repoDir = repoData["repo_dir"]
    startupScript = repoData["startup_script"]

    #If it's missing or not the latest commit anymore, do a pull and make sure the requirements haven't changed.
    #Also if it was previously installing and was interrupted partway through.
    if os.path.exists("installing") or not os.path.exists(repoDir) or not check_if_latest(repoDir, repoURL):
        open("installing", 'w').close()
        messageBox = QtWidgets.QMessageBox()
        messageBox.setWindowTitle(translate_ui_text("Update"))
        messageBox.setText(translate_ui_text("Updating Github repository..."))
        messageBox.setStandardButtons(QtWidgets.QMessageBox.StandardButton.NoButton)
        signalEmitter = SignalEmitter()
        signalEmitter.signal.connect(lambda: messageBox.done(0))
        def thread_func():
            clone_or_pull(repoURL, repoDir)
            signalEmitter.signal.emit()
        pullThread = threading.Thread(target=thread_func)
        pullThread.start()
        QtCore.QTimer.singleShot(1, lambda: (messageBox.activateWindow(), messageBox.raise_()))
        messageBox.show()
        app.exec()
        packages = check_requirements(repoDir)

        if len(packages) > 0:
            dialog = PackageDownloadDialog(packages)
            dialog.show()
            app.exec()
        os.remove("installing")


    run_startup(repoDir, startupScript)
    app.exit(0)
    sys.exit(0)

if __name__ == "__main__":
    print("Starting main...")
    if os.name == "nt":
        import ctypes
        myappid = u'lugia19.installer'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    main()
