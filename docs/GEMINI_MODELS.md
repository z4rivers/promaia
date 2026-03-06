# Gemini Model Configuration

How to use different Gemini models with Promaia.

## Available Gemini Models

### Gemini 3.1 (Current Generation — March 2026)
- **pro** → `gemini-3.1-pro-preview` - Advanced reasoning, agentic workflows, coding (default)
- **flash-lite** → `gemini-3.1-flash-lite-preview` - Cost-efficient, high-volume tasks

### Gemini 3 (Still Current)
- **flash** → `gemini-3-flash-preview` - Pro-level intelligence at Flash speed/pricing

### Gemini 2.5 (Legacy)
- **2.5-pro** → `gemini-2.5-pro-preview-05-06`
- **2.5-flash** → `gemini-2.5-flash-preview-05-20`

### Embedding
- **gemini-embedding-001** - 768-dimensional vectors for semantic search

### Deprecated (DO NOT USE)
- `gemini-3-pro-preview` — **Shut down March 9, 2026**
- `gemini-2.0-flash-exp` — Superseded by 3.1 Flash-Lite
- `gemini-2.0-flash-thinking-exp-1219` — Superseded

## Configuration

Set `GOOGLE_DEFAULT_MODEL` in `.env`:

```bash
# Key names (resolved via GOOGLE_MODELS dict)
GOOGLE_DEFAULT_MODEL='pro'          # Gemini 3.1 Pro (default)
GOOGLE_DEFAULT_MODEL='flash'        # Gemini 3 Flash
GOOGLE_DEFAULT_MODEL='flash-lite'   # Gemini 3.1 Flash-Lite (cheapest)
GOOGLE_DEFAULT_MODEL='2.5-pro'      # Gemini 2.5 Pro (legacy)

# Or use full model IDs directly
GOOGLE_DEFAULT_MODEL='gemini-3.1-pro-preview'
```

## Model Selection Guide

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| Gemini 3.1 Pro | Medium | Medium | Complex reasoning, agentic workflows, coding |
| Gemini 3 Flash | Fast | Low | General purpose, balanced speed/quality |
| Gemini 3.1 Flash-Lite | Very Fast | Very Low | High-volume extraction, simple tasks |

## Internal Usage

- **Brain action extraction** (`promaia/brain/extraction.py`): Uses `gemini-3.1-flash-lite-preview`
- **Embeddings** (`promaia/storage/vector_db.py`): Uses `gemini-embedding-001` (768 dims)
- **Chat/NL** (`promaia/ai/nl_orchestrator.py`): Uses `GOOGLE_DEFAULT_MODEL` setting
- **Web routers**: Uses `GOOGLE_DEFAULT_MODEL` setting
