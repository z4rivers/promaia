"""
Response Generator - Generates email responses using AI with learning.

Uses learned patterns from previous successful responses to match user's style.
"""
import logging
import re
from typing import Dict, Any, Optional
import os
from promaia.utils.timezone_utils import now_utc

from promaia.mail.learning_system import EmailResponseLearningSystem
from promaia.mail.context_builder import ResponseContext

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates email responses using AI with learning."""
    
    RESPONSE_PROMPT_TEMPLATE = """{user_persona}

You are writing an email response based on the following context.

{learned_patterns}

**Thread History:**
{thread_history}

**Relevant Context from User's Knowledge Base:**
{context_documents}

**Latest Message to Respond To:**
From: {from_addr}
Subject: {subject}
Date: {date}

Write a professional, concise email response that:
- Uses information from the context when relevant
- Matches the tone and style of previous responses (if examples provided above) and the user persona.
- Is clear and actionable
- Is appropriately concise unless detail is needed
- Maintains the conversation flow

IMPORTANT: Write in natural flowing paragraphs. Do NOT add hard line breaks within paragraphs. Let the email client handle text wrapping. Only use line breaks between distinct paragraphs or list items.

Return ONLY the email body text, ready to send. Do not include subject line or headers."""
    
    def __init__(self):
        """Initialize response generator."""
        self.learning_system = EmailResponseLearningSystem()
        self.ai_client = None
        self.model_type = None
        self.user_persona = self._load_user_persona()

    def _load_user_persona(self):
        """Loads the user's persona from the prompt file."""
        prompt_path = "prompts/maia_mail_prompt.md"
        default_persona = "You are an AI assistant writing an email on behalf of the user. Your goal is to be helpful, professional, and concise."
        
        if not os.path.exists(prompt_path):
            logger.warning(f"'{prompt_path}' not found. Using default persona.")
            return default_persona
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                persona = f.read()
                logger.info(f"Loaded user persona from '{prompt_path}'")
                return persona
        except Exception as e:
            logger.error(f"Failed to load persona from '{prompt_path}': {e}")
            return default_persona

    def _save_mail_context_log(self, prompt_content: str, log_type: str):
        """
        Save the prompt content to a log file for debugging.
        
        Args:
            prompt_content: The full prompt sent to the AI.
            log_type: Type of log (e.g., 'initial_draft', 'refinement').
        """
        try:
            log_dir = "mail-context-logs"
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = now_utc().strftime("%Y%m%d-%H%M%S")
            filename = f"{log_dir}/{timestamp}_{log_type}_prompt.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                header = f"=== MAIA MAIL - {log_type.upper()} PROMPT ===\n"
                f.write(header)
                f.write(prompt_content)
                
            logger.info(f"Saved mail context log to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save mail context log: {e}")
    
    def _format_email_body(self, text: str) -> str:
        """
        Remove unnecessary hard line breaks from email body while preserving intentional formatting.
        
        This fixes the issue where AI generates text with hard wraps at ~70-80 characters,
        which looks bad in modern email clients. We want continuous paragraphs that wrap naturally.
        
        Rules:
        - Remove single line breaks within paragraphs (hard wraps)
        - Preserve double line breaks (paragraph separators)
        - Remove hard breaks within list items
        - Preserve line breaks between list items
        - Preserve intentional formatting like signatures
        """
        if not text:
            return text
        
        # Split into lines
        lines = text.split('\n')
        formatted_lines = []
        current_paragraph = []
        in_list_item = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Empty line = paragraph break
            if not stripped:
                # Flush current paragraph
                if current_paragraph:
                    formatted_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                in_list_item = False
                # Add paragraph break (single empty line)
                if formatted_lines and formatted_lines[-1] != '':
                    formatted_lines.append('')
                continue
            
            # Check if this is a list item start (numbered or bulleted)
            is_list_start = re.match(r'^\d+[\.\)]\s', stripped) or re.match(r'^[-\*•]\s', stripped)
            
            if is_list_start:
                # Flush previous paragraph/list item
                if current_paragraph:
                    formatted_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                # Start new list item
                current_paragraph = [stripped]
                in_list_item = True
                continue
            
            # Salutations and closings - preserve as separate lines
            if stripped in ['Hi!', 'Hello!', 'Thanks!', 'Best!', 'Cheers!', 'Best regards,', 'Thanks,', 'Cheers,', 'Best,']:
                # Flush current paragraph
                if current_paragraph:
                    formatted_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                formatted_lines.append(stripped)
                in_list_item = False
                continue
            
            # Check if this looks like a signature line
            if len(stripped) < 40 and i == len(lines) - 1:
                # Last line and short - likely a signature
                if current_paragraph:
                    formatted_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                formatted_lines.append(stripped)
                continue
            
            # If we're in a list item or regular paragraph, add to current
            current_paragraph.append(stripped)
        
        # Flush any remaining paragraph
        if current_paragraph:
            formatted_lines.append(' '.join(current_paragraph))
        
        # Join with single newlines (paragraphs separated by blank lines)
        result = '\n'.join(formatted_lines)
        
        # Clean up any excessive blank lines (max 1 blank line between paragraphs)
        result = re.sub(r'\n\n\n+', '\n\n', result)
        
        return result.strip()
    
    def _get_ai_client(self):
        """Get AI client from existing infrastructure."""
        if self.ai_client is not None:
            return self.ai_client
        
        import os
        from anthropic import Anthropic
        from openai import OpenAI
        
        # Try Anthropic first (preferred)
        if os.getenv("ANTHROPIC_API_KEY"):
            self.ai_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model_type = "anthropic"
            logger.info("Using Anthropic for response generation")
            return self.ai_client
        
        # Fall back to OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model_type = "openai"
            logger.info("Using OpenAI for response generation")
            return self.ai_client
        
        raise ValueError("No AI API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
    
    async def generate_response(
        self,
        email_thread: Dict[str, Any],
        context: ResponseContext,
    ) -> Dict[str, Any]:
        """
        Generate email response with learned patterns.
        
        Args:
            email_thread: Email thread data
            context: ResponseContext with thread history and relevant docs
            
        Returns:
            Dict with 'body' (response text), 'subject', 'model' keys
        """
        try:
            # Get learned patterns for prompt
            learned_patterns = self.learning_system.get_patterns_for_prompt(limit=10)
            
            # Extract email details
            from_addr = email_thread.get('from', 'Unknown')
            subject = email_thread.get('subject', 'No Subject')
            date = email_thread.get('date', 'Unknown')
            
            # Build full prompt
            prompt = self.RESPONSE_PROMPT_TEMPLATE.format(
                user_persona=self.user_persona,
                learned_patterns=learned_patterns,
                thread_history=context.thread_history,
                context_documents=context.relevant_docs_text,
                from_addr=from_addr,
                subject=subject,
                date=date
            )
            
            # Save prompt for debugging
            self._save_mail_context_log(prompt, "initial_draft")
            
            # Get AI client
            client = self._get_ai_client()
            
            # Generate response based on model type
            if self.model_type == "anthropic":
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_body = response.content[0].text.strip()
                model_used = "claude-sonnet-4-20250514"
            
            elif self.model_type == "openai":
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_body = response.choices[0].message.content.strip()
                model_used = "gpt-4o"
            
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
            
            # Format the email body to remove hard line breaks
            response_body = self._format_email_body(response_body)
            
            # Prepare response subject (add RE: if not present)
            response_subject = subject
            if not response_subject.upper().startswith('RE:'):
                response_subject = f"RE: {response_subject}"
            
            logger.info(f"✅ Generated response ({len(response_body.split())} words)")
            
            return {
                'body': response_body,
                'subject': response_subject,
                'model': model_used,
                'prompt': prompt  # Store for debugging/refinement
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate response: {e}")
            raise
    
    async def refine_response(
        self,
        current_draft: str,
        user_feedback: str,
        email_thread: Dict[str, Any],
        context: ResponseContext
    ) -> str:
        """
        Refine an existing draft based on user feedback.
        
        Args:
            current_draft: The current draft text
            user_feedback: User's refinement request
            email_thread: Original email thread data
            context: ResponseContext
            
        Returns:
            Refined draft text
        """
        try:

            # Get email body for context
            email_body = email_thread.get('conversation_body') or email_thread.get('body', '')
            
            # Build refinement prompt
            refinement_prompt = f"""{self.user_persona}

You are revising an email draft based on user feedback.

{f"You previously generated this email draft:\n\n{current_draft}\n\n" if current_draft else "You are generating a NEW draft for this email.\n\n"}The user has requested a change:
"{user_feedback}"

Original email context:
From: {email_thread.get('from')}
Subject: {email_thread.get('subject')}

Email thread/body:
{email_body}

Relevant context from knowledge base:
{context.relevant_docs_text if context.relevant_docs_text else "No additional context available"}

Please {"revise the draft" if current_draft else "generate a response"} according to the user's feedback, the user persona, and the original context, while maintaining:
- Professional tone
- Clarity and conciseness
- Appropriate context from the conversation

IMPORTANT: Write in natural flowing paragraphs. Do NOT add hard line breaks within paragraphs. Let the email client handle text wrapping. Only use line breaks between distinct paragraphs or list items.

Return ONLY the {"revised" if current_draft else ""} email body text."""
            
            # Save refinement prompt for debugging
            self._save_mail_context_log(refinement_prompt, "refinement")

            # Get AI client
            client = self._get_ai_client()
            
            # Generate refined response
            if self.model_type == "anthropic":
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": refinement_prompt
                    }]
                )
                refined_body = response.content[0].text.strip()
            
            elif self.model_type == "openai":
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": refinement_prompt
                    }]
                )
                refined_body = response.choices[0].message.content.strip()
            
            # Format the refined body to remove hard line breaks
            refined_body = self._format_email_body(refined_body)
            
            logger.info(f"✅ Refined response based on feedback")
            
            return refined_body
            
        except Exception as e:
            logger.error(f"❌ Failed to refine response: {e}")
            # Return original on error
            return current_draft

