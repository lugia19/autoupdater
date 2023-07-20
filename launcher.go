package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
)

var pythonBinaryPath string

type Config struct {
	UsePythonW bool   `json:"use_pythonw"`
	VenvFolder string `json:"venv_folder"`
}

var config Config

func findPython(path string, info os.FileInfo, err error) error {
	checkError("walkPath error", err)

	if info.IsDir() {
		return nil
	}

	base := filepath.Base(path)

	if runtime.GOOS == "windows" {
		if config.UsePythonW && strings.EqualFold(base, "pythonw.exe") {
			pythonBinaryPath = path
			return filepath.SkipDir
		} else if !config.UsePythonW && strings.EqualFold(base, "python.exe") {
			pythonBinaryPath = path
			return filepath.SkipDir
		}
	} else if base == "python" {
		pythonBinaryPath = path
		return filepath.SkipDir
	}

	return nil
}

func checkError(message string, err error) {
	if err != nil {
		logMsg := fmt.Sprintf("%s: %v", message, err)

		logDir := "logs"
		if _, err := os.Stat(logDir); os.IsNotExist(err) {
			err := os.MkdirAll(logDir, 0755)
			if err != nil {
				log.Fatal("Cannot create log directory: ", err)
			}
		}

		logFile := filepath.Join(logDir, "launcher-error.log")

		// Write to a log file
		f, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			log.Fatal("Cannot open log file: ", err)
		}
		defer func(f *os.File) {
			err := f.Close()
			if err != nil {
				log.Print("Failed to close file: ", err)
			}
		}(f)

		// Get the current time and format it
		currentTime := time.Now().Format("2006-01-02 15:04:05")

		// Append the timestamp to the log message
		timestampedLogMsg := fmt.Sprintf("%s %s\n", currentTime, logMsg)

		// Write the timestamped log message to the file
		if _, err := f.WriteString(timestampedLogMsg); err != nil {
			log.Println("Cannot write to log file: ", err)
		}

		log.Fatal(logMsg)
	}
}

func main() {
	fmt.Println("Started!")

	//Create a bytes buffer for stderr
	var stderr bytes.Buffer

	data, err := os.ReadFile("repo.json")
	checkError("Error reading repo.json", err)

	err = json.Unmarshal(data, &config)
	checkError("Error parsing repo.json", err)

	//Check if venv already exists...
	_, err = os.Stat(config.VenvFolder)
	if os.IsNotExist(err) {
		//Venv does not exist, create it.
		if runtime.GOOS == "windows" {
			dirs, err := os.ReadDir("WPy")
			checkError("Error reading root directory", err)

			// Find the first subfolder starts with "python-"
			for _, dir := range dirs {
				if dir.IsDir() && strings.HasPrefix(dir.Name(), "python-") {
					subfolderPath := filepath.Join("WPy", dir.Name())
					if config.UsePythonW {
						pythonBinaryPath = filepath.Join(subfolderPath, "pythonw.exe")
					} else {
						pythonBinaryPath = filepath.Join(subfolderPath, "python.exe")
					}
					break
				}
			}
		} else {
			//TBD.
		}

		absBaseVenvPythonBinaryPath, err := filepath.Abs(pythonBinaryPath)
		checkError("Cannot resolve absolute path for python binary", err)

		fmt.Println("Base-venv Python Binary Path: ", absBaseVenvPythonBinaryPath) // Print pythonBinaryPath

		newVenvCommand := exec.Command(absBaseVenvPythonBinaryPath, "-m", "venv", config.VenvFolder)
		newVenvCommand.Stderr = &stderr
		if runtime.GOOS == "windows" {
			newVenvCommand.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
		}
		err = newVenvCommand.Run()
		checkError("Failed to create new venv:"+stderr.String(), err)
	} else if err != nil {
		// error checking directory, report and exit
		checkError("Error checking new venv directory", err)
	} else {
		// directory already exists, skip venv creation
		fmt.Println("New venv directory already exists, skipping venv creation")
	}

	//Get the python exe from the new venv
	err = filepath.Walk(config.VenvFolder, findPython)
	checkError("Error walking the path", err)

	absNewVenvPythonBinaryPath, err := filepath.Abs(pythonBinaryPath)
	checkError("Cannot resolve absolute path for python binary", err)

	//Get the script's location
	pythonScript := "install.py"
	absPythonScriptPath, err := filepath.Abs(pythonScript)
	checkError("Cannot resolve absolute path for python script", err)
	fmt.Println("Python Script Path: ", absPythonScriptPath)
	fmt.Println("Venv Python Binary Path: ", absNewVenvPythonBinaryPath)

	cmd := exec.Command(absNewVenvPythonBinaryPath, absPythonScriptPath)
	cmd.Stderr = &stderr

	if runtime.GOOS == "windows" {
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	}
	err = cmd.Run()
	counter := 0
	if err != nil {
		exitError, ok := err.(*exec.ExitError) // type assert to *exec.ExitError
		if ok {
			for {
				counter += 1
				if exitError.ExitCode() != 99 || !ok || counter > 3 {
					break
				}
				cmd = exec.Command(absNewVenvPythonBinaryPath, absPythonScriptPath)
				if runtime.GOOS == "windows" {
					cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
				}
				err = cmd.Run()
				exitError, ok = err.(*exec.ExitError) // type assert to *exec.ExitError
			}
		} else {
			checkError("install.py script error"+stderr.String(), err)
		}
	}

	checkError("install.py script error"+stderr.String(), err)

}
