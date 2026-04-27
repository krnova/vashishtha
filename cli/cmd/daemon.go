package cmd

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"
)

var ms = time.Millisecond

func newRunCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "run",
		Short: "Start agent daemon",
		RunE: func(cmd *cobra.Command, args []string) error {
			if dmn.IsRunning() {
				pid, _ := dmn.PID()
				fmt.Printf("  \033[38;5;208malready running\033[0m  PID \033[38;5;75m%d\033[0m\n", pid)
				return nil
			}
			startDaemon()
			return nil
		},
	}
}

func newStopCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "stop",
		Short: "Stop agent daemon",
		RunE: func(cmd *cobra.Command, args []string) error {
			if !dmn.IsRunning() {
				fmt.Printf("  \033[2mnot running\033[0m\n")
				return nil
			}
			if err := dmn.Stop(); err != nil {
				fmt.Printf("  \033[38;5;196m✗ %v\033[0m\n", err)
				return nil
			}
			fmt.Printf("  \033[2mstopped\033[0m\n")
			return nil
		},
	}
}

func newRestartCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "restart",
		Short: "Restart agent daemon",
		RunE: func(cmd *cobra.Command, args []string) error {
			_ = dmn.Stop()
			time.Sleep(800 * ms)
			startDaemon()
			return nil
		},
	}
}

func newStatusCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show daemon status",
		RunE: func(cmd *cobra.Command, args []string) error {
			if dmn.IsRunning() {
				pid, _ := dmn.PID()
				fmt.Printf("  \033[38;5;82m●  running\033[0m  PID \033[38;5;75m%d\033[0m\n", pid)
				if h, err := client.Health(); err == nil {
					fmt.Printf("  \033[2mmodel\033[0m     %s\n", h.Model)
					fmt.Printf("  \033[2msessions\033[0m  %d\n", h.ActiveSessions)
				}
			} else {
				fmt.Printf("  \033[38;5;196m●  not running\033[0m\n")
			}
			return nil
		},
	}
}
