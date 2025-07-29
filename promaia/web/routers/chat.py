from fastapi import APIRouter, HTTPException
from promaia.web.models import ChatMessageInput, ChatMessageOutput, InitialMessageOutput

from promaia.ai.prompts import create_system_prompt
from promaia.utils.ai import debug_print
from promaia.ai.models import GOOGLE_MODELS
from promaia.config.databases import get_database_manager
from promaia.storage.files import read_markdown_files_with_registry

import os
import traceback
import google.generativeai as genai
import asyncio
import uuid
import random
from datetime import datetime

router = APIRouter()

# Initialize Gemini Client (outside the request handler if API key is always available)
# Ensure GOOGLE_API_KEY is loaded in the environment where Uvicorn runs
gemini_model_name = GOOGLE_MODELS.get("pro", "gemini-2.5-pro")
gemini_client_initialized = False
if os.getenv("GOOGLE_API_KEY"):
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        # Test configuration (optional, but good for early failure)
        # models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # if not any(gemini_model_name in m.name for m in models):
        #     debug_print(f"Error: Model {gemini_model_name} not available or not configured correctly.")
        # else:
        #     gemini_client_initialized = True # Placeholder, client re-init with system prompt per request
        gemini_client_initialized = True # Simpler check for now
        debug_print(f"Gemini API configured. Model to be used: {gemini_model_name}")
    except Exception as e:
        debug_print(f"Error configuring Gemini API: {e}. Gemini features will be unavailable.")
else:
    debug_print("GOOGLE_API_KEY not found. Gemini features will be unavailable.")

def load_initial_message_prompt():
    """Load the initial message prompt from the markdown file and add randomness for variety."""
    prompt_file_path = os.path.join(os.getcwd(), "prompts", "initial-message-prompt.md")
    
    try:
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read().strip()
        debug_print(f"Loaded initial message prompt from {prompt_file_path}")
    except FileNotFoundError:
        debug_print(f"Initial message prompt file not found at {prompt_file_path}")
        base_prompt = "Based on the context you have, create an engaging opening question or comment to start a conversation. This should be specific to the content in my journals/blog, reflect my voice, and be phrased as a first-person statement or question a human would naturally ask. Keep it under 100 characters if possible."
    except Exception as e:
        debug_print(f"Error loading initial message prompt: {e}")
        base_prompt = "Based on the context you have, create an engaging opening question or comment to start a conversation."
    
    # Add subtle variety elements that encourage different types of responses
    # These don't change the core instruction but give the AI different creative angles
    variety_elements = [
        "Focus on something that might spark curiosity or introspection.",
        "Consider drawing from a recent insight or reflection.",
        "Think about what might resonate most with someone seeking growth.",
        "Choose something that invites deeper conversation.",
        "Pick something that feels authentic and personally meaningful.",
        "Consider what would genuinely interest someone exploring these ideas.",
        "Focus on an element that might inspire or motivate reflection.",
        "Choose something that feels conversational and inviting.",
    ]
    
    # Randomly select one variety element
    selected_element = random.choice(variety_elements)
    
    # Combine the base prompt with the variety element
    enhanced_prompt = f"{base_prompt} {selected_element}"
    
    debug_print(f"Enhanced prompt with variety element: {selected_element}")
    return enhanced_prompt

