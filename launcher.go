package main

import (
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

var pythonBinaryPath string

func findPython(path string, info os.FileInfo, err error) error {
	if err != nil {
		return err
	}

	if info.IsDir() {
		return nil
	}

	base := filepath.Base(path)
	if (runtime.GOOS == "windows" && strings.EqualFold(base, "python.exe")) || base == "python" {
		pythonBinaryPath = path
		return filepath.SkipDir
	}

	return nil
}

func main() {
	pythonScript := "install.py"

	err := filepath.Walk(".", findPython)
	if err != nil {
		log.Fatalf("Error walking the path: %v", err)
	}

	absPythonScriptPath, err := filepath.Abs(pythonScript)
	if err != nil {
		log.Fatalf("Cannot resolve absolute path for python script: %s", err)
	}

	if pythonBinaryPath == "" {
		log.Fatalf("Python binary not found")
	}

	cmd := exec.Command(pythonBinaryPath, absPythonScriptPath)

	err = cmd.Start()
	if err != nil {
		log.Fatal(err)
	}
}
