"""Constants for the dev-twin project. Configuration moved to config/default.json"""

from __future__ import annotations

# Static file name
DOCKER_FILE_NAME = "Dockerfile"

# Keywords for plan validation
CORE_IMPLEMENTATION_KEYWORDS = [
    "implement", "create", "build", "develop", "add", "write"
]

VALID_STUCK_KEYWORDS = [
    "test", "lint", "setup", "config", "install", "deploy"
]

# Error message templates
ERRORS = {
    "MISSING_GITHUB_TOKEN": "GITHUB_TOKEN is required",
    "MISSING_REPO_URL": "REPO_URL is required", 
    "INVALID_PROVIDER": "PROVIDER must be one of: {providers}",
    "MISSING_API_KEY": "{provider}_API_KEY is required when PROVIDER={provider}",
    "FILE_NOT_FOUND": "NOT_FOUND: {path}",
    "PATCH_VALIDATION_ERROR": "Patch must start with '*** Begin Patch' and end with '*** End Patch'",
    "NO_PLAN": "NO_PLAN",
    "PLAN_INCOMPLETE": "plan has incomplete steps",
    "TOO_MANY_STUCK_STEPS": "too many steps marked as stuck - likely misuse",
}
