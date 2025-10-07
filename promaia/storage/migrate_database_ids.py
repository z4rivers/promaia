"""
Migration script to fix NULL database_id values in hybrid storage.

This script updates old registry entries that were created before the database_id
column was properly implemented.
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List
from promaia.config.databases import get_database_manager

logger = logging.getLogger(__name__)

def migrate_null_database_ids(db_path: str = "data/hybrid_metadata.db", dry_run: bool = False) -> Dict[str, int]:
    """
    Update NULL database_id values with correct IDs from database config.
    
    Args:
        db_path: Path to hybrid metadata database
        dry_run: If True, only report what would be updated without making changes
        
    Returns:
        Dictionary mapping database names to count of updated entries
    """
    results = {}
    
    try:
        db_manager = get_database_manager()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find all entries with NULL database_id
        cursor.execute("""
            SELECT DISTINCT workspace, database_name, COUNT(*) as count
            FROM generic_content 
            WHERE database_id IS NULL
            GROUP BY workspace, database_name
        """)
        
        null_entries = cursor.fetchall()
        
        if not null_entries:
            logger.info("No entries with NULL database_id found - migration not needed")
            return results
        
        logger.info(f"Found {len(null_entries)} database(s) with NULL database_id entries:")
        
        for workspace, db_name, count in null_entries:
            logger.info(f"  {workspace}.{db_name}: {count} entries")
            
            # Get the correct database_id from config
            try:
                # Try getting by qualified name first (workspace.nickname)
                qualified_name = f"{workspace}.{db_name}"
                db_config = db_manager.get_database(qualified_name)
                
                if not db_config:
                    # Try without workspace prefix
                    db_config = db_manager.get_database(db_name)
                
                if db_config and db_config.database_id:
                    if dry_run:
                        logger.info(f"    Would update to database_id: {db_config.database_id}")
                        results[qualified_name] = count
                    else:
                        # Update the entries
                        cursor.execute("""
                            UPDATE generic_content 
                            SET database_id = ?
                            WHERE workspace = ? AND database_name = ? AND database_id IS NULL
                        """, (db_config.database_id, workspace, db_name))
                        
                        updated = cursor.rowcount
                        logger.info(f"    ✅ Updated {updated} entries to database_id: {db_config.database_id}")
                        results[qualified_name] = updated
                else:
                    logger.warning(f"    ⚠️  Could not find database config for {qualified_name}")
                    
            except Exception as e:
                logger.error(f"    ❌ Error updating {workspace}.{db_name}: {e}")
        
        if not dry_run:
            conn.commit()
            logger.info("Migration completed successfully")
        else:
            logger.info("Dry run completed - no changes made")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    
    return results


def check_missing_database_ids() -> List[Dict[str, any]]:
    """
    Check for entries with missing database_ids without updating them.
    
    Returns:
        List of dictionaries with database info and count of NULL entries
    """
    try:
        conn = sqlite3.connect("data/hybrid_metadata.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT workspace, database_name, content_type, COUNT(*) as count, MAX(synced_time) as latest_sync
            FROM generic_content 
            WHERE database_id IS NULL
            GROUP BY workspace, database_name, content_type
            ORDER BY latest_sync DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "workspace": row[0],
                "database_name": row[1],
                "content_type": row[2],
                "count": row[3],
                "latest_sync": row[4]
            })
        
        conn.close()
        return results
        
    except Exception as e:
        logger.error(f"Check failed: {e}")
        return []


if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    
    print("=" * 60)
    print("Database ID Migration Tool")
    print("=" * 60)
    
    # First check what needs to be migrated
    print("\n📊 Checking for entries with NULL database_id...\n")
    missing = check_missing_database_ids()
    
    if not missing:
        print("✅ No entries with NULL database_id found!")
        sys.exit(0)
    
    print(f"Found {len(missing)} database(s) with NULL database_id entries:\n")
    for entry in missing:
        print(f"  • {entry['workspace']}.{entry['database_name']}")
        print(f"    Type: {entry['content_type']}")
        print(f"    Count: {entry['count']} entries")
        print(f"    Latest sync: {entry['latest_sync']}\n")
    
    # Run migration
    print("\n🔧 Running migration...\n")
    results = migrate_null_database_ids(dry_run=dry_run)
    
    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN COMPLETED")
        print("Run without --dry-run to apply changes")
    else:
        print("MIGRATION COMPLETED")
        total_updated = sum(results.values())
        print(f"Total entries updated: {total_updated}")
    print("=" * 60)

