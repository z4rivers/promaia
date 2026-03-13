ANTHROPIC_MODELS = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

GOOGLE_MODELS = {
    # Gemini 3.1 models (current generation — March 2026)
    "pro": "gemini-3.1-pro-preview",
    "flash-lite": "gemini-3.1-flash-lite-preview",
    # Gemini 3 models (still current)
    "flash": "gemini-3-flash-preview",
    # Gemini 2.5 models (legacy, but TTS still lives here)
    "2.5-pro": "gemini-2.5-pro",
    "2.5-flash": "gemini-2.5-flash",
    # TTS-specific models (2.5 generation — 3.x doesn't support audio output yet)
    "tts": "gemini-2.5-flash-preview-tts",
    "tts-hq": "gemini-2.5-pro-preview-tts",
    # Embeddings (Gemini Embedding 2 — multimodal: text, image, audio, video, PDF)
    "embedding": "gemini-embedding-2-preview",
}

# Local Llama models (commonly used models with Ollama or similar local setups)
LLAMA_MODELS = {
    "llama3": "llama3:latest",
    "llama3-8b": "llama3:8b",
    "llama3-70b": "llama3:70b",
    "codellama": "codellama:latest",
    "codellama-7b": "codellama:7b",
    "codellama-13b": "codellama:13b",
    "mixtral": "mixtral:latest",
    "mistral": "mistral:latest",
}

# Display names for models (maps model IDs to human-readable names)
MODEL_DISPLAY_NAMES = {
    # Anthropic models
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-opus-4-5": "Claude Opus 4.5",
    "claude-sonnet-4-5": "Claude Sonnet 4.5",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",

    # Google models - Gemini 3.1
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash-Lite",

    # Google models - Gemini 3
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "gemini-3-flash": "Gemini 3 Flash",

    # Google models - Gemini 2.5 (legacy, but TTS still lives here)
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-flash-preview-tts": "Gemini 2.5 Flash TTS",
    "gemini-2.5-pro-preview-tts": "Gemini 2.5 Pro TTS",

    # OpenAI models
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4": "GPT-4",

    # Llama models
    "llama3:latest": "Llama 3",
    "llama3:8b": "Llama 3 8B",
    "llama3:70b": "Llama 3 70B",
    "codellama:latest": "Code Llama",
    "codellama:7b": "Code Llama 7B",
    "codellama:13b": "Code Llama 13B",
    "mixtral:latest": "Mixtral",
    "mistral:latest": "Mistral",
}

def get_model_display_name(model_id: str, api_type: str = None) -> str:
    """
    Get the human-readable display name for a model ID.
    
    Args:
        model_id: The model identifier (e.g., "claude-sonnet-4-5-20250929")
        api_type: Optional API type (anthropic, openai, gemini, llama) for generic fallback
    
    Returns:
        Human-readable model name
    """
    # Try direct lookup first
    if model_id in MODEL_DISPLAY_NAMES:
        return MODEL_DISPLAY_NAMES[model_id]
    
    # Fallback to API-based generic names
    if api_type:
        api_fallbacks = {
            "anthropic": "Claude",
            "openai": "GPT-4o",
            "gemini": "Gemini 3.1 Pro",
            "llama": f"Local Llama ({model_id})"
        }
        return api_fallbacks.get(api_type, model_id)
    
    # Last resort: return the model ID itself
    return model_id

def get_current_anthropic_model() -> str:
    """Get the current default Anthropic model ID."""
    return ANTHROPIC_MODELS["sonnet"]

def get_current_google_model() -> str:
    """Get the current default Google model ID."""
    import os
    # Check for environment variable first, then fall back to default
    env_model = os.getenv("GOOGLE_DEFAULT_MODEL")
    if env_model:
        # If it's a key in GOOGLE_MODELS, resolve it
        if env_model in GOOGLE_MODELS:
            return GOOGLE_MODELS[env_model]
        # Otherwise assume it's a full model ID
        return env_model
    return GOOGLE_MODELS["flash"]