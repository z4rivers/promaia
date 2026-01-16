#!/usr/bin/env python3
"""
Debug script to diagnose Discord context loading issue.
"""
import sqlite3
import json
from pathlib import Path

# Find the registry database (relative to the project root)
registry_path = Path("data/hybrid_metadata.db")

if not registry_path.exists():
    print(f"❌ Registry not found at: {registry_path}")
    exit(1)

print(f"📂 Using registry: {registry_path}\n")

# Connect to database
conn = sqlite3.connect(str(registry_path))
cursor = conn.cursor()

# Check for Discord messages in trass.tg
print("=" * 80)
print("1. Checking for Discord messages in trass.tg")
print("=" * 80)

cursor.execute("""
    SELECT COUNT(*)
    FROM unified_content
    WHERE workspace = 'trass'
    AND database_id LIKE '%discord%'
""")
total_discord = cursor.fetchone()[0]
print(f"Total Discord messages in trass workspace: {total_discord}\n")

# Check specific database
cursor.execute("""
    SELECT database_id, database_name, COUNT(*) as count
    FROM unified_content
    WHERE workspace = 'trass'
    AND database_id LIKE '%discord%'
    GROUP BY database_id, database_name
""")
results = cursor.fetchall()
print("Discord databases in trass:")
for db_id, db_name, count in results:
    print(f"  - {db_name} (ID: {db_id}): {count} messages")

print("\n" + "=" * 80)
print("2. Checking metadata structure for Discord messages")
print("=" * 80)

# Get a sample Discord message
cursor.execute("""
    SELECT page_id, metadata, content_type
    FROM unified_content
    WHERE workspace = 'trass'
    AND database_id LIKE '%discord%'
    LIMIT 1
""")
row = cursor.fetchone()

if row:
    page_id, metadata_str, content_type = row
    print(f"Sample page_id: {page_id}")
    print(f"Content type: {content_type}\n")

    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
            print("Metadata structure:")
            print(f"  Top-level keys: {list(metadata.keys())}")

            # Check for Discord fields
            discord_fields = ['discord_channel_name', 'discord_channel_id', 'discord_server_name']
            print(f"\n  Discord-specific fields:")
            for field in discord_fields:
                value = metadata.get(field, "NOT FOUND")
                print(f"    - {field}: {value}")

            # Check properties
            if 'properties' in metadata:
                print(f"\n  Properties keys: {list(metadata['properties'].keys())}")
        except json.JSONDecodeError as e:
            print(f"  ❌ Failed to parse metadata: {e}")
else:
    print("  ❌ No Discord messages found")

print("\n" + "=" * 80)
print("3. Checking for 'koii-work' channel specifically")
print("=" * 80)

cursor.execute("""
    SELECT page_id, metadata
    FROM unified_content
    WHERE workspace = 'trass'
    AND database_id LIKE '%discord%'
""")

koii_work_count = 0
channel_names = set()

for page_id, metadata_str in cursor.fetchall():
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
            channel_name = metadata.get('discord_channel_name')
            if channel_name:
                channel_names.add(channel_name)
                if channel_name == 'koii-work':
                    koii_work_count += 1
        except:
            pass

print(f"Messages in 'koii-work' channel: {koii_work_count}")
print(f"\nAll unique channel names found:")
for channel in sorted(channel_names):
    cursor.execute("""
        SELECT COUNT(*)
        FROM unified_content
        WHERE workspace = 'trass'
        AND database_id LIKE '%discord%'
        AND json_extract(metadata, '$.discord_channel_name') = ?
    """, (channel,))
    count = cursor.fetchone()[0]
    marker = "  ← TARGET" if channel == 'koii-work' else ""
    print(f"  - {channel}: {count} messages{marker}")

print("\n" + "=" * 80)
print("4. Testing filter logic")
print("=" * 80)

# Test the actual SQL filtering that would be used
cursor.execute("""
    SELECT page_id
    FROM unified_content
    WHERE workspace = 'trass'
    AND database_id LIKE '%discord%'
""")

all_page_ids = [row[0] for row in cursor.fetchall()]
print(f"Total pages from SQL query: {len(all_page_ids)}")

# Simulate the property filter logic
matching_pages = 0
for page_id in all_page_ids:
    cursor.execute("""
        SELECT metadata
        FROM unified_content
        WHERE page_id = ?
    """, (page_id,))
    metadata_str = cursor.fetchone()[0]
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
            if metadata.get('discord_channel_name') == 'koii-work':
                matching_pages += 1
        except:
            pass

print(f"Pages matching 'discord_channel_name=koii-work': {matching_pages}")

print("\n" + "=" * 80)
print("5. Checking database configuration")
print("=" * 80)

# Check if the database is properly configured
from promaia.config.databases import get_database_manager
db_manager = get_database_manager()

try:
    trass_databases = db_manager.get_workspace_databases('trass')
    print(f"Databases in 'trass' workspace:")
    for db in trass_databases:
        print(f"  - {db.get_qualified_name()} (type: {db.source_type})")
        if db.source_type == 'discord':
            print(f"    database_id: {db.database_id}")
            print(f"    nickname: {db.nickname}")
except Exception as e:
    print(f"  ❌ Error loading workspace databases: {e}")

conn.close()

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)
