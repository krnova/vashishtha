package cmd

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/color"
)

func newInstallCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "install",
		Short: "Run the installer",
		RunE: func(cmd *cobra.Command, args []string) error {
			script := vashDir + "/install.sh"
			if _, err := os.Stat(script); err != nil {
				fmt.Printf("  %s✗ install.sh not found at %s%s\n", color.Red, script, color.Reset)
				return nil
			}
			sh := exec.Command("bash", script)
			sh.Stdout = os.Stdout
			sh.Stderr = os.Stderr
			sh.Stdin  = os.Stdin
			return sh.Run()
		},
	}
}
