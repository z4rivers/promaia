"""
Resend Audiences API client for subscriber management.
"""
import os
import resend
from typing import List, Dict, Any, Optional
import time


class ResendAudiencesClient:
    """Client for managing contacts and audiences in Resend."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Resend Audiences client."""
        self.api_key = api_key or os.getenv("RESEND_API_KEY")
        if not self.api_key:
            raise ValueError("RESEND_API_KEY environment variable is required")
        
        # Set the API key for resend
        resend.api_key = self.api_key
    
    def create_audience(self, name: str) -> Dict[str, Any]:
        """
        Create a new audience in Resend.
        
        Args:
            name: Name of the audience
            
        Returns:
            Audience object
        """
        try:
            audience = resend.Audiences.create(name=name)
            print(f"✅ Created audience: {name} (ID: {audience.get('id')})")
            return audience
        except Exception as e:
            print(f"❌ Error creating audience: {str(e)}")
            raise
    
    def list_audiences(self) -> List[Dict[str, Any]]:
        """List all audiences."""
        try:
            audiences = resend.Audiences.list()
            return audiences.get("data", [])
        except Exception as e:
            print(f"❌ Error listing audiences: {str(e)}")
            return []
    
    def get_audience_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get audience by name."""
        audiences = self.list_audiences()
        for audience in audiences:
            if audience.get("name", "").lower() == name.lower():
                return audience
        return None
    
    def create_contact(self, audience_id: str, email: str, first_name: Optional[str] = None, 
                      last_name: Optional[str] = None, unsubscribed: bool = False) -> Dict[str, Any]:
        """
        Create a new contact in an audience.
        
        Args:
            audience_id: Audience ID
            email: Contact email
            first_name: Contact first name
            last_name: Contact last name
            unsubscribed: Whether contact is unsubscribed
            
        Returns:
            Contact object
        """
        try:
            contact_data = {
                "email": email,
                "audience_id": audience_id,
                "unsubscribed": unsubscribed
            }
            
            if first_name:
                contact_data["first_name"] = first_name
            if last_name:
                contact_data["last_name"] = last_name
            
            contact = resend.Contacts.create(**contact_data)
            return contact
        except Exception as e:
            # Don't print individual contact errors to avoid spam
            raise Exception(f"Error creating contact {email}: {str(e)}")
    
    def batch_create_contacts(self, audience_id: str, contacts: List[Dict[str, Any]], 
                             batch_size: int = 100) -> Dict[str, int]:
        """
        Create multiple contacts in batches.
        
        Args:
            audience_id: Audience ID
            contacts: List of contact dictionaries
            batch_size: Number of contacts per batch
            
        Returns:
            Statistics of the import
        """
        total_contacts = len(contacts)
        successful = 0
        failed = 0
        
        print(f"📥 Importing {total_contacts} contacts to Resend in batches of {batch_size}...")
        
        for i in range(0, total_contacts, batch_size):
            batch = contacts[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_contacts + batch_size - 1) // batch_size
            
            print(f"   📧 Processing batch {batch_num}/{total_batches} ({len(batch)} contacts)...")
            
            batch_successful = 0
            batch_failed = 0
            
            for contact in batch:
                try:
                    self.create_contact(
                        audience_id=audience_id,
                        email=contact["email"],
                        first_name=contact.get("first_name"),
                        last_name=contact.get("last_name"),
                        unsubscribed=contact.get("unsubscribed", False)
                    )
                    batch_successful += 1
                    successful += 1
                except Exception as e:
                    batch_failed += 1
                    failed += 1
                    if "already exists" not in str(e).lower():
                        print(f"      ⚠️  Failed to create {contact['email']}: {str(e)}")
            
            print(f"   ✅ Batch {batch_num} completed: {batch_successful} successful, {batch_failed} failed")
            
            # Small delay between batches to be respectful to the API
            if i + batch_size < total_contacts:
                time.sleep(0.5)
        
        return {
            "total": total_contacts,
            "successful": successful,
            "failed": failed
        }
    
    def list_contacts(self, audience_id: str) -> List[Dict[str, Any]]:
        """List contacts in an audience."""
        try:
            contacts = resend.Contacts.list(audience_id=audience_id)
            return contacts.get("data", [])
        except Exception as e:
            print(f"❌ Error listing contacts: {str(e)}")
            return []
    
    def get_contact_count(self, audience_id: str) -> int:
        """Get contact count for an audience."""
        contacts = self.list_contacts(audience_id)
        return len(contacts)


# Default client instance
_resend_audiences_client = None

def get_resend_audiences_client() -> ResendAudiencesClient:
    """Get or create Resend Audiences client instance."""
    global _resend_audiences_client
    if _resend_audiences_client is None:
        _resend_audiences_client = ResendAudiencesClient()
    return _resend_audiences_client 