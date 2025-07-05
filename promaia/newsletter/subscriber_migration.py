"""
Subscriber migration from MailerLite to Resend.
"""
import os
import csv
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from promaia.newsletter.mailerlite_client import get_mailerlite_client
from promaia.newsletter.resend_audiences_client import get_resend_audiences_client


class SubscriberMigration:
    """Handle subscriber migration from MailerLite to Resend."""
    
    def __init__(self):
        """Initialize migration system."""
        self.mailerlite_client = get_mailerlite_client()
        self.resend_client = get_resend_audiences_client()
        
        # Migration settings
        self.default_audience_name = "Migrated from MailerLite"
        self.backup_dir = Path("data/migration_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def transform_mailerlite_to_resend(self, mailerlite_subscribers: List[Dict[str, Any]], 
                                     status: str) -> List[Dict[str, Any]]:
        """
        Transform MailerLite subscriber format to Resend format.
        
        Args:
            mailerlite_subscribers: List of MailerLite subscribers
            status: Original MailerLite status
            
        Returns:
            List of Resend-compatible contact dictionaries
        """
        resend_contacts = []
        
        for subscriber in mailerlite_subscribers:
            # Extract basic information
            email = subscriber.get("email", "").strip()
            if not email:
                continue
            
            # Extract name fields
            fields = subscriber.get("fields", {})
            first_name = fields.get("name") or fields.get("first_name")
            last_name = fields.get("last_name")
            
            # Determine unsubscribed status based on MailerLite status
            unsubscribed = status in ["unsubscribed", "bounced", "junk"]
            
            contact = {
                "email": email,
                "unsubscribed": unsubscribed,
                "mailerlite_status": status,
                "mailerlite_id": subscriber.get("id"),
                "subscribed_at": subscriber.get("subscribed_at"),
                "unsubscribed_at": subscriber.get("unsubscribed_at")
            }
            
            if first_name:
                contact["first_name"] = str(first_name).strip()
            if last_name:
                contact["last_name"] = str(last_name).strip()
            
            resend_contacts.append(contact)
        
        return resend_contacts
    
    def backup_subscribers(self, all_subscribers: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Backup MailerLite subscribers to local files.
        
        Args:
            all_subscribers: Dictionary of subscribers by status
            
        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"mailerlite_backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        print(f"💾 Creating backup at: {backup_path}")
        
        # Save JSON backup
        json_file = backup_path / "subscribers.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_subscribers, f, indent=2, ensure_ascii=False)
        
        # Save CSV backup for each status
        total_backed_up = 0
        for status, subscribers in all_subscribers.items():
            if not subscribers:
                continue
                
            csv_file = backup_path / f"subscribers_{status}.csv"
            
            # Get all possible field names
            all_fields = set()
            for subscriber in subscribers:
                all_fields.update(subscriber.get("fields", {}).keys())
                all_fields.update(["id", "email", "status", "subscribed_at", "unsubscribed_at"])
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                if subscribers:
                    # Use the first subscriber to get the base structure
                    fieldnames = ["id", "email", "status", "subscribed_at", "unsubscribed_at"]
                    
                    # Add custom fields
                    sample_fields = subscribers[0].get("fields", {})
                    fieldnames.extend(sample_fields.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for subscriber in subscribers:
                        row = {
                            "id": subscriber.get("id"),
                            "email": subscriber.get("email"),
                            "status": subscriber.get("status"),
                            "subscribed_at": subscriber.get("subscribed_at"),
                            "unsubscribed_at": subscriber.get("unsubscribed_at")
                        }
                        
                        # Add custom fields
                        fields = subscriber.get("fields", {})
                        row.update(fields)
                        
                        writer.writerow(row)
            
            total_backed_up += len(subscribers)
            print(f"   📄 Saved {len(subscribers)} {status} subscribers to {csv_file.name}")
        
        print(f"✅ Backup completed: {total_backed_up} total subscribers backed up")
        return str(backup_path)
    
    def get_or_create_audience(self, audience_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get existing audience or create new one.
        
        Args:
            audience_name: Name of the audience (defaults to migration default)
            
        Returns:
            Audience object
        """
        audience_name = audience_name or self.default_audience_name
        
        # Check if audience already exists
        existing_audience = self.resend_client.get_audience_by_name(audience_name)
        if existing_audience:
            print(f"📋 Using existing audience: {audience_name} (ID: {existing_audience['id']})")
            return existing_audience
        
        # Create new audience
        print(f"📋 Creating new audience: {audience_name}")
        return self.resend_client.create_audience(audience_name)
    
    def migrate_subscribers(self, audience_name: Optional[str] = None, 
                           include_statuses: Optional[List[str]] = None,
                           batch_size: int = 50) -> Dict[str, Any]:
        """
        Migrate all subscribers from MailerLite to Resend.
        
        Args:
            audience_name: Name of the Resend audience
            include_statuses: List of MailerLite statuses to include (defaults to ["active"])
            batch_size: Number of contacts to import per batch
            
        Returns:
            Migration report
        """
        print("🚀 Starting MailerLite to Resend subscriber migration...")
        print("=" * 60)
        
        # Default to only active subscribers
        include_statuses = include_statuses or ["active"]
        
        # Step 1: Export from MailerLite
        print("📥 Step 1: Exporting subscribers from MailerLite")
        all_subscribers = self.mailerlite_client.get_all_subscribers()
        
        # Filter by requested statuses
        filtered_subscribers = {
            status: subscribers 
            for status, subscribers in all_subscribers.items() 
            if status in include_statuses
        }
        
        # Step 2: Backup subscribers
        print("\n💾 Step 2: Creating backup")
        backup_path = self.backup_subscribers(all_subscribers)
        
        # Step 3: Transform data
        print("\n🔄 Step 3: Transforming subscriber data")
        all_contacts = []
        transformation_stats = {}
        
        for status, subscribers in filtered_subscribers.items():
            if not subscribers:
                continue
                
            contacts = self.transform_mailerlite_to_resend(subscribers, status)
            all_contacts.extend(contacts)
            transformation_stats[status] = len(contacts)
            print(f"   ✅ Transformed {len(contacts)} {status} subscribers")
        
        if not all_contacts:
            print("⚠️  No subscribers found to migrate")
            return {
                "success": False,
                "message": "No subscribers found to migrate",
                "backup_path": backup_path
            }
        
        print(f"   📊 Total contacts to migrate: {len(all_contacts)}")
        
        # Step 4: Get or create Resend audience
        print("\n📋 Step 4: Setting up Resend audience")
        audience = self.get_or_create_audience(audience_name)
        audience_id = audience["id"]
        
        # Step 5: Import to Resend
        print("\n📤 Step 5: Importing contacts to Resend")
        import_stats = self.resend_client.batch_create_contacts(
            audience_id=audience_id,
            contacts=all_contacts,
            batch_size=batch_size
        )
        
        # Step 6: Generate report
        print("\n📊 Step 6: Generating migration report")
        migration_report = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "backup_path": backup_path,
            "mailerlite_stats": {
                status: len(subscribers) 
                for status, subscribers in all_subscribers.items()
            },
            "included_statuses": include_statuses,
            "transformation_stats": transformation_stats,
            "resend_audience": {
                "name": audience["name"],
                "id": audience_id
            },
            "import_stats": import_stats
        }
        
        # Save migration report
        report_file = Path(backup_path) / "migration_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(migration_report, f, indent=2, ensure_ascii=False)
        
        print("=" * 60)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"📈 Migration Summary:")
        print(f"   • Total MailerLite subscribers: {sum(migration_report['mailerlite_stats'].values())}")
        print(f"   • Migrated to Resend: {import_stats['successful']}")
        print(f"   • Failed imports: {import_stats['failed']}")
        print(f"   • Resend audience: {audience['name']} ({audience_id})")
        print(f"   • Backup location: {backup_path}")
        print(f"   • Report saved: {report_file}")
        
        return migration_report


def migrate_subscribers_command(args):
    """CLI command for subscriber migration."""
    # Get parameters from args or environment
    audience_name = getattr(args, 'audience_name', None) or os.getenv("RESEND_AUDIENCE_NAME")
    include_unsubscribed = getattr(args, 'include_unsubscribed', False)
    batch_size = getattr(args, 'batch_size', 50)
    
    # Determine which statuses to include
    if include_unsubscribed:
        include_statuses = ["active", "unsubscribed"]
        print("📢 Including both active AND unsubscribed subscribers")
    else:
        include_statuses = ["active"]
        print("📢 Including only active subscribers")
    
    try:
        # Run migration
        migration = SubscriberMigration()
        report = migration.migrate_subscribers(
            audience_name=audience_name,
            include_statuses=include_statuses,
            batch_size=batch_size
        )
        
        if report["success"]:
            print("\n✅ Migration completed successfully!")
        else:
            print(f"\n❌ Migration failed: {report.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n❌ Migration failed with error: {str(e)}")
        raise 