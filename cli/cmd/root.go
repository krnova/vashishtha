package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/api"
	"github.com/krnova/vashishtha/cli/internal/daemon"
	"github.com/krnova/vashishtha/cli/internal/state"
)

const repoURL = "https://github.com/krnova/vashishtha"

var (
	vashDir string
	client  *api.Client
	dmn     *daemon.Daemon
)

var rootCmd = &cobra.Command{
	Use:   "va",
	Short: "Vashishtha — sovereign personal agent",
	Long:  "",
	// No Run — bare va shows help
	RunE: func(cmd *cobra.Command, args []string) error {
		return cmd.Help()
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func init() {
	home, _ := os.UserHomeDir()
	vashDir = filepath.Join(home, "vashishtha")

	state.Init(vashDir)
	client = api.New(api.DefaultURL)
	dmn    = daemon.New(vashDir)

	rootCmd.AddCommand(
		newRunCmd(),
		newStopCmd(),
		newRestartCmd(),
		newStatusCmd(),
		newQueryCmd(),
		newProviderCmd(),
		newUpdateCmd(),
		newLogsCmd(),
		newSessionCmd(),
		newNewSessionCmd(),
		newInstallCmd(),
	)

	// Completions — cobra built-in, all shells free
	// cobra auto-adds completion subcommand
}

// ── Shared helpers ────────────────────────────────────────────────────────────

func ensureServer() bool {
	if client.Ping() {
		return true
	}
	fmt.Printf("  \033[38;5;208magent not running\033[0m  start it? [y/N] ")
	var ans string
	fmt.Scanln(&ans)
	if ans != "y" && ans != "Y" {
		fmt.Printf("  \033[2mexiting\033[0m\n")
		return false
	}
	return startDaemon()
}

func startDaemon() bool {
	startSpinner("starting")

	pid, err := dmn.Start()
	if err != nil {
		stopSpinner()
		fmt.Printf("  \033[38;5;196m✗ failed to start: %v\033[0m\n", err)
		return false
	}

	ok := dmn.WaitReady(client.Ping, 20, 500*ms)
	stopSpinner()

	if ok {
		fmt.Printf("  \033[38;5;82m✓ running\033[0m  PID \033[38;5;75m%d\033[0m\n", pid)
		return true
	}
	fmt.Printf("  \033[38;5;196m✗ server didn't respond — check: va logs\033[0m\n")
	return false
}
