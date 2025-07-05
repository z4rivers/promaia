"""
Simple Resend email client for newsletters.
"""
import os
import resend
from typing import List, Optional, Dict, Any


class ResendClient:
    """Simple client for sending emails via Resend API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Resend client."""
        self.api_key = api_key or os.getenv("RESEND_API_KEY")
        if not self.api_key:
            raise ValueError("RESEND_API_KEY environment variable is required")
        
        # Set the API key for resend
        resend.api_key = self.api_key
    
    def send_newsletter(
        self, 
        subject: str,
        plain_text: str,
        html_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        to_emails: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send a newsletter email using Resend.
        
        Args:
            subject: Email subject line
            plain_text: Plain text content
            html_content: Optional HTML content (if None, will be generated from plain_text)
            from_email: Sender email (defaults to env var)
            from_name: Sender name (defaults to env var)
            to_emails: List of recipient emails (defaults to test email)
            
        Returns:
            Dictionary with send results
        """
        # Default values from environment
        from_email = from_email or os.getenv("RESEND_FROM_EMAIL", "newsletter@koiibenvenutto.com")
        from_name = from_name or os.getenv("RESEND_FROM_NAME", "Koii Benvenutto")
        
        # For testing, send to yourself or test emails
        if not to_emails:
            test_email = os.getenv("RESEND_TEST_EMAIL", "koii@koiibenvenutto.com")
            to_emails = [test_email]
        
        # Generate simple HTML from plain text if not provided
        if not html_content:
            html_content = self._plain_text_to_html(plain_text)
        
        try:
            print(f"   📧 Sending newsletter via Resend...")
            print(f"   📧 Subject: {subject}")
            print(f"   📧 From: {from_name} <{from_email}>")
            print(f"   📧 To: {to_emails}")
            print(f"   📧 Content length: {len(plain_text)} characters")
            
            # Send the email
            response = resend.Emails.send({
                "from": f"{from_name} <{from_email}>",
                "to": to_emails,
                "subject": subject,
                "text": plain_text,
                "html": html_content
            })
            
            print(f"   ✅ Email sent successfully!")
            print(f"   📧 Resend ID: {response.get('id', 'Unknown')}")
            
            return {
                "success": True,
                "email_id": response.get("id"),
                "response": response
            }
            
        except Exception as e:
            print(f"   ❌ Error sending email: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _plain_text_to_html(self, plain_text: str) -> str:
        """
        Convert plain text to simple, clean HTML with clickable links.
        
        Args:
            plain_text: Plain text content
            
        Returns:
            Simple HTML version with clickable links
        """
        import re
        
        lines = plain_text.split('\n')
        html_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                html_lines.append('<br>')
                continue
            
            # Headers (lines with === or ---)
            if line.startswith('=') and len(line) > 5:
                continue  # Skip separator lines
            
            # Check if previous line might be a title (look for === after it)
            if len(html_lines) > 0 and lines and html_lines[-1] != '<br>':
                next_idx = lines.index(line.strip()) if line.strip() in lines else -1
                if next_idx < len(lines) - 1 and lines[next_idx + 1].startswith('='):
                    # This is a title
                    html_lines[-1] = f'<h1 style="font-size: 24px; font-weight: bold; margin: 20px 0 10px 0; color: #333;">{html_lines[-1]}</h1>'
                    continue
            
            # Subheaders (lines with --- or lines that end with :)
            if line.startswith('-') and len(line) > 5:
                continue  # Skip separator lines
            elif line.endswith(':') and len(line) < 50:
                html_lines.append(f'<h2 style="font-size: 18px; font-weight: bold; margin: 15px 0 8px 0; color: #555;">{line}</h2>')
                continue
            
            # Cover image (convert to actual image)
            if line.startswith('🖼️ http'):
                image_url = line.replace('🖼️ ', '').strip()
                html_lines.append(f'<p style="margin: 16px 0; text-align: center;"><img src="{image_url}" alt="Cover Image" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px;" /></p>')
                continue
            
            # URLs (convert to clickable links)
            if line.startswith('http'):
                html_lines.append(f'<p style="margin: 8px 0;"><a href="{line}" style="color: #007acc; text-decoration: underline;">{line}</a></p>')
                continue
            
            # Lines that contain "Read the full post:" - make the URL clickable
            if "📖 Read the full post:" in line:
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    url = url_match.group(0)
                    # Replace the entire line with just the clickable link
                    html_lines.append(f'<p style="margin: 8px 0; line-height: 1.5; color: #333;">📖 <a href="{url}" style="color: #007acc; text-decoration: underline; font-weight: bold;">Read the full post</a></p>')
                    continue
            
            # Lines that contain "Subscribe:" - make the URL clickable
            if "💌 Forwarded this email? Subscribe:" in line:
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    url = url_match.group(0)
                    # Replace the entire line with just the clickable link
                    html_lines.append(f'<p style="margin: 8px 0; line-height: 1.5; color: #333;">💌 Forwarded this email? <a href="{url}" style="color: #007acc; text-decoration: underline; font-weight: bold;">Subscribe here</a></p>')
                    continue
            
            # Regular paragraphs - check for any URLs within the text and make them clickable
            url_pattern = r'(https?://[^\s]+)'
            if re.search(url_pattern, line):
                clickable_line = re.sub(url_pattern, r'<a href="\1" style="color: #007acc; text-decoration: underline;">\1</a>', line)
                html_lines.append(f'<p style="margin: 8px 0; line-height: 1.5; color: #333;">{clickable_line}</p>')
            else:
                html_lines.append(f'<p style="margin: 8px 0; line-height: 1.5; color: #333;">{line}</p>')
        
        # Wrap in minimal HTML structure
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; line-height: 1.6;">
            {''.join(html_lines)}
        </body>
        </html>
        """
        
        return html.strip()


# Default client instance
resend_client = None

def get_resend_client() -> ResendClient:
    """Get or create default Resend client."""
    global resend_client
    if resend_client is None:
        resend_client = ResendClient()
    return resend_client 