@router.get("/initial-message", response_model=InitialMessageOutput)
async def get_initial_message():
    debug_print("--- get_initial_message invoked (Gemini) ---")
    
    conversation_id = str(uuid.uuid4())
    debug_print(f"Generated conversation ID: {conversation_id}")
    
    multi_source_data = {}
    try:
        db_manager = get_database_manager()
        cms_db_config = db_manager.get_database("cms") # Assuming 'cms' is the nickname
        if cms_db_config:
            cms_data = read_markdown_files_with_registry(cms_db_config)
            multi_source_data['cms'] = cms_data
            debug_print(f"Loaded {len(cms_data)} CMS entries.")
        else:
            debug_print("CMS database config not found.")
    except Exception as e:
        debug_print(f"Error reading content files: {e}\\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to read content entries.")

    system_prompt_str = create_system_prompt(multi_source_data)
    if not system_prompt_str:
        debug_print("Warning: create_system_prompt returned an empty string. Using fallback.")
        system_prompt_str = "You are a helpful AI."

    initial_message = "Welcome to KOii's journal! How can I help you today?"

    if not gemini_client_initialized:
        debug_print("Gemini client not available (check GOOGLE_API_KEY and configuration).")
        return InitialMessageOutput(message=initial_message, conversation_id=conversation_id)  # Return default message as fallback

    try:
        # Initialize the model with the system prompt
        current_gemini_model = genai.GenerativeModel(
            model_name=gemini_model_name,
            system_instruction=system_prompt_str 
        )
        
        # Load the instruction from the markdown file
        instruction = load_initial_message_prompt()
        
        # Add a subtle randomness injection to encourage variety
        # This gives the AI a slightly different "mental state" each time
        conversation_starters = [
            "with fresh curiosity",
            "with genuine interest", 
            "with thoughtful reflection",
            "with warm engagement",
            "with open wonder",
            "with authentic connection",
            "with mindful presence",
            "with gentle inquiry"
        ]
        
        random_starter = random.choice(conversation_starters)
        enhanced_instruction = f"{instruction} Approach this {random_starter}."
        
        debug_print(f"Attempting to generate initial message with Gemini using enhanced prompt. Starter: {random_starter}")
        
        response = await asyncio.to_thread(
            current_gemini_model.generate_content,
            contents=[{'role': 'user', 'parts': [enhanced_instruction]}],
            generation_config={
                "temperature": 1.0,  # Higher temperature for more creativity and variety
                "top_p": 0.95,       # Nucleus sampling for diverse but coherent responses
                "top_k": 40,         # Limit to top 40 tokens for good variety without randomness
                "max_output_tokens": 150,  # Keep it concise
                "candidate_count": 1,      # Generate one response
            }
        )
        
        if response and response.text:
            initial_message = response.text.strip()
            debug_print(f"Generated initial message: {initial_message}")
            
            # Log token usage for initial message generation
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                response_tokens = getattr(usage, 'candidates_token_count', 0)
                total_tokens = getattr(usage, 'total_token_count', 0)
                debug_print(f"Initial message token usage: {prompt_tokens:,} prompt + {response_tokens:,} response = {total_tokens:,} total")

    except Exception as e:
        debug_print(f"Error generating initial message: {e}\\n{traceback.format_exc()}")
        # Fall back to default message on error, don't raise exception

    return InitialMessageOutput(message=initial_message, conversation_id=conversation_id)

