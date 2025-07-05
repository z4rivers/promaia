"""
MailerLite API client for subscriber migration.
"""
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import time


class MailerLiteClient:
    """Client for interacting with MailerLite API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize MailerLite client."""
        self.api_key = api_key or os.getenv("MAILERLITE_API_KEY")
        if not self.api_key:
            raise ValueError("MAILERLITE_API_KEY environment variable is required")
        
        # MailerLite API base URL
        self.base_url = "https://connect.mailerlite.com/api"
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to MailerLite API."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                # Rate limit exceeded - wait and retry
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"   ⏳ Rate limit exceeded, waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self._make_request(method, endpoint, **kwargs)
            else:
                raise Exception(f"MailerLite API error: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"MailerLite API connection error: {str(e)}")
    
    def get_subscribers(self, status: str = "active", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all subscribers from MailerLite.
        
        Args:
            status: Subscriber status (active, unsubscribed, unconfirmed, bounced, junk)
            limit: Number of subscribers per request (max 100)
            
        Returns:
            List of subscriber dictionaries
        """
        all_subscribers = []
        cursor = None
        
        print(f"📥 Fetching {status} subscribers from MailerLite...")
        
        while True:
            params = {
                "filter[status]": status,
                "limit": limit,
                "include": "groups"
            }
            
            if cursor:
                params["cursor"] = cursor
            
            response = self._make_request("GET", "subscribers", params=params)
            
            subscribers = response.get("data", [])
            all_subscribers.extend(subscribers)
            
            print(f"   📧 Retrieved {len(subscribers)} subscribers (total: {len(all_subscribers)})")
            
            # Check if there are more pages
            cursor = response.get("meta", {}).get("next_cursor")
            if not cursor:
                break
                
            # Small delay to be respectful to the API
            time.sleep(0.1)
        
        print(f"✅ Total {status} subscribers retrieved: {len(all_subscribers)}")
        return all_subscribers
    
    def get_all_subscribers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all subscribers organized by status.
        
        Returns:
            Dictionary with subscriber status as keys and lists of subscribers as values
        """
        statuses = ["active", "unsubscribed", "unconfirmed", "bounced", "junk"]
        all_subscribers = {}
        
        for status in statuses:
            try:
                subscribers = self.get_subscribers(status=status)
                all_subscribers[status] = subscribers
            except Exception as e:
                print(f"⚠️  Error fetching {status} subscribers: {str(e)}")
                all_subscribers[status] = []
        
        return all_subscribers
    
    def get_subscriber_count(self) -> int:
        """Get total subscriber count."""
        try:
            response = self._make_request("GET", "subscribers", params={"limit": 0})
            return response.get("total", 0)
        except Exception as e:
            print(f"⚠️  Error getting subscriber count: {str(e)}")
            return 0


# Default client instance
_mailerlite_client = None

def get_mailerlite_client() -> MailerLiteClient:
    """Get or create MailerLite client instance."""
    global _mailerlite_client
    if _mailerlite_client is None:
        _mailerlite_client = MailerLiteClient()
    return _mailerlite_client 