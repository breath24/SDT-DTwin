from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from .error_handling import validate_required_config


@dataclass
class Settings:
    github_token: str
    repo_url: str
    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    provider: str = "google"  # google, openai, anthropic, openrouter
    default_model: str = "gemini-2.0-flash"
    base_url: str = ""  # For custom endpoints
    workdir: Path = Path(".devtwin_work")

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            repo_url=os.environ.get("REPO_URL", ""),
            google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            provider=os.environ.get("PROVIDER", "google"),
            default_model=os.environ.get("DEFAULT_MODEL", "gemini-2.0-flash"),
            base_url=os.environ.get("BASE_URL", ""),
            workdir=Path(os.environ.get("WORKDIR", ".devtwin_work")),
        )

    def get_api_key_for_provider(self, provider: str) -> str:
        """Get the API key for a specific provider."""
        if provider == "google":
            return self.google_api_key
        elif provider == "openai":
            return self.openai_api_key
        elif provider == "anthropic":
            return self.anthropic_api_key
        elif provider == "openrouter":
            return self.openrouter_api_key
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_current_api_key(self) -> str:
        """Get the API key for the currently configured provider."""
        return self.get_api_key_for_provider(self.provider)

    def ensure(self) -> None:
        validate_required_config(self)
        self.workdir.mkdir(parents=True, exist_ok=True)


