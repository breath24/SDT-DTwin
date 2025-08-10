# Configuration System

This directory contains configuration files for dev-twin agents and system settings.

## Files

- `default.json` - Default configuration settings
- `example.json` - Example configuration showing customization options

## Usage

### Using Custom Configuration File

```bash
# Use a custom config file
dev-twin --config-file config/example.json

# Use custom config with demo
dev-twin demo run --config-file config/example.json
```

### Using CLI Overrides

```bash
# Override specific settings via CLI
dev-twin --config agents.unified.max_steps=300 --config agents.unified.context_size=150000

# Multiple overrides
dev-twin --config agents.unified.max_steps=300 \
         --config timeouts.default_shell_timeout=90

# Override for benchmarks
dev-twin bench run --config agents.unified.max_steps=500
```

## Configuration Structure

### Agent Configuration

Each agent can be configured with:
- `max_steps`: Maximum number of steps the agent can take
- `max_history_chars`: Maximum characters to keep in conversation history (overrides global default)
- `keep_last_messages`: Number of recent messages to always keep. Use -1 for unlimited messages (subject to max_history_chars limit). (overrides global default)
- `max_tool_result_chars`: Maximum characters per tool result (overrides global default)
- `tools`: Tool configuration (for unified agent only)

### Tool Configuration

For the unified agent, tools can be enabled/disabled and descriptions can be customized:

```json
{
  "agents": {
    "unified": {
      "tools": {
        "replace_in_file": {
          "enabled": true,
          "description": "(path, pattern, replacement, flags=\"\", count=1): Replace text in file"
        },
        "debug_env": {
          "enabled": false,
          "description": "(): Show working directory and file structure (for debugging)"
        }
      }
    }
  }
}
```

### Global Settings

- `timeouts`: Shell command timeouts and test timeouts
- `limits`: Various system limits and thresholds
- `providers`: LLM provider configuration
- `docker`: Docker-related settings
- `git`: Git-related settings

## Override Format

CLI overrides use dot notation to specify nested configuration values:

- `agents.unified.max_steps=300` - Set max steps for unified agent
- `agents.unified.max_history_chars=150000` - Set history limit for unified agent
- `limits.max_history_chars=120000` - Set default history limit for all agents
- `tools.shell.enabled=false` - Disable shell tool
- `timeouts.test_timeout=180` - Set test timeout to 3 minutes

Values are automatically converted to appropriate types:
- `true`/`false` → boolean
- Numeric strings → int or float
- Everything else → string

## Extending Configuration

To add new configuration options:

1. Update `config/default.json` with the new setting
2. Add corresponding field to `DevTwinConfig` in `src/config_loader.py`
3. Use the configuration in your code via `load_config()`

Example:

```python
from src.config_loader import load_config

config = load_config(overrides={"agents.my_agent.custom_setting": "value"})
my_setting = config.agents.get("my_agent", {}).get("custom_setting", "default")
```
