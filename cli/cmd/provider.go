package cmd

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/color"
	"github.com/krnova/vashishtha/cli/internal/config"
)

func newProviderCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "provider [name]",
		Short: "Show or switch LLM provider",
		ValidArgsFunction: func(cmd *cobra.Command, args []string, toComplete string) ([]string, cobra.ShellCompDirective) {
			return config.Providers(vashDir), cobra.ShellCompDirectiveNoFileComp
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, err := config.Load(vashDir)
			if err != nil {
				fmt.Printf("  %s✗ config not found%s\n", color.Red, color.Reset)
				return nil
			}

			if len(args) == 0 {
				// Show current
				model := cfg.API.Models[cfg.API.Provider]
				providers := make([]string, 0, len(cfg.API.Models))
				for k := range cfg.API.Models {
					providers = append(providers, k)
				}
				fmt.Printf("  %scurrent%s    %s%s%s  %s(%s)%s\n",
					color.Dim, color.Reset,
					color.Gold, cfg.API.Provider, color.Reset,
					color.Dim, model, color.Reset,
				)
				fmt.Printf("  %savailable%s  %s\n",
					color.Dim, color.Reset,
					strings.Join(providers, "  ·  "),
				)
				fmt.Printf("  %susage: va provider <name>%s\n", color.Dim, color.Reset)
				return nil
			}

			name := args[0]
			if _, ok := cfg.API.Models[name]; !ok {
				providers := make([]string, 0, len(cfg.API.Models))
				for k := range cfg.API.Models {
					providers = append(providers, k)
				}
				fmt.Printf("  %s✗ unknown provider '%s' — available: %s%s\n",
					color.Red, name, strings.Join(providers, ", "), color.Reset)
				return nil
			}

			cfg.API.Provider = name
			if err := cfg.Save(vashDir); err != nil {
				fmt.Printf("  %s✗ save failed: %v%s\n", color.Red, err, color.Reset)
				return nil
			}

			model := cfg.API.Models[name]
			fmt.Printf("  %s✓%s  provider → %s%s%s  %s(%s)%s\n",
				color.Green, color.Reset,
				color.Gold, name, color.Reset,
				color.Dim, model, color.Reset,
			)
			fmt.Printf("  %srestart to apply:%s  %sva restart%s\n",
				color.Dim, color.Reset, color.Green, color.Reset)
			return nil
		},
	}
	return cmd
}
