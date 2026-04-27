package cmd

import (
	"fmt"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/color"
	"github.com/krnova/vashishtha/cli/internal/state"
)

func newSessionCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "session",
		Short: "Show current session ID",
		RunE: func(cmd *cobra.Command, args []string) error {
			sid := state.GetSession()
			if sid == "" {
				fmt.Printf("  %sno active session%s\n", color.Dim, color.Reset)
			} else {
				fmt.Printf("  %ssession%s  %s%s%s\n",
					color.Dim, color.Reset, color.Blue, sid, color.Reset)
			}
			return nil
		},
	}
}

func newNewSessionCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "new-session",
		Short: "Clear current session",
		RunE: func(cmd *cobra.Command, args []string) error {
			state.ClearSession()
			state.ClearStatus()
			fmt.Printf("  %ssession cleared%s\n", color.Dim, color.Reset)
			return nil
		},
	}
}