@router.post("/message", response_model=ChatMessageOutput)
async def handle_chat_message(chat_input: ChatMessageInput):
    debug_print("--- handle_chat_message invoked (Gemini) ---")
    user_message = chat_input.message
    conversation_id = chat_input.conversation_id or str(uuid.uuid4())
    message_history = chat_input.history or []
    
    debug_print(f"User message: {user_message}")
    debug_print(f"Conversation ID: {conversation_id}")
    debug_print(f"Message history length: {len(message_history)}")
    
    multi_source_data = {}
    try:
        db_manager = get_database_manager()
        cms_db_config = db_manager.get_database("cms") # Assuming 'cms' is the nickname
        if cms_db_config:
            cms_data = read_markdown_files_with_registry(cms_db_config)
            multi_source_data['cms'] = cms_data
            debug_print(f"Loaded {len(cms_data)} CMS entries.")
        else:
            debug_print("CMS database config not found.")
    except Exception as e:
        debug_print(f"Error reading content files: {e}\\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to read content entries.")

    system_prompt_str = create_system_prompt(multi_source_data)
    if not system_prompt_str:
        debug_print("Warning: create_system_prompt returned an empty string. Using fallback.")
        system_prompt_str = "You are a helpful AI."

    ai_reply_content = "Sorry, I couldn't process that with Gemini." 

    if not gemini_client_initialized:
        debug_print("Gemini client not available (check GOOGLE_API_KEY and configuration).")
        raise HTTPException(status_code=503, detail="AI Service (Gemini) is not configured.")

    try:
        # For Gemini, the system prompt is part of the model initialization.
        # We re-initialize the model here with the specific system_prompt.
        # This is how it's handled in maia/chat/interface.py for the CLI.
        current_gemini_model = genai.GenerativeModel(
            model_name=gemini_model_name,
            system_instruction=system_prompt_str 
        )
        
        # Build conversation history for Gemini
        # Convert our message history to Gemini format
        gemini_messages = []
        for msg in message_history:
            role = 'user' if msg.role == 'user' else 'model'  # Gemini uses 'model' instead of 'assistant'
            gemini_messages.append({'role': role, 'parts': [msg.content]})
        
        # Add the current user message
        gemini_messages.append({'role': 'user', 'parts': [user_message]})
        
        debug_print(f"Attempting to call Gemini with {len(gemini_messages)} messages. System prompt ({len(system_prompt_str)} chars). Current user message: {user_message[:100]}...")
        
        response = await asyncio.to_thread(
            current_gemini_model.generate_content,
            contents=gemini_messages,
            generation_config={
                "temperature": 0.7, # Adjust as needed
                # "max_output_tokens": 8192 # Gemini 1.5 Pro default, can be set if needed
            }
        )
        
        ai_reply_content = response.text
        debug_print(f"Got reply from Gemini: {ai_reply_content[:100]}...")
        
        # Extract token usage information
        token_usage_data = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            prompt_tokens = getattr(usage, 'prompt_token_count', 0)
            response_tokens = getattr(usage, 'candidates_token_count', 0)
            total_tokens = getattr(usage, 'total_token_count', 0)
            
            # Calculate cost using centralized function with appropriate model tier
            from promaia.utils.ai import calculate_ai_cost
            model_tier = "gemini-2.5-pro-short" if prompt_tokens <= 128000 else "gemini-2.5-pro-long"
            cost_data = calculate_ai_cost(prompt_tokens, response_tokens, model_tier)
            total_cost = cost_data["total_cost"]
            
            # Import TokenUsage here to avoid circular imports
            from promaia.web.models import TokenUsage
            token_usage_data = TokenUsage(
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens,
                cost=total_cost,
                model="Gemini 2.5 Pro"
            )
            debug_print(f"Token usage: {prompt_tokens:,} prompt + {response_tokens:,} response = {total_tokens:,} total, cost: ${total_cost:.6f}")
        else:
            debug_print("No usage_metadata found in Gemini response")

    except HTTPException as e: 
        raise e 
    except Exception as e:
        error_detail_msg = f"General error calling Gemini: {e}"
        debug_print(error_detail_msg)
        debug_print(traceback.format_exc())
        # Check for specific Gemini API errors if possible from 'e'
        # For example, if e.args contains specific error codes or messages from Gemini
        # This helps differentiate from general Python exceptions.
        # If response object exists and has prompt_feedback:
        if 'response' in locals() and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            debug_print(f"Gemini Prompt Feedback: {response.prompt_feedback}")
            if response.prompt_feedback.block_reason:
                 error_detail_msg = f"Gemini API Error: Blocked - {response.prompt_feedback.block_reason}. {error_detail_msg}"
                 # Potentially raise a more specific HTTP error if blocked for safety/policy
                 # raise HTTPException(status_code=400, detail=f"Request blocked by AI for safety/policy reasons.")
        
        raise HTTPException(status_code=500, detail=error_detail_msg)
    
    if not ai_reply_content and not (hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason):
        debug_print("Gemini call returned empty content, and not due to a block reason.")
        raise HTTPException(status_code=500, detail="AI service (Gemini) failed to generate a response (empty content).")

    return ChatMessageOutput(
        reply=ai_reply_content, 
        conversation_id=conversation_id,
        model_used="gemini",
        token_usage=token_usage_data
    )

# You can add other chat-related endpoints here if needed. 