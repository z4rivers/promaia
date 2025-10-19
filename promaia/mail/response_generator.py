"""
Response Generator - Generates email responses using AI with learning.

Uses learned patterns from previous successful responses to match user's style.
"""
import logging
import re
from typing import Dict, Any, Optional

from promaia.mail.learning_system import EmailResponseLearningSystem
from promaia.mail.context_builder import ResponseContext

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates email responses using AI with learning."""
    
    RESPONSE_PROMPT_TEMPLATE = """You are writing an email response on behalf of the user.

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
- Matches the tone and style of previous responses (if examples provided above)
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
                learned_patterns=learned_patterns,
                thread_history=context.thread_history,
                context_documents=context.relevant_docs_text,
                from_addr=from_addr,
                subject=subject,
                date=date
            )
            
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
            # Build refinement prompt
            refinement_prompt = f"""You previously generated this email draft:

{current_draft}

The user has requested a change:
"{user_feedback}"

Original email context:
From: {email_thread.get('from')}
Subject: {email_thread.get('subject')}

Please revise the draft according to the user's feedback while maintaining:
- Professional tone
- Clarity and conciseness
- Appropriate context from the conversation

IMPORTANT: Write in natural flowing paragraphs. Do NOT add hard line breaks within paragraphs. Let the email client handle text wrapping. Only use line breaks between distinct paragraphs or list items.

Return ONLY the revised email body text."""
            
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

