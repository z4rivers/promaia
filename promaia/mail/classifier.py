"""
Email Classifier - AI-based email classification.

Determines if an email:
- Pertains to the user
- Is spam/promotional
- Requires a response
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EmailClassifier:
    """AI-based email classification using existing chat infrastructure."""
    
    CLASSIFICATION_PROMPT = """You are an email classifier. Analyze this email and determine:
1. Does this pertain to the user? (Is it relevant to them personally/professionally?)
2. Is this spam, an ad, promotion, or phishing attempt?
3. Does this require a response from the user?

Email Details:
From: {from_addr}
Subject: {subject}
Date: {date}
Body:
{body}

Thread Context (if part of a conversation):
{thread_context}

Respond with ONLY valid JSON in this exact format:
{{
    "pertains_to_me": true/false,
    "is_spam": true/false,
    "requires_response": true/false,
    "reasoning": "Brief explanation of your classification"
}}"""
    
    def __init__(self):
        """Initialize classifier with AI client."""
        # Will use the existing AI client infrastructure
        self.ai_client = None
        self.model_type = None
    
    def _get_ai_client(self):
        """Get AI client from existing chat infrastructure."""
        if self.ai_client is not None:
            return self.ai_client
        
        import os
        from anthropic import Anthropic
        from openai import OpenAI
        
        # Try Anthropic first (preferred)
        if os.getenv("ANTHROPIC_API_KEY"):
            self.ai_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model_type = "anthropic"
            logger.info("Using Anthropic for email classification")
            return self.ai_client
        
        # Fall back to OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model_type = "openai"
            logger.info("Using OpenAI for email classification")
            return self.ai_client
        
        raise ValueError("No AI API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
    
    async def classify(self, email_thread: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an email thread.
        
        Args:
            email_thread: Dict containing email data (from, subject, body, etc.)
            
        Returns:
            Dict with classification results:
            {
                "pertains_to_me": bool,
                "is_spam": bool,
                "requires_response": bool,
                "reasoning": str
            }
        """
        try:
            # Extract email data
            from_addr = email_thread.get('from', 'Unknown')
            subject = email_thread.get('subject', 'No Subject')
            date = email_thread.get('date', 'Unknown')
            body = email_thread.get('conversation_body', '') or email_thread.get('body', '')
            thread_context = email_thread.get('thread_context', 'No previous context')
            
            # Truncate body if too long (keep first 1000 chars)
            if len(body) > 1000:
                body = body[:1000] + "\n[... truncated ...]"
            
            # Build prompt
            prompt = self.CLASSIFICATION_PROMPT.format(
                from_addr=from_addr,
                subject=subject,
                date=date,
                body=body,
                thread_context=thread_context
            )
            
            # Get AI client
            client = self._get_ai_client()
            
            # Call AI based on model type
            if self.model_type == "anthropic":
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_text = response.content[0].text
            
            elif self.model_type == "openai":
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_text = response.choices[0].message.content
            
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
            
            # Parse JSON response
            # Extract JSON from response (it might have markdown code blocks)
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith('```'):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()
            
            classification = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['pertains_to_me', 'is_spam', 'requires_response', 'reasoning']
            for field in required_fields:
                if field not in classification:
                    raise ValueError(f"Missing required field in classification: {field}")
            
            logger.info(
                f"Classified email from {from_addr}: "
                f"pertains={classification['pertains_to_me']}, "
                f"spam={classification['is_spam']}, "
                f"requires_response={classification['requires_response']}"
            )
            
            return classification
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse classification JSON: {e}")
            logger.error(f"Response was: {response_text}")
            # Return conservative defaults
            return {
                "pertains_to_me": True,
                "is_spam": False,
                "requires_response": True,
                "reasoning": f"Classification failed (JSON parse error), defaulting to requiring response"
            }
        
        except Exception as e:
            logger.error(f"❌ Classification failed: {e}")
            # Return conservative defaults (assume it needs attention)
            return {
                "pertains_to_me": True,
                "is_spam": False,
                "requires_response": True,
                "reasoning": f"Classification error: {str(e)}, defaulting to requiring response"
            }
    
    def should_generate_draft(self, classification: Dict[str, Any]) -> bool:
        """
        Determine if we should generate a draft based on classification.
        
        Args:
            classification: Result from classify()
            
        Returns:
            True if we should generate a draft
        """
        return (
            classification.get('pertains_to_me', False) and
            not classification.get('is_spam', False) and
            classification.get('requires_response', False)
        )

