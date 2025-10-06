ANTHROPIC_MODELS = {
    "opus": "claude-opus-4-1-20250805",
    "sonnet": "claude-sonnet-4-5-20250929",
}

GOOGLE_MODELS = {
    "pro": "gemini-2.5-pro-preview-05-06",
    "flash": "gemini-2.5-flash-preview-05-20",
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
    "claude-opus-4-1-20250805": "Claude Opus 4.1",
    "claude-opus-4-20250514": "Claude Opus 4",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
    
    # Google models
    "gemini-2.5-pro-preview-05-06": "Gemini 2.5 Pro",
    "gemini-2.5-flash-preview-05-20": "Gemini 2.5 Flash",
    
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
            "gemini": "Gemini 2.5 Pro",
            "llama": f"Local Llama ({model_id})"
        }
        return api_fallbacks.get(api_type, model_id)
    
    # Last resort: return the model ID itself
    return model_id

def get_current_anthropic_model() -> str:
    """Get the current default Anthropic model ID."""
    return ANTHROPIC_MODELS.get("sonnet", "claude-sonnet-4-5-20250929")

def get_current_google_model() -> str:
    """Get the current default Google model ID."""
    return GOOGLE_MODELS.get("pro", "gemini-2.5-pro-preview-05-06") 