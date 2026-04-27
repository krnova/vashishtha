package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type API struct {
	Provider string            `json:"provider"`
	Models   map[string]string `json:"models"`
}

type Config struct {
	API API `json:"api"`
}

func Load(vashDir string) (*Config, error) {
	path := filepath.Join(vashDir, "config.json")
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var c Config
	if err := json.Unmarshal(b, &c); err != nil {
		return nil, err
	}
	return &c, nil
}

func (c *Config) Save(vashDir string) error {
	path := filepath.Join(vashDir, "config.json")
	b, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0644)
}

func Providers(vashDir string) []string {
	c, err := Load(vashDir)
	if err != nil {
		return []string{"nim", "gemini", "groq"}
	}
	out := make([]string, 0, len(c.API.Models))
	for k := range c.API.Models {
		out = append(out, k)
	}
	return out
}
