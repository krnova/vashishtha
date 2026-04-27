package cmd

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/color"
)

func newLogsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "logs [start|stop|clear]",
		Short: "Tail agent logs",
		ValidArgs: []string{"start", "stop", "clear"},
		RunE: func(cmd *cobra.Command, args []string) error {
			logFile := dmn.LogFile()
			subCmd := "follow"
			if len(args) > 0 {
				subCmd = args[0]
			}

			logPidFile := filepath.Join(vashDir, ".vashishtha.log.pid")

			switch subCmd {
			case "start":
				if pid := readLogPid(logPidFile); pid > 0 {
					fmt.Printf("  %salready streaming%s  PID %s%d%s\n",
						color.Orange, color.Reset, color.Blue, pid, color.Reset)
					return nil
				}
				tail := exec.Command("tail", "-f", logFile)
				tail.Stdout = os.Stdout
				tail.Stderr = os.Stderr
				if err := tail.Start(); err != nil {
					fmt.Printf("  %s✗ %v%s\n", color.Red, err, color.Reset)
					return nil
				}
				_ = os.WriteFile(logPidFile, []byte(strconv.Itoa(tail.Process.Pid)+"\n"), 0644)
				go tail.Wait()
				fmt.Printf("  %s✓ log stream started%s  PID %s%d%s\n",
					color.Green, color.Reset, color.Blue, tail.Process.Pid, color.Reset)
				fmt.Printf("  %stip: open a second terminal for clean output%s\n", color.Dim, color.Reset)

			case "stop":
				pid := readLogPid(logPidFile)
				if pid <= 0 {
					fmt.Printf("  %sno active log stream%s\n", color.Dim, color.Reset)
					return nil
				}
				proc, err := os.FindProcess(pid)
				if err == nil {
					_ = proc.Signal(syscall.SIGTERM)
				}
				_ = os.Remove(logPidFile)
				fmt.Printf("  %slog stream stopped%s\n", color.Dim, color.Reset)

			case "clear":
				if err := os.WriteFile(logFile, []byte{}, 0644); err != nil {
					fmt.Printf("  %s✗ %v%s\n", color.Red, err, color.Reset)
					return nil
				}
				fmt.Printf("  %slogs cleared%s\n", color.Dim, color.Reset)

			default: // follow
				f, err := os.Open(logFile)
				if err != nil {
					fmt.Printf("  %s✗ log file not found%s\n", color.Red, color.Reset)
					return nil
				}
				defer f.Close()

				_, _ = f.Seek(0, io.SeekEnd)

				sig := make(chan os.Signal, 1)
				signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
				defer signal.Stop(sig)

				buf := make([]byte, 4096)
				ticker := time.NewTicker(100 * time.Millisecond)
				defer ticker.Stop()

				for {
					select {
					case <-sig:
						return nil
					case <-ticker.C:
						n, _ := f.Read(buf)
						if n > 0 {
							os.Stdout.Write(buf[:n])
						}
					}
				}
			}
			return nil
		},
	}
	return cmd
}

func readLogPid(pidFile string) int {
	b, err := os.ReadFile(pidFile)
	if err != nil {
		return 0
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(b)))
	if err != nil {
		return 0
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return 0
	}
	if proc.Signal(syscall.Signal(0)) != nil {
		return 0
	}
	return pid
}
