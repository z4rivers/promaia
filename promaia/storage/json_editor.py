"""
JSON Editor for Notion Data

This module provides safe editing capabilities for local Notion JSON files,
including validation, change tracking, and preparation for sync back to Notion.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import copy

from promaia.config.databases import get_database_manager

@dataclass
class EditChange:
    """Represents a change made to a JSON file"""
    timestamp: str
    change_type: str  # 'property_update', 'content_add', 'content_update', 'content_delete'
    location: str     # Path to the changed element (e.g., 'properties.Name.title.0.text.content')
    old_value: Any
    new_value: Any
    description: str

class NotionJSONEditor:
    """Safe editor for Notion JSON files with validation and change tracking"""
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.config = get_database_manager()
        self.workspace_root = workspace_root or os.getcwd()
        self.data_dir = os.path.join(self.workspace_root, "data", "json")
        self.changes_log = []
        
    def _get_content_type_dir(self, content_type: str) -> str:
        """Get the directory path for a specific content type"""
        return os.path.join(self.data_dir, content_type)
    
    def _validate_notion_structure(self, data: Dict[str, Any]) -> bool:
        """Validate that the JSON maintains proper Notion structure"""
        required_keys = ['page_id', 'title', 'saved_at', 'content_type', 'notion_data']
        
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key: {key}")
        
        notion_data = data['notion_data']
        if 'properties' not in notion_data:
            raise ValueError("Missing 'properties' in notion_data")
        
        return True
    
    def _log_change(self, change_type: str, location: str, old_value: Any, 
                   new_value: Any, description: str = ""):
        """Log a change for tracking"""
        change = EditChange(
            timestamp=datetime.now().isoformat(),
            change_type=change_type,
            location=location,
            old_value=old_value,
            new_value=new_value,
            description=description
        )
        self.changes_log.append(change)
    
    def find_similar_page_ids(self, content_type: str, page_id: str) -> List[str]:
        """Find page IDs similar to the given one (for typo correction)"""
        content_dir = self._get_content_type_dir(content_type)
        
        if not os.path.exists(content_dir):
            return []
        
        similar_ids = []
        
        try:
            for filename in os.listdir(content_dir):
                if filename.endswith('.json') and 'backup' not in filename:
                    filepath = os.path.join(content_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        internal_page_id = data.get('page_id', '')
                        if internal_page_id:
                            # Calculate similarity - check for common prefix/suffix patterns
                            if len(internal_page_id) == len(page_id):
                                # Same length - check character differences
                                differences = sum(c1 != c2 for c1, c2 in zip(internal_page_id, page_id))
                                if differences <= 3:  # Allow up to 3 character differences
                                    similar_ids.append(internal_page_id)
                            elif abs(len(internal_page_id) - len(page_id)) <= 2:
                                # Similar length - check substring overlap
                                overlap = len(set(internal_page_id) & set(page_id))
                                if overlap >= len(page_id) * 0.8:  # 80% character overlap
                                    similar_ids.append(internal_page_id)
                                    
                    except Exception:
                        continue
                        
        except Exception:
            pass
            
        return similar_ids[:5]  # Return top 5 matches
    
    def load_page(self, content_type: str, page_id: str) -> Optional[Dict[str, Any]]:
        """Load a page by content type and page ID"""
        content_dir = self._get_content_type_dir(content_type)
        
        if not os.path.exists(content_dir):
            print(f"Content directory does not exist: {content_dir}")
            return None
        
        # First, try to find the exact file by reading all JSON files
        # This is more reliable than filename matching
        found_files = []
        
        try:
            for filename in os.listdir(content_dir):
                if filename.endswith('.json') and 'backup' not in filename:
                    filepath = os.path.join(content_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        internal_page_id = data.get('page_id')
                        if internal_page_id == page_id:
                            return data
                        elif page_id in filename:
                            # Keep track of potential matches by filename
                            found_files.append((filename, filepath))
                            
                    except Exception as e:
                        print(f"Error reading JSON file {filepath}: {e}")
                        continue
            
            # If no exact match found, try the filename matches
            for filename, filepath in found_files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    internal_page_id = data.get('page_id')
                    if internal_page_id == page_id:
                        return data
                        
                except Exception as e:
                    print(f"Error loading potential match {filepath}: {e}")
                    continue
            
            # If still no match, provide helpful debug info
            all_files = [f for f in os.listdir(content_dir) if f.endswith('.json') and 'backup' not in f]
            print(f"Page not found: {page_id} in {content_type}")
            print(f"Directory: {content_dir}")
            print(f"Available files: {len(all_files)}")
            
            # Check for similar page IDs (typo correction)
            similar_ids = self.find_similar_page_ids(content_type, page_id)
            if similar_ids:
                print(f"Did you mean one of these similar page IDs?")
                for similar_id in similar_ids:
                    print(f"  - {similar_id}")
            
            if len(all_files) <= 10:
                print("All available files:")
                for f in all_files:
                    print(f"  - {f}")
            else:
                print(f"First few files: {all_files[0]} ... (and {len(all_files)-1} more)")
            
            return None
            
        except Exception as e:
            print(f"Error accessing directory {content_dir}: {e}")
            return None
    
    def save_page(self, data: Dict[str, Any], backup: bool = True) -> str:
        """Save a page back to its JSON file"""
        self._validate_notion_structure(data)
        
        content_type = data['content_type']
        page_id = data['page_id']
        title = data['title']
        
        # Generate filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title} {page_id}.json"
        filepath = os.path.join(self._get_content_type_dir(content_type), filename)
        
        # Create backup if requested
        if backup and os.path.exists(filepath):
            backup_path = f"{filepath}.backup.{int(datetime.now().timestamp())}"
            os.rename(filepath, backup_path)
        
        # Update saved_at timestamp
        data['saved_at'] = datetime.now().isoformat()
        
        # Save the file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def update_title(self, data: Dict[str, Any], new_title: str) -> Dict[str, Any]:
        """Update the title of a page"""
        old_title = data['title']
        
        # Update the wrapper title
        data['title'] = new_title
        
        # Update the Notion properties title
        if 'Name' in data['notion_data']['properties']:
            name_prop = data['notion_data']['properties']['Name']
            if name_prop.get('type') == 'title' and 'title' in name_prop:
                old_notion_title = name_prop['title'][0]['text']['content'] if name_prop['title'] else ""
                name_prop['title'] = [{
                    "type": "text",
                    "text": {
                        "content": new_title,
                        "link": None
                    },
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default"
                    },
                    "plain_text": new_title,
                    "href": None
                }]
                
                self._log_change(
                    "property_update",
                    "properties.Name.title.0.text.content",
                    old_notion_title,
                    new_title,
                    f"Updated title from '{old_title}' to '{new_title}'"
                )
        
        self._log_change(
            "property_update",
            "title",
            old_title,
            new_title,
            f"Updated page title from '{old_title}' to '{new_title}'"
        )
        
        return data
    
    def update_property(self, data: Dict[str, Any], property_name: str, 
                       new_value: Any, property_type: str = None) -> Dict[str, Any]:
        """Update a property in the Notion data"""
        properties = data['notion_data']['properties']
        
        if property_name not in properties:
            # If property doesn't exist, we need to know its type
            if not property_type:
                raise ValueError(f"Property '{property_name}' doesn't exist and no type specified")
            properties[property_name] = {"type": property_type}
        
        old_value = properties[property_name].get(property_type or properties[property_name]['type'])
        
        # Handle different property types
        prop_type = property_type or properties[property_name]['type']
        
        if prop_type == 'select':
            properties[property_name]['select'] = new_value
        elif prop_type == 'multi_select':
            properties[property_name]['multi_select'] = new_value
        elif prop_type == 'rich_text':
            properties[property_name]['rich_text'] = new_value
        elif prop_type == 'relation':
            properties[property_name]['relation'] = new_value
        else:
            properties[property_name][prop_type] = new_value
        
        self._log_change(
            "property_update",
            f"properties.{property_name}.{prop_type}",
            old_value,
            new_value,
            f"Updated property '{property_name}' ({prop_type})"
        )
        
        return data
    
    def add_content_block(self, data: Dict[str, Any], block_data: Dict[str, Any], 
                         position: int = -1) -> Dict[str, Any]:
        """Add a new content block to the page"""
        content = data['notion_data']['content']
        
        # Generate a new block ID (simplified version)
        import uuid
        block_data['id'] = str(uuid.uuid4())
        block_data['object'] = 'block'
        block_data['created_time'] = datetime.now().isoformat()
        block_data['last_edited_time'] = datetime.now().isoformat()
        
        if position == -1:
            content.append(block_data)
            position = len(content) - 1
        else:
            content.insert(position, block_data)
        
        self._log_change(
            "content_add",
            f"content[{position}]",
            None,
            block_data,
            f"Added new {block_data.get('type', 'unknown')} block at position {position}"
        )
        
        return data
    
    def update_content_block(self, data: Dict[str, Any], block_id: str, 
                           updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing content block"""
        content = data['notion_data']['content']
        
        for i, block in enumerate(content):
            if block.get('id') == block_id:
                old_block = copy.deepcopy(block)
                block.update(updates)
                block['last_edited_time'] = datetime.now().isoformat()
                
                self._log_change(
                    "content_update",
                    f"content[{i}]",
                    old_block,
                    block,
                    f"Updated content block {block_id}"
                )
                break
        else:
            raise ValueError(f"Block with ID {block_id} not found")
        
        return data
    
    def delete_content_block(self, data: Dict[str, Any], block_id: str) -> Dict[str, Any]:
        """Delete a content block"""
        content = data['notion_data']['content']
        
        for i, block in enumerate(content):
            if block.get('id') == block_id:
                old_block = content.pop(i)
                
                self._log_change(
                    "content_delete",
                    f"content[{i}]",
                    old_block,
                    None,
                    f"Deleted content block {block_id}"
                )
                break
        else:
            raise ValueError(f"Block with ID {block_id} not found")
        
        return data
    
    def get_changes_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all changes made"""
        return [
            {
                'timestamp': change.timestamp,
                'type': change.change_type,
                'location': change.location,
                'description': change.description,
                'old_value': str(change.old_value)[:100] if change.old_value else None,
                'new_value': str(change.new_value)[:100] if change.new_value else None
            }
            for change in self.changes_log
        ]
    
    def clear_changes_log(self):
        """Clear the changes log"""
        self.changes_log = []
    
    def create_paragraph_block(self, text: str, **annotations) -> Dict[str, Any]:
        """Helper to create a paragraph block"""
        return {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": text,
                        "link": None
                    },
                    "annotations": {
                        "bold": annotations.get('bold', False),
                        "italic": annotations.get('italic', False),
                        "strikethrough": annotations.get('strikethrough', False),
                        "underline": annotations.get('underline', False),
                        "code": annotations.get('code', False),
                        "color": annotations.get('color', 'default')
                    },
                    "plain_text": text,
                    "href": None
                }],
                "color": "default"
            }
        }
    
    def create_heading_block(self, text: str, level: int = 1) -> Dict[str, Any]:
        """Helper to create a heading block"""
        heading_type = f"heading_{level}"
        return {
            "type": heading_type,
            heading_type: {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": text,
                        "link": None
                    },
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default"
                    },
                    "plain_text": text,
                    "href": None
                }],
                "color": "default",
                "is_toggleable": False
            }
        }
    
    def create_bulleted_list_item(self, text: str) -> Dict[str, Any]:
        """Helper to create a bulleted list item"""
        return {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": text,
                        "link": None
                    },
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default"
                    },
                    "plain_text": text,
                    "href": None
                }],
                "color": "default"
            }
        } 