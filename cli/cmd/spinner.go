package cmd

import (
	"github.com/krnova/vashishtha/cli/internal/spinner"
)

var _sp *spinner.Spinner

func startSpinner(msg string) {
	_sp = spinner.New(msg)
	_sp.Start()
}

func stopSpinner() {
	if _sp != nil {
		_sp.Stop()
		_sp = nil
	}
}
