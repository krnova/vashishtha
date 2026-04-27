package state

import (
	"os"
	"path/filepath"
	"strings"
)

var (
	sessionFile string
	statusFile  string
)

func Init(vashDir string) {
	sessionFile = filepath.Join(vashDir, ".last_session")
	statusFile  = filepath.Join(vashDir, ".last_status")
}

func GetSession() string {
	b, err := os.ReadFile(sessionFile)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}

func SaveSession(id string) {
	_ = os.WriteFile(sessionFile, []byte(id+"\n"), 0644)
}

func GetStatus() string {
	b, err := os.ReadFile(statusFile)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}

func SaveStatus(s string) {
	_ = os.WriteFile(statusFile, []byte(s+"\n"), 0644)
}

func ClearStatus() {
	_ = os.Remove(statusFile)
}

func ClearSession() {
	_ = os.Remove(sessionFile)
}
