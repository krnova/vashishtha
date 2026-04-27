package color

const (
	Gold    = "\033[38;5;220m"
	Dim     = "\033[2m"
	Bold    = "\033[1m"
	Cyan    = "\033[38;5;51m"
	Magenta = "\033[38;5;177m"
	Red     = "\033[38;5;196m"
	Green   = "\033[38;5;82m"
	Orange  = "\033[38;5;208m"
	Blue    = "\033[38;5;75m"
	Reset   = "\033[0m"
)

func G(s string) string  { return Gold + s + Reset }
func Gr(s string) string { return Green + s + Reset }
func D(s string) string  { return Dim + s + Reset }
func B(s string) string  { return Bold + s + Reset }
func R(s string) string  { return Red + s + Reset }
func O(s string) string  { return Orange + s + Reset }
func Bl(s string) string { return Blue + s + Reset }
func C(s string) string  { return Cyan + s + Reset }
func M(s string) string  { return Magenta + s + Reset }
