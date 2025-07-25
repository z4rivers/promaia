from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None

class ChatMessageInput(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None
    preferred_model: Optional[str] = None  # 'anthropic', 'openai', 'gemini'

class TokenUsage(BaseModel):
    prompt_tokens: int
    response_tokens: int
    total_tokens: int
    cost: Optional[float] = None  # Total cost in USD
    model: Optional[str] = None  # Model name for cost calculation context

class ChatMessageOutput(BaseModel):
    reply: str
    conversation_id: str
    model_used: Optional[str] = None  # Which model actually responded
    token_usage: Optional[TokenUsage] = None  # Token count information
    # We could add other fields like debug_info, etc. 

class InitialMessageOutput(BaseModel):
    message: str
    conversation_id: str
    model_used: Optional[str] = None 