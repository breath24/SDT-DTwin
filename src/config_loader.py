"""Configuration loader for dev-twin with CLI override support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

# Global context for configuration so that callers who don't
# thread config_file/overrides explicitly still respect CLI inputs
_GLOBAL_CONFIG_FILE: Optional[str] = None
_GLOBAL_OVERRIDES: Optional[Dict[str, Any]] = None


@dataclass
class AgentConfig:
    """Configuration for a specific agent."""
    max_steps: int
    max_history_chars: Optional[int] = None
    keep_last_messages: Optional[int] = None
    max_tool_result_chars: Optional[int] = None
    tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DevTwinConfig:
    """Main configuration class for dev-twin."""
    agents: Dict[str, AgentConfig] = field(default_factory=dict)
    prompts: Dict[str, Any] = field(default_factory=dict)
    timeouts: Dict[str, int] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    providers: Dict[str, Any] = field(default_factory=dict)
    docker: Dict[str, str] = field(default_factory=dict)
    git: Dict[str, str] = field(default_factory=dict)
    file_types: Dict[str, Any] = field(default_factory=dict)
    testing: Dict[str, Any] = field(default_factory=dict)
    paths: Dict[str, Any] = field(default_factory=dict)


def _find_project_root() -> Path:
    """Find the project root directory."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / "config" / "default.json").exists():
            return current
        current = current.parent
    # Fallback to the src parent directory
    return Path(__file__).parent.parent


