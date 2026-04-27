package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const DefaultURL = "http://127.0.0.1:5000"

type Client struct {
	base string
	http *http.Client
}

func New(base string) *Client {
	return &Client{
		base: base,
		http: &http.Client{Timeout: 120 * time.Second},
	}
}

// ── Request / Response types ──────────────────────────────────────────────────

type ChatRequest struct {
	Message    string `json:"message"`
	SessionID  string `json:"session_id,omitempty"`
	Thinking   bool   `json:"thinking,omitempty"`
	Confirming bool   `json:"confirming,omitempty"`
}

type Action struct {
	Tool     string                 `json:"tool"`
	Args     map[string]interface{} `json:"args"`
	Result   string                 `json:"result"`
	Thinking string                 `json:"thinking,omitempty"`
}

type ChatResponse struct {
	Reply                string   `json:"reply"`
	SessionID            string   `json:"session_id"`
	Status               string   `json:"status"`
	Actions              []Action `json:"actions"`
	Thinking             string   `json:"thinking,omitempty"`
	ConfirmationRequired bool     `json:"confirmation_required"`
	ConfirmQuestion      string   `json:"confirmation_question,omitempty"`
	PendingAction        *Action  `json:"pending_action,omitempty"`
	Error                string   `json:"error,omitempty"`
}

type HealthResponse struct {
	Status         string `json:"status"`
	Model          string `json:"model"`
	ActiveSessions int    `json:"active_sessions"`
}

// ── Methods ───────────────────────────────────────────────────────────────────

func (c *Client) Health() (*HealthResponse, error) {
	resp, err := c.http.Get(c.base + "/health")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var h HealthResponse
	if err := json.NewDecoder(resp.Body).Decode(&h); err != nil {
		return nil, err
	}
	return &h, nil
}

func (c *Client) Ping() bool {
	cl := &http.Client{Timeout: 3 * time.Second}
	resp, err := cl.Get(c.base + "/health")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == 200
}

func (c *Client) Chat(req ChatRequest) (*ChatResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	resp, err := c.http.Post(c.base+"/chat", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var cr ChatResponse
	if err := json.Unmarshal(raw, &cr); err != nil {
		return nil, fmt.Errorf("parse error: %w — raw: %s", err, string(raw[:min(len(raw), 200)]))
	}
	return &cr, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
