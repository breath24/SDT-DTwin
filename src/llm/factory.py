"""LLM factory for creating language model instances."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from ..config_loader import load_config


def normalize_openai_model_and_kwargs(model: str) -> Tuple[str, Dict[str, Any]]:
    """
    Map virtual model names to real model + request kwargs.
    
    Example: "o4-mini-high" -> ("o4-mini", {"reasoning": {"effort": "high"}})
    """
    normalized_model = model
    model_kwargs: Dict[str, Any] = {}
    
    # o4-mini with explicit reasoning effort
    if model.lower() == "o4-mini-high":
        normalized_model = "o4-mini"
        model_kwargs["reasoning"] = {"effort": "high"}
        
    return normalized_model, model_kwargs


def make_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> BaseChatModel:
    """
    Create an LLM instance based on the provider and model.
    
    Args:
        provider: Provider name ("google", "openai", "anthropic", "openrouter")
        model: Model identifier (e.g., "gemini-2.0-flash", "gpt-4o", "claude-3-5-sonnet-20241022")
        api_key: API key for the provider
        base_url: Base URL for custom endpoints (mainly for OpenRouter)
    
    Returns:
        Configured LLM instance
    """
    if not api_key:
        raise ValueError(f"API key is required for provider {provider}")
    
    config = load_config()
    supported_providers = config.providers.get("supported", ["google", "openai", "anthropic", "openrouter"])
    if provider not in supported_providers:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Supported providers: {', '.join(supported_providers)}"
        )
    
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model, api_key=api_key)
    
    elif provider == "openai":
        real_model, model_kwargs = normalize_openai_model_and_kwargs(model)
        kwargs: Dict[str, Any] = {"model": real_model, "api_key": api_key}
        
        # Elevate supported params explicitly to avoid warnings
        if "reasoning" in model_kwargs:
            kwargs["reasoning"] = model_kwargs.pop("reasoning")
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
        if base_url:
            kwargs["base_url"] = base_url
            
        return ChatOpenAI(**kwargs)
    
    elif provider == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key)
    
    elif provider == "openrouter":
        # OpenRouter uses OpenAI API format
        if base_url is None:
            config = load_config()
            base_url = config.providers.get("openrouter_base_url", "https://openrouter.ai/api/v1")
            
        real_model, model_kwargs = normalize_openai_model_and_kwargs(model)
        kwargs: Dict[str, Any] = {
            "model": real_model, 
            "api_key": api_key, 
            "base_url": base_url
        }
        
        if "reasoning" in model_kwargs:
            kwargs["reasoning"] = model_kwargs.pop("reasoning")
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
            
        return ChatOpenAI(**kwargs)
    
    # This should never be reached due to the earlier check
    raise ValueError(f"Unsupported provider: {provider}")


def make_llm_from_settings(settings, model: str | None = None) -> BaseChatModel:
    """
    Create an LLM from settings object.
    
    Args:
        settings: Settings object containing provider, API keys, and default model
        model: Model to use (if None, uses settings.default_model)
    
    Returns:
        Configured LLM instance
    """
    if model is None:
        model = settings.default_model
    
    api_key = settings.get_current_api_key()
    base_url = settings.base_url if settings.base_url else None
    
    return make_llm(
        provider=settings.provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
