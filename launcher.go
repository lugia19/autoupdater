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
)

var pythonBinaryPath string

type Config struct {
	UsePythonW bool `json:"use_pythonw"`
}

func findPython(path string, info os.FileInfo, err error) error {
	if err != nil {
		return err
	}

	if info.IsDir() {
		return nil
	}

	base := filepath.Base(path)
	if runtime.GOOS == "windows" {
		data, err := os.ReadFile("repo.json")
		if err != nil {
			log.Fatalf("Error reading repo.json: %v", err)
		}

		var config Config
		err = json.Unmarshal(data, &config)
		if err != nil {
			log.Fatalf("Error parsing repo.json: %v", err)
		}

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

func main() {
	fmt.Println("Started!") // Here's your print statement.

	pythonScript := "install.py"

	err := filepath.Walk(".", findPython)
	if err != nil {
		log.Fatalf("Error walking the path: %v", err)
	}

	absPythonBinaryPath, err := filepath.Abs(pythonBinaryPath)
	if err != nil {
		log.Fatalf("Cannot resolve absolute path for python binary: %s", err)
	}

	absPythonScriptPath, err := filepath.Abs(pythonScript)
	if err != nil {
		log.Fatalf("Cannot resolve absolute path for python script: %s", err)
	}

	if pythonBinaryPath == "" {
		log.Fatalf("Python binary not found")
	}

	fmt.Println("Python Binary Path: ", absPythonBinaryPath) // Print pythonBinaryPath
	fmt.Println("Python Script Path: ", absPythonScriptPath) // Print absPythonScriptPath

	cmd := exec.Command(absPythonBinaryPath, absPythonScriptPath)

	err = cmd.Run()
	if err != nil {
		log.Fatal(err)
	}
}
