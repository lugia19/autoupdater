package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
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

		// Write to a log file
		f, err := os.OpenFile("error.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
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

	data, err := os.ReadFile("repo.json")
	checkError("Error reading repo.json", err)

	err = json.Unmarshal(data, &config)
	checkError("Error parsing repo.json", err)

	//Check if venv already exists...
	_, err = os.Stat(config.VenvFolder)
	if os.IsNotExist(err) {
		//Venv does not exist, create it.
		err = filepath.Walk("base-venv", findPython)
		checkError("Error walking the path", err)

		absBaseVenvPythonBinaryPath, err := filepath.Abs(pythonBinaryPath)
		checkError("Cannot resolve absolute path for python binary", err)

		fmt.Println("Base-venv Python Binary Path: ", absBaseVenvPythonBinaryPath) // Print pythonBinaryPath

		newVenvCommand := exec.Command(absBaseVenvPythonBinaryPath, "-m", "venv", config.VenvFolder)
		err = newVenvCommand.Run()
		checkError("Failed to create new venv", err)
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
	err = cmd.Run()

	if err != nil {
		exitError, ok := err.(*exec.ExitError) // type assert to *exec.ExitError
		if ok {
			exitCode := exitError.ExitCode()
			if exitCode == 99 {
				//Program just installed the prerequisites. Run it again.
				cmd = exec.Command(absNewVenvPythonBinaryPath, absPythonScriptPath)
				err = cmd.Run()
			} else {
				checkError("install.py script error", err)
			}
		} else {
			checkError("install.py script error", err)
		}
	}

	checkError("install.py script error", err)

}
