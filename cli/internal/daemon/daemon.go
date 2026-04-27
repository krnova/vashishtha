package daemon

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type Daemon struct {
	vashDir string
	logFile string
	pidFile string
}

func New(vashDir string) *Daemon {
	return &Daemon{
		vashDir: vashDir,
		logFile: filepath.Join(vashDir, ".vashishtha.log"),
		pidFile: filepath.Join(vashDir, ".vashishtha.pid"),
	}
}

func (d *Daemon) LogFile() string { return d.logFile }

func (d *Daemon) PID() (int, error) {
	b, err := os.ReadFile(d.pidFile)
	if err != nil {
		return 0, err
	}
	return strconv.Atoi(strings.TrimSpace(string(b)))
}

func (d *Daemon) IsRunning() bool {
	pid, err := d.PID()
	if err != nil {
		return false
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return proc.Signal(syscall.Signal(0)) == nil
}

func (d *Daemon) Start() (int, error) {
	main := filepath.Join(d.vashDir, "main.py")

	log, err := os.OpenFile(d.logFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return 0, fmt.Errorf("open log: %w", err)
	}

	cmd := exec.Command("python3", main)
	cmd.Dir    = d.vashDir
	cmd.Stdout = log
	cmd.Stderr = log
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err := cmd.Start(); err != nil {
		log.Close()
		return 0, fmt.Errorf("start python3: %w", err)
	}

	pid := cmd.Process.Pid
	if err := os.WriteFile(d.pidFile, []byte(strconv.Itoa(pid)+"\n"), 0644); err != nil {
		return pid, fmt.Errorf("write pid: %w", err)
	}

	// Detach
	go cmd.Wait()

	return pid, nil
}

func (d *Daemon) Stop() error {
	pid, err := d.PID()
	if err != nil {
		return nil // not running
	}

	proc, err := os.FindProcess(pid)
	if err != nil {
		_ = os.Remove(d.pidFile)
		return nil
	}

	_ = proc.Signal(syscall.SIGTERM)
	time.Sleep(800 * time.Millisecond)

	if proc.Signal(syscall.Signal(0)) == nil {
		_ = proc.Signal(syscall.SIGKILL)
	}

	_ = os.Remove(d.pidFile)
	return nil
}

func (d *Daemon) WaitReady(ping func() bool, maxTries int, delay time.Duration) bool {
	for i := 0; i < maxTries; i++ {
		if ping() {
			return true
		}
		time.Sleep(delay)
	}
	return false
}
