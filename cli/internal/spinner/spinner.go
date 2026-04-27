package spinner

import (
	"fmt"
	"time"
)

var frames = []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}

const dim   = "\033[2m"
const reset = "\033[0m"

type Spinner struct {
	msg  string
	stop chan struct{}
	done chan struct{}
}

func New(msg string) *Spinner {
	return &Spinner{msg: msg, stop: make(chan struct{}), done: make(chan struct{})}
}

func (s *Spinner) Start() {
	go func() {
		defer close(s.done)
		i := 0
		for {
			select {
			case <-s.stop:
				fmt.Printf("\r\033[K")
				return
			default:
				fmt.Printf("\r  %s%s %s%s", dim, frames[i%len(frames)], s.msg, reset)
				time.Sleep(80 * time.Millisecond)
				i++
			}
		}
	}()
}

func (s *Spinner) Stop() {
	close(s.stop)
	<-s.done
}
