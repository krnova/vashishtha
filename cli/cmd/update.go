package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/color"
)

func newUpdateCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "update",
		Short: "Pull latest from git and rebuild",
		RunE: func(cmd *cobra.Command, args []string) error {
			// git required
			if _, err := exec.LookPath("git"); err != nil {
				fmt.Printf("  %s✗ git not found%s\n", color.Red, color.Reset)
				return nil
			}

			fmt.Printf("  %sfetching%s  %s%s%s\n\n", color.Dim, color.Reset, color.Blue, repoURL, color.Reset)

			// Get current HEAD
			before := gitHead()

			// git pull
			pull := exec.Command("git", "pull", "origin", "main")
			pull.Dir    = vashDir
			pull.Stdout = os.Stdout
			pull.Stderr = os.Stderr
			if err := pull.Run(); err != nil {
				fmt.Printf("\n  %s✗ pull failed%s\n", color.Red, color.Reset)
				return nil
			}

			after := gitHead()
			if before == after {
				fmt.Printf("\n  %salready up to date%s\n", color.Dim, color.Reset)
				return nil
			}

			log := gitLog()
			fmt.Printf("\n  %s✓ updated%s  %s%s%s\n\n",
				color.Green, color.Reset, color.Dim, log, color.Reset)

			// Rebuild binary
			fmt.Printf("  rebuilding binary...\n")
			cliDir := vashDir + "/cli"
			outBin := os.ExpandEnv("$PREFIX/bin/va")

			build := exec.Command("go", "build",
				"-ldflags=-s -w",
				"-o", outBin,
				".",
			)
			build.Dir    = cliDir
			build.Stdout = os.Stdout
			build.Stderr = os.Stderr

			if err := build.Run(); err != nil {
				fmt.Printf("  %s✗ build failed — binary unchanged%s\n", color.Red, color.Reset)
				fmt.Printf("  %smanual rebuild: cd %s && go build -o $PREFIX/bin/va .%s\n",
					color.Dim, cliDir, color.Reset)
				return nil
			}

			fmt.Printf("  %s✓ binary updated%s  %s%s%s\n\n",
				color.Green, color.Reset, color.Dim, outBin, color.Reset)

			// Re-run installer?
			fmt.Printf("  re-run installer? %s(recommended)%s [y/N] ", color.Dim, color.Reset)
			var ans string
			fmt.Scanln(&ans)
			if strings.ToLower(ans) == "y" {
				sh := exec.Command("bash", vashDir+"/install.sh")
				sh.Stdout = os.Stdout
				sh.Stderr = os.Stderr
				_ = sh.Run()
			}

			fmt.Printf("\n  %sapply changes:%s  %sva restart%s\n",
				color.Dim, color.Reset, color.Green, color.Reset)
			return nil
		},
	}
}

func gitHead() string {
	out, err := exec.Command("git", "-C", vashDir, "rev-parse", "HEAD").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func gitLog() string {
	out, err := exec.Command("git", "-C", vashDir, "log", "--oneline", "-1").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}
