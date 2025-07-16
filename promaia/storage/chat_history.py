"""
Chat history management for maia chat threads.
Stores and retrieves the last 10 chat conversations for easy re-execution.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class ChatThread:
    """Represents a chat thread/conversation."""
    id: str
    name: str
    messages: List[Dict[str, str]]
    context: Dict[str, Any]
    last_accessed: str
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatThread':
        """Create from dictionary for JSON deserialization."""
        return cls(**data)
    
    def __str__(self) -> str:
        """Human-readable representation of the thread."""
        # Format: "Thread Name (Jan 15, 14:30)"
        if self.last_accessed:
            try:
                dt = datetime.fromisoformat(self.last_accessed)
                time_str = dt.strftime("%b %d, %H:%M")
                return f"{self.name} ({time_str})"
            except:
                pass
        
        return self.name

class ChatHistoryManager:
    """Manages chat history threads."""
    
    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self.history_file = os.path.expanduser("~/.maia_chat_history.json")
    
    def _load_history(self) -> List[ChatThread]:
        """Load chat threads from file."""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [ChatThread.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            # If file is corrupted, start fresh
            return []
    
    def _save_history(self, threads: List[ChatThread]) -> None:
        """Save chat threads to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([item.to_dict() for item in threads], f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save chat history: {e}")
    
    def _generate_thread_name(self, messages: List[Dict[str, str]]) -> str:
        """Generate a thread name using AI summarization."""
        # For now, use first user message truncated (AI summarization to be added)
        for msg in messages:
            if msg.get('role') == 'user':
                content = msg.get('content', '').strip()
                if content:
                    # Truncate to ~40 characters for display
                    if len(content) > 40:
                        return content[:37] + "..."
                    return content
        
        # Fallback to timestamp
        return f"Chat - {datetime.now().strftime('%b %d, %H:%M')}"
    
    def save_thread(self, 
                   messages: List[Dict[str, str]], 
                   context: Dict[str, Any],
                   thread_name: Optional[str] = None) -> str:
        """Save a new chat thread."""
        thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()
        
        # Generate name if not provided
        if not thread_name:
            thread_name = self._generate_thread_name(messages)
        
        new_thread = ChatThread(
            id=thread_id,
            name=thread_name,
            messages=messages.copy(),
            context=context.copy(),
            last_accessed=timestamp,
            created_at=timestamp
        )
        
        threads = self._load_history()
        
        # Add new thread at the beginning (most recent)
        threads.insert(0, new_thread)
        
        # Keep only max_entries
        threads = threads[:self.max_entries]
        
        self._save_history(threads)
        return thread_id
    
    def is_natural_language_thread(self, thread: ChatThread) -> bool:
        """Check if a thread was created with a natural language query."""
        return thread.context.get('natural_language_prompt') is not None
    
    def get_thread_query_command(self, thread: ChatThread) -> str:
        """Get the command string for a thread, prioritizing natural language format."""
        context = thread.context
        
        # Check if this was a natural language thread
        if context.get('natural_language_prompt'):
            return f"maia chat -nl {context['natural_language_prompt']}"
        
        # Fall back to traditional format
        return context.get('query_command', 'maia chat')
    
    def get_threads(self) -> List[ChatThread]:
        """Get list of chat threads ordered by last_accessed."""
        threads = self._load_history()
        # Sort by last_accessed (most recent first)
        threads.sort(key=lambda t: t.last_accessed, reverse=True)
        return threads
    
    def get_thread(self, thread_id: str) -> Optional[ChatThread]:
        """Get a specific thread by ID."""
        threads = self._load_history()
        for thread in threads:
            if thread.id == thread_id:
                return thread
        return None
    
    def update_thread_access(self, thread_id: str) -> None:
        """Update the last_accessed timestamp for a thread."""
        threads = self._load_history()
        for thread in threads:
            if thread.id == thread_id:
                thread.last_accessed = datetime.now().isoformat()
                self._save_history(threads)
                break
    
    def update_thread(self, thread_id: str, messages: List[Dict[str, str]], 
                     context: Dict[str, Any], thread_name: Optional[str] = None) -> bool:
        """Update an existing thread with new messages and context."""
        threads = self._load_history()
        for thread in threads:
            if thread.id == thread_id:
                # Update the thread
                thread.messages = messages.copy()
                thread.context = context.copy()
                thread.last_accessed = datetime.now().isoformat()
                
                # Update name if provided
                if thread_name:
                    thread.name = thread_name
                
                self._save_history(threads)
                return True
        return False
    
    def clear_history(self) -> None:
        """Clear all chat history."""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
    
    def clean_duplicates(self) -> int:
        """Remove duplicate threads with the same name, keeping the most recent."""
        threads = self._load_history()
        if len(threads) <= 1:
            return 0
        
        # Group threads by name
        name_groups = {}
        for thread in threads:
            if thread.name not in name_groups:
                name_groups[thread.name] = []
            name_groups[thread.name].append(thread)
        
        # Keep only the most recent thread for each name
        cleaned_threads = []
        removed_count = 0
        
        for name, thread_list in name_groups.items():
            if len(thread_list) > 1:
                # Sort by last_accessed (most recent first)
                thread_list.sort(key=lambda t: t.last_accessed, reverse=True)
                cleaned_threads.append(thread_list[0])  # Keep most recent
                removed_count += len(thread_list) - 1
            else:
                cleaned_threads.append(thread_list[0])
        
        # Sort the cleaned threads by last_accessed
        cleaned_threads.sort(key=lambda t: t.last_accessed, reverse=True)
        
        if removed_count > 0:
            self._save_history(cleaned_threads)
        
        return removed_count
    
    def has_history(self) -> bool:
        """Check if there are any saved threads."""
        return len(self.get_threads()) > 0 