def load_config(
    config_file: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> DevTwinConfig:
    """Load configuration from file with optional CLI overrides.
    
    Args:
        config_file: Path to custom config file (defaults to config/default.json)
        overrides: Dictionary of CLI overrides in dot notation (e.g., "agents.unified.max_steps": 300)
    
    Returns:
        DevTwinConfig instance
    """
    # Fall back to globally set context when explicit args are not provided
    if config_file is None and _GLOBAL_CONFIG_FILE is not None:
        config_file = _GLOBAL_CONFIG_FILE
    if overrides is None and _GLOBAL_OVERRIDES is not None:
        overrides = _GLOBAL_OVERRIDES

    if config_file:
        config_path = Path(config_file)
    else:
        project_root = _find_project_root()
        config_path = project_root / "config" / "default.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # Apply CLI overrides
    if overrides:
        config_data = _apply_overrides(config_data, overrides)
    
    # Convert to structured config
    agents = {}
    for agent_name, agent_data in config_data.get("agents", {}).items():
        agents[agent_name] = AgentConfig(
            max_steps=agent_data.get("max_steps", 50),
            max_history_chars=agent_data.get("max_history_chars"),
            keep_last_messages=agent_data.get("keep_last_messages"),
            max_tool_result_chars=agent_data.get("max_tool_result_chars"),
            tools=agent_data.get("tools", {})
        )
    
    return DevTwinConfig(
        agents=agents,
        prompts=config_data.get("prompts", {}),
        timeouts=config_data.get("timeouts", {}),
        limits=config_data.get("limits", {}),
        providers=config_data.get("providers", {}),
        docker=config_data.get("docker", {}),
        git=config_data.get("git", {}),
        file_types=config_data.get("file_types", {}),
        testing=config_data.get("testing", {}),
        paths=config_data.get("paths", {}),
    )


def set_global_config_context(*, config_file: Optional[str], overrides: Optional[Dict[str, Any]]) -> None:
    """Set global default context for config loading throughout the process."""
    global _GLOBAL_CONFIG_FILE, _GLOBAL_OVERRIDES
    _GLOBAL_CONFIG_FILE = config_file
    _GLOBAL_OVERRIDES = overrides


def _apply_overrides(config_data: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply CLI overrides to config data using dot notation."""
    result = config_data.copy()
    
    for key, value in overrides.items():
        # Split dot notation key (e.g., "agents.unified.max_steps")
        parts = key.split(".")
        current = result
        
        # Navigate to the parent of the target key
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the final value
        final_key = parts[-1]
        current[final_key] = value
    
    return result


def get_agent_config(config: DevTwinConfig, agent_name: str) -> AgentConfig:
    """Get configuration for a specific agent with fallback defaults."""
    if agent_name in config.agents:
        return config.agents[agent_name]
    
    # Fallback defaults
    return AgentConfig(
        max_steps=50,
        max_history_chars=None,
        keep_last_messages=None,
        max_tool_result_chars=None,
        tools={}
    )


def get_enabled_tools(config: DevTwinConfig, agent_name: str) -> Dict[str, Dict[str, Any]]:
    """Get enabled tools for a specific agent."""
    agent_config = get_agent_config(config, agent_name)
    return {
        name: tool_config 
        for name, tool_config in agent_config.tools.items() 
        if tool_config.get("enabled", False)
    }


def get_timeout_setting(config: DevTwinConfig, setting_name: str, default: int) -> int:
    """Get timeout setting with fallback to default."""
    return config.timeouts.get(setting_name, default)


def get_limit_setting(config: DevTwinConfig, setting_name: str, default: Any) -> Any:
    """Get limit setting with fallback to default."""
    return config.limits.get(setting_name, default)


def get_agent_history_setting(config: DevTwinConfig, agent_name: str, setting_name: str) -> Any:
    """Get agent-specific history setting with fallback to global defaults."""
    # First check if agent has specific setting (and it's not None)
    agent_config = get_agent_config(config, agent_name)
    agent_value = getattr(agent_config, setting_name, None)
    if agent_value is not None:
        return agent_value
    
    # Fall back to limits
    fallback_map = {
        "max_history_chars": get_limit_setting(config, "max_history_chars", 100000),
        "keep_last_messages": get_limit_setting(config, "keep_last_messages", 40),
        "max_tool_result_chars": get_limit_setting(config, "default_tool_result_chars", 4000),
    }
    return fallback_map.get(setting_name, None)


def load_prompt(prompt_name: str, project_root: Optional[Path] = None) -> str:
    """Load a prompt from the prompts directory."""
    if project_root is None:
        project_root = _find_project_root()
    
    prompt_path = project_root / "src" / "prompts" / f"{prompt_name}.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    return prompt_path.read_text(encoding='utf-8')


def build_unified_prompt(
    config: DevTwinConfig, 
    tools: Dict[str, Dict[str, Any]],
    project_root: Optional[Path] = None
) -> str:
    """Build the unified agent prompt with dynamic content injection."""
    base_prompt = load_prompt("unified_base", project_root)
    
    # Build available tools list
    available_tools = "\n- ".join([
        f"**{name}**{tool_config['description']}" 
        for name, tool_config in tools.items()
    ])
    
    # Determine if patch format should be included
    patch_usage = ""
    patch_format = ""
    
    if "apply_patch" in tools:
        patch_usage = "- Prefer `apply_patch` for multi-file edits"
        
        # Load patch format from a separate prompt file or define inline
        patch_format = '''
**Patch Format**: Use `apply_patch` with this exact format:
```
*** Begin Patch
*** Update File: path/to/file.py
@@ optional hunk header
| context line
-removed line
+added line
| more context
*** End Patch
```

**Patch Best Practices**:
- **Read before patching**: Always `read_file` immediately before applying patches
- **Small patches**: Limit patches to 5-10 lines of changes to avoid context mismatches
- **Exact context**: Use exact whitespace and formatting from the current file
- **Sequential changes**: Apply changes one function/section at a time
- **Handle failures**: If a patch fails, read the file again and try a smaller patch

**Patch Examples**:
```
*** Begin Patch
*** Add File: src/new_module.py
+def hello():
+    return "world"
*** End Patch
```

```
*** Begin Patch
*** Update File: src/main.py
@@ in main function
| def main():
-    print("old")
+    print("new")
     return 0
*** End Patch
```
'''
    
    # Replace placeholders
    return base_prompt.format(
        AVAILABLE_TOOLS=available_tools,
        PATCH_USAGE=patch_usage,
        PATCH_FORMAT=patch_format
    )
