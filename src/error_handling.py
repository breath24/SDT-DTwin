"""Centralized error handling and custom exceptions for dev-twin."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import ERRORS
from .config_loader import load_config


class DevTwinError(Exception):
    """Base exception for dev-twin errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConfigurationError(DevTwinError):
    """Raised when configuration is invalid or missing."""
    pass


class GitHubError(DevTwinError):
    """Raised when GitHub API operations fail."""
    pass


class DockerError(DevTwinError):
    """Raised when Docker operations fail."""
    pass


class LLMError(DevTwinError):
    """Raised when LLM operations fail."""
    pass


class PatchError(DevTwinError):
    """Raised when patch operations fail."""
    pass


class PlanValidationError(DevTwinError):
    """Raised when plan validation fails."""
    pass


def format_error_message(error_key: str, **kwargs) -> str:
    """Format an error message from the constants."""
    try:
        template = ERRORS.get(error_key, "Unknown error")
        return template.format(**kwargs)
    except KeyError as e:
        return f"Error formatting message for '{error_key}': missing key {e}"


def safe_execute(func, default=None, error_type: type = DevTwinError, log_errors: bool = True):
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        default: Default value to return on error
        error_type: Exception type to catch and re-raise as DevTwinError
        log_errors: Whether to log errors
    
    Returns:
        Function result or default value on error
    """
    try:
        return func()
    except error_type:
        raise  # Re-raise dev-twin errors
    except Exception as e:
        if log_errors:
            logging.error(f"Error in {func.__name__ if hasattr(func, '__name__') else 'function'}: {e}")
        if error_type != DevTwinError:
            raise error_type(str(e)) from e
        return default


def validate_required_config(settings) -> None:
    """Validate required configuration settings."""
    if not settings.github_token:
        raise ConfigurationError(format_error_message("MISSING_GITHUB_TOKEN"))
    
    if not settings.repo_url:
        raise ConfigurationError(format_error_message("MISSING_REPO_URL"))
    
    # Validate provider
    config = load_config()
    supported_providers = config.providers.get("supported", ["google", "openai", "anthropic", "openrouter"])
    if settings.provider not in supported_providers:
        raise ConfigurationError(
            format_error_message("INVALID_PROVIDER", providers=", ".join(supported_providers))
        )
    
    # Check API key
    required_key = settings.get_current_api_key()
    if not required_key:
        provider = settings.provider
        raise ConfigurationError(
            f"{provider.upper()}_API_KEY is required when PROVIDER={provider}"
        )


def handle_file_operation_error(error: Exception, file_path: str | Path) -> str:
    """Handle common file operation errors and return user-friendly message."""
    if isinstance(error, FileNotFoundError):
        return format_error_message("FILE_NOT_FOUND", path=file_path)
    elif isinstance(error, PermissionError):
        return f"Permission denied: {file_path}"
    elif isinstance(error, OSError):
        return f"OS error accessing {file_path}: {error}"
    else:
        return f"Unexpected error with {file_path}: {error}"


class ErrorHandler:
    """Context manager for consistent error handling."""
    
    def __init__(
        self, 
        operation: str, 
        reraise: bool = True, 
        log_level: int = logging.ERROR,
        artifacts_dir: Optional[Path] = None
    ):
        self.operation = operation
        self.reraise = reraise
        self.log_level = log_level
        self.artifacts_dir = artifacts_dir
        self.error: Optional[Exception] = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            error_msg = f"Error in {self.operation}: {exc_val}"
            
            # Log the error
            logging.log(self.log_level, error_msg)
            
            # Write error to artifacts if available
            if self.artifacts_dir:
                try:
                    error_file = self.artifacts_dir / f"{self.operation}_error.txt"
                    error_file.write_text(str(exc_val), encoding="utf-8")
                except Exception:
                    pass  # Don't fail on error writing
            
            if self.reraise:
                # Convert to appropriate dev-twin error type
                if exc_type in (FileNotFoundError, PermissionError, OSError):
                    raise DevTwinError(error_msg) from exc_val
                elif "docker" in self.operation.lower():
                    raise DockerError(error_msg) from exc_val
                elif "github" in self.operation.lower():
                    raise GitHubError(error_msg) from exc_val
                elif "patch" in self.operation.lower():
                    raise PatchError(error_msg) from exc_val
                else:
                    raise DevTwinError(error_msg) from exc_val
            
            return True  # Suppress the exception
        
        return False


def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """Set up centralized logging for dev-twin."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger('devtwin')
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.warning(f"Could not set up file logging: {e}")


# Decorator for common error handling
def handle_errors(operation: str, error_type: type = DevTwinError):
    """Decorator to handle errors in functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except error_type:
                raise  # Re-raise specific dev-twin errors
            except Exception as e:
                raise error_type(f"Error in {operation}: {e}") from e
        return wrapper
    return decorator
