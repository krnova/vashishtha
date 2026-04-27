package cmd

import (
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"

	"github.com/chzyer/readline"
	"github.com/spf13/cobra"

	"github.com/krnova/vashishtha/cli/internal/api"
	"github.com/krnova/vashishtha/cli/internal/color"
	"github.com/krnova/vashishtha/cli/internal/render"
	"github.com/krnova/vashishtha/cli/internal/state"
)

type queryMode int

const (
	modePlain queryMode = iota
	modeThinking
	modeVerbose
)

func newQueryCmd() *cobra.Command {
	var thinking bool
	var verbose bool

	cmd := &cobra.Command{
		Use:   "query [message]",
		Short: "Query the agent — interactive REPL or single shot",
		RunE: func(cmd *cobra.Command, args []string) error {
			mode := modePlain
			if thinking {
				mode = modeThinking
			} else if verbose {
				mode = modeVerbose
			}

			if !ensureServer() {
				os.Exit(1)
			}

			if len(args) > 0 {
				return runSingleQuery(strings.Join(args, " "), mode)
			}
			return runREPL(mode)
		},
	}

	cmd.Flags().BoolVarP(&thinking, "thinking", "t", false, "Show thinking traces")
	cmd.Flags().BoolVarP(&verbose, "verbose", "v", false, "Verbose output")
	return cmd
}

// ── Single shot ───────────────────────────────────────────────────────────────

func runSingleQuery(msg string, mode queryMode) error {
	startSpinner("thinking")
	resp, err := sendMessage(msg, mode)
	stopSpinner()

	if err != nil {
		fmt.Printf("  %s✗ %v%s\n", color.Red, err, color.Reset)
		return nil
	}

	fmt.Println()
	renderResponse(resp, mode)
	fmt.Println()
	return nil
}

// ── REPL ──────────────────────────────────────────────────────────────────────

func runREPL(mode queryMode) error {
	session := state.GetSession()

	fmt.Printf("\n  %s%svashishtha%s", color.Bold, color.Gold, color.Reset)
	if session != "" {
		fmt.Printf("  %s·  %s%s%s", color.Dim, color.Blue, session, color.Reset)
	}
	fmt.Printf("\n  %sexit · Ctrl+C · new-session%s\n\n", color.Dim, color.Reset)

	rl, err := readline.NewEx(&readline.Config{
		Prompt:                 buildPrompt(),
		HistoryFile:            os.ExpandEnv("$HOME/.vashishtha_history"),
		HistorySearchFold:      true,
		InterruptPrompt:        "",
		EOFPrompt:              "exit",
		DisableAutoSaveHistory: false,
	})
	if err != nil {
		return fmt.Errorf("readline init: %w", err)
	}
	defer rl.Close()

	lastInterrupt := false

	for {
		rl.SetPrompt(buildPrompt())

		line, err := rl.Readline()

		if err == readline.ErrInterrupt {
			if lastInterrupt {
				// Second Ctrl+C — exit
				break
			}
			// First Ctrl+C — hint and wait
			lastInterrupt = true
			fmt.Printf("  %s(Ctrl+C again to exit)%s\n\n", color.Dim, color.Reset)
			continue
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			break
		}

		lastInterrupt = false // reset on any real input
		input := strings.TrimSpace(line)
		if input == "" {
			continue
		}

		switch input {
		case "exit", "quit":
			goto done
		case "clear":
			readline.ClearScreen(rl.Terminal)
			continue
		case "session":
			sid := state.GetSession()
			if sid == "" {
				sid = "none"
			}
			fmt.Printf("  %ssession%s  %s%s%s\n\n", color.Dim, color.Reset, color.Blue, sid, color.Reset)
			continue
		case "new-session":
			state.ClearSession()
			state.ClearStatus()
			fmt.Printf("  %ssession cleared%s\n\n", color.Dim, color.Reset)
			continue
		}

		startSpinner("thinking")

		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, os.Interrupt)

		type result struct {
			resp *api.ChatResponse
			err  error
		}
		resCh := make(chan result, 1)
		go func() {
			r, e := sendMessage(input, mode)
			resCh <- result{r, e}
		}()

		var resp *api.ChatResponse
		var sendErr error
		cancelled := false

		select {
		case res := <-resCh:
			resp, sendErr = res.resp, res.err
		case <-sigCh:
			cancelled = true
		}

		signal.Stop(sigCh)
		stopSpinner()

		if cancelled {
			fmt.Printf("  %scancelled%s\n\n", color.Dim, color.Reset)
			continue
		}

		if sendErr != nil {
			fmt.Printf("  %s✗ %v%s\n\n", color.Red, sendErr, color.Reset)
			continue
		}

		fmt.Println()
		renderResponse(resp, mode)
		fmt.Println()
	}

done:
	fmt.Printf("\n  %sbye.%s\n", color.Dim, color.Reset)
	return nil
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func buildPrompt() string {
	if state.GetStatus() == "confirm" {
		return color.Orange + "  ⚠ confirm ❯" + color.Reset + " "
	}
	return color.Green + "  ❯" + color.Reset + " "
}

func sendMessage(msg string, mode queryMode) (*api.ChatResponse, error) {
	req := api.ChatRequest{
		Message:   msg,
		SessionID: state.GetSession(),
		Thinking:  mode == modeThinking || mode == modeVerbose,
	}

	if state.GetStatus() == "confirm" {
		req.Confirming = true
	}

	resp, err := client.Chat(req)
	if err != nil {
		return nil, err
	}

	if resp.SessionID != "" {
		state.SaveSession(resp.SessionID)
	}
	if resp.Status == "confirm" {
		state.SaveStatus("confirm")
	} else {
		state.ClearStatus()
	}

	return resp, nil
}

func renderResponse(resp *api.ChatResponse, mode queryMode) {
	switch mode {
	case modeThinking:
		render.Thinking(resp)
	case modeVerbose:
		render.Verbose(resp)
	default:
		render.Plain(resp)
	}
}


