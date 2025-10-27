"""
Artifact management for maia chat.

Provides Claude-style inline artifacts for generated content like emails,
blog posts, documents, and code.
"""
import logging
import re
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class ArtifactManager:
    """Manages inline artifacts for maia chat (like Claude)."""
    
    def __init__(self):
        """Initialize artifact manager."""
        self.artifacts: Dict[int, Dict[str, any]] = {}  # artifact_id -> {content, type, version}
        self.current_number = 0
        self.last_artifact_id: Optional[int] = None  # Track most recent artifact for updates
    
    def should_create_artifact(self, user_input: str, ai_response: str) -> bool:
        """
        Determine if response should be rendered as artifact.
        
        Hybrid approach:
        1. Check for explicit keywords in user input
        2. Check for artifact tags in AI response
        
        Args:
            user_input: User's message
            ai_response: AI's response text
            
        Returns:
            True if response should be an artifact
        """
        # Explicit keywords in user input
        keywords = ['write a', 'write an', 'create a', 'draft a', 'compose', 'generate']
        content_types = ['email', 'blog', 'article', 'document', 'post', 'letter', 
                        'essay', 'story', 'script', 'code', 'function', 'class',
                        'summary', 'report', 'analysis', 'outline', 'plan', 'list',
                        'guide', 'tutorial', 'proposal', 'spec', 'contract']
        
        user_lower = user_input.lower()

        # Check for AI artifact tags FIRST (respect AI's decision)
        # Use regex to handle both simple and attributed artifact tags
        artifact_pattern = r'<artifact(?:\s+[^>]*)?>(.+?)</artifact>'
        if re.search(artifact_pattern, ai_response, re.DOTALL):
            logger.debug("Artifact triggered by AI tags")
            return True

        # Check for explicit "as an artifact" or "as artifact"
        if 'as an artifact' in user_lower or 'as artifact' in user_lower:
            logger.debug("Artifact triggered by explicit 'as artifact' phrase")
            return True

        # Check for keyword + content type combinations (fallback)
        for keyword in keywords:
            for content_type in content_types:
                if keyword in user_lower and content_type in user_lower:
                    logger.debug(f"Artifact triggered by keywords: '{keyword}' + '{content_type}'")
                    return True

        return False
    
    def should_update_artifact(self, user_input: str) -> bool:
        """
        Determine if user is asking to modify the last artifact.
        
        Args:
            user_input: User's message
            
        Returns:
            True if this is an artifact update request
        """
        if not self.last_artifact_id:
            return False
        
        # Update keywords
        update_phrases = [
            'make it', 'make that', 'change it', 'change that',
            'update it', 'update that', 'revise it', 'revise that',
            'shorter', 'longer', 'more formal', 'less formal',
            'add', 'remove', 'fix', 'improve'
        ]
        
        user_lower = user_input.lower()
        return any(phrase in user_lower for phrase in update_phrases)
    
    def extract_artifact_content(self, ai_response: str) -> Tuple[str, str]:
        """
        Extract artifact content from AI response.

        Handles both simple <artifact> tags and Claude's native format with attributes:
        - Simple: <artifact>content</artifact>
        - With attributes: <artifact identifier="..." type="..." title="...">content</artifact>

        Args:
            ai_response: AI's full response

        Returns:
            Tuple of (artifact_content, remaining_response)
        """
        # Use regex to match artifact tags with or without attributes
        # Pattern matches: <artifact [anything]> ... </artifact>
        artifact_pattern = r'<artifact(?:\s+[^>]*)?>(.+?)</artifact>'
        match = re.search(artifact_pattern, ai_response, re.DOTALL)

        if match:
            # Extract content between tags (group 1)
            artifact = match.group(1).strip()

            # Get text before artifact
            before = ai_response[:match.start()].strip()

            # Get text after artifact
            after = ai_response[match.end():].strip()

            # Combine before and after commentary
            commentary = (before + "\n\n" + after).strip() if before or after else ""

            return artifact, commentary
        else:
            # No artifact tags found - entire response is the artifact
            return ai_response, ""
    
    def create_artifact(self, content: str, artifact_type: str = "text") -> int:
        """
        Create new artifact and return its ID.
        
        Args:
            content: Artifact content
            artifact_type: Type of artifact (text, code, etc.)
            
        Returns:
            Artifact ID
        """
        self.current_number += 1
        self.artifacts[self.current_number] = {
            'content': content,
            'type': artifact_type,
            'version': 1
        }
        self.last_artifact_id = self.current_number
        logger.info(f"Created artifact #{self.current_number}")
        return self.current_number
    
    def update_artifact(self, artifact_id: int, new_content: str) -> None:
        """
        Update existing artifact.
        
        Args:
            artifact_id: ID of artifact to update
            new_content: New content
        """
        if artifact_id in self.artifacts:
            self.artifacts[artifact_id]['content'] = new_content
            self.artifacts[artifact_id]['version'] += 1
            self.last_artifact_id = artifact_id
            logger.info(f"Updated artifact #{artifact_id} to version {self.artifacts[artifact_id]['version']}")
        else:
            logger.warning(f"Attempted to update non-existent artifact #{artifact_id}")
    
    def get_artifact(self, artifact_id: int) -> Optional[Dict[str, any]]:
        """
        Get artifact by ID.
        
        Args:
            artifact_id: Artifact ID
            
        Returns:
            Artifact dict or None if not found
        """
        return self.artifacts.get(artifact_id)
    
    def list_artifacts(self) -> list:
        """
        Get list of all artifacts.
        
        Returns:
            List of (artifact_id, preview) tuples
        """
        result = []
        for artifact_id in sorted(self.artifacts.keys()):
            artifact = self.artifacts[artifact_id]
            preview = artifact['content'][:60] + "..." if len(artifact['content']) > 60 else artifact['content']
            result.append((artifact_id, preview, artifact['version']))
        return result
    
    def render_artifact(self, artifact_id: int, content: str = None) -> str:
        """
        Render artifact with clean separators (copy-friendly).
        
        Args:
            artifact_id: Artifact ID
            content: Optional content override (uses stored content if None)
            
        Returns:
            Formatted artifact string
        """
        if content is None:
            if artifact_id not in self.artifacts:
                return f"Artifact #{artifact_id} not found"
            content = self.artifacts[artifact_id]['content']
        
        return f"""Artifact #{artifact_id}
─────────────────────────────────────────────────────────────────

{content}

─────────────────────────────────────────────────────────────────"""

