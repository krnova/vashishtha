package render

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/krnova/vashishtha/cli/internal/api"
	"github.com/krnova/vashishtha/cli/internal/color"
)

const maxLines = 8
const maxThinkLines = 6

// ── Plain ─────────────────────────────────────────────────────────────────────

func Plain(r *api.ChatResponse) {
	if len(r.Actions) > 0 {
		tools := make([]string, len(r.Actions))
		for i, a := range r.Actions {
			tools[i] = a.Tool
		}
		n := len(r.Actions)
		suffix := "step"
		if n > 1 {
			suffix = "steps"
		}
		fmt.Printf("  %s↳ %s  [%d %s]%s\n\n",
			color.Dim, strings.Join(tools, " · "), n, suffix, color.Reset)
	}

	if r.Status == "confirm" {
		fmt.Println(color.Orange + r.Reply + color.Reset)
	} else {
		fmt.Println(color.Gold + r.Reply + color.Reset)
	}
}

// ── Thinking ──────────────────────────────────────────────────────────────────

func Thinking(r *api.ChatResponse) {
	for i, a := range r.Actions {
		if a.Thinking != "" {
			fmt.Printf("  %s[%d] thinking%s\n", color.Dim, i+1, color.Reset)
			for _, ln := range limitLines(a.Thinking, maxThinkLines) {
				fmt.Printf("  %s%s%s\n", color.Cyan, ln, color.Reset)
			}
			fmt.Println()
		}
		fmt.Printf("  %s[%d] %s%s\n\n", color.Dim, i+1, a.Tool, color.Reset)
	}

	lastTh := ""
	if len(r.Actions) > 0 {
		lastTh = r.Actions[len(r.Actions)-1].Thinking
	}

	if r.Thinking != "" && r.Thinking != lastTh {
		label := "thinking"
		if len(r.Actions) > 0 {
			label = "final thinking"
		}
		fmt.Printf("  %s[%s]%s\n", color.Dim, label, color.Reset)
		for _, ln := range limitLines(r.Thinking, maxLines) {
			fmt.Printf("  %s%s%s\n", color.Magenta, ln, color.Reset)
		}
		fmt.Println()
	}

	if r.Status == "confirm" {
		fmt.Println(color.Orange + r.Reply + color.Reset)
	} else {
		fmt.Println(color.Gold + r.Reply + color.Reset)
	}
}

// ── Verbose ───────────────────────────────────────────────────────────────────

func Verbose(r *api.ChatResponse) {
	sc := color.Green
	if r.Status == "confirm" {
		sc = color.Orange
	} else if r.Status == "error" {
		sc = color.Red
	}

	fmt.Printf("  %s─────────────────────────────────────────%s\n", color.Dim, color.Reset)
	fmt.Printf("  %ssession%s  %s%s%s  %sstatus%s  %s%s%s\n",
		color.Dim, color.Reset,
		color.Blue, r.SessionID, color.Reset,
		color.Dim, color.Reset,
		sc, r.Status, color.Reset,
	)

	if len(r.Actions) > 0 {
		fmt.Println()
		for i, a := range r.Actions {
			fmt.Printf("  %s[%d] %s%s\n", color.Dim, i+1, a.Tool, color.Reset)

			argsJSON, _ := json.Marshal(a.Args)
			if len(argsJSON) < 80 {
				fmt.Printf("      %sargs%s    %s\n", color.Dim, color.Reset, string(argsJSON))
			} else {
				for k, v := range a.Args {
					vs, _ := json.Marshal(v)
					vstr := string(vs)
					if len(vstr) > 80 {
						vstr = vstr[:77] + "..."
					}
					fmt.Printf("      %s%s%s    %s\n", color.Dim, k, color.Reset, vstr)
				}
			}

			if a.Result != "" {
				lines := strings.Split(strings.TrimSpace(a.Result), "\n")
				if a.Tool == "execute_code" {
					fmt.Printf("      %sresult%s\n", color.Dim, color.Reset)
					shown := lines
					if len(shown) > 20 {
						shown = shown[:20]
					}
					for _, ln := range shown {
						fmt.Printf("      %s%s%s\n", color.Red, ln, color.Reset)
					}
					if len(lines) > 20 {
						fmt.Printf("      %s... +%d lines%s\n", color.Dim, len(lines)-20, color.Reset)
					}
				} else {
					preview := lines[0]
					if len(preview) > 120 {
						preview = preview[:120]
					}
					sfx := ""
					if len(lines) > 1 {
						sfx = fmt.Sprintf("  %s+%d lines%s", color.Dim, len(lines)-1, color.Reset)
					}
					fmt.Printf("      %sresult%s  %s%s\n", color.Dim, color.Reset, preview, sfx)
				}
			}

			if a.Thinking != "" {
				thLines := limitLines(a.Thinking, 5)
				fmt.Printf("      %sthinking%s\n", color.Dim, color.Reset)
				for _, ln := range thLines {
					fmt.Printf("      %s%s%s\n", color.Cyan, ln, color.Reset)
				}
				full := strings.Split(strings.TrimSpace(a.Thinking), "\n")
				if len(full) > 5 {
					fmt.Printf("      %s... +%d lines%s\n", color.Cyan, len(full)-5, color.Reset)
				}
			}
			fmt.Println()
		}
	}

	lastTh := ""
	if len(r.Actions) > 0 {
		lastTh = r.Actions[len(r.Actions)-1].Thinking
	}
	if r.Thinking != "" && r.Thinking != lastTh {
		label := "thinking"
		if len(r.Actions) > 0 {
			label = "final thinking"
		}
		fmt.Printf("  %s%s%s\n", color.Dim, label, color.Reset)
		for _, ln := range limitLines(r.Thinking, maxLines) {
			fmt.Printf("  %s%s%s\n", color.Magenta, ln, color.Reset)
		}
		full := strings.Split(strings.TrimSpace(r.Thinking), "\n")
		if len(full) > maxLines {
			fmt.Printf("  %s... +%d lines%s\n", color.Magenta, len(full)-maxLines, color.Reset)
		}
		fmt.Println()
	}

	if r.PendingAction != nil {
		args, _ := json.Marshal(r.PendingAction.Args)
		fmt.Printf("  %spending%s  %s%s %s%s\n",
			color.Dim, color.Reset,
			color.Orange, r.PendingAction.Tool, string(args), color.Reset,
		)
		fmt.Println()
	}

	fmt.Printf("  %s─────────────────────────────────────────%s\n", color.Dim, color.Reset)
	if r.Status == "confirm" {
		fmt.Println(color.Orange + r.Reply + color.Reset)
	} else {
		fmt.Println(color.Gold + r.Reply + color.Reset)
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func limitLines(s string, n int) []string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) > n {
		return lines[:n]
	}
	return lines
}
