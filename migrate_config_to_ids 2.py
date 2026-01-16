#!/usr/bin/env python3
"""
Migrate property_filters in promaia.config.json from name-based to ID-based format.

This script:
1. Reads the current config
2. For each database with property_filters, resolves property names and option names to IDs
3. Updates the config with ID-based filters
4. Saves a backup of the old config
5. Writes the new config

Usage:
    python migrate_config_to_ids.py [--dry-run] [--config path/to/config.json]
"""
import json
import asyncio
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from promaia.storage.property_resolver import PropertyResolver
from promaia.connectors.notion_connector import NotionConnector


async def migrate_database_filters(
    database_id: str,
    property_filters: Dict[str, Any],
    connector: NotionConnector,
    resolver: PropertyResolver
) -> Dict[str, Any]:
    """
    Migrate property_filters from names to IDs for a single database.

    Args:
        database_id: The Notion database ID
        property_filters: Current property_filters dict (name-based)
        connector: NotionConnector instance for this database
        resolver: PropertyResolver instance

    Returns:
        New property_filters dict (ID-based)
    """
    # First, sync property metadata from Notion
    print(f"  Syncing property metadata for database {database_id[:8]}...")
    await connector.sync_property_metadata()

    new_filters = {}

    for prop_name, prop_values in property_filters.items():
        # Check if already an ID (heuristic: no spaces and length > 10)
        if ' ' not in prop_name and len(prop_name) > 10:
            print(f"  Property '{prop_name}' appears to already be an ID, keeping as-is")
            new_filters[prop_name] = prop_values
            continue

        # Resolve property name to ID
        property_id = resolver.get_property_id(database_id, prop_name)
        if not property_id:
            print(f"  WARNING: Could not resolve property '{prop_name}' to ID, keeping name")
            new_filters[prop_name] = prop_values
            continue

        # Resolve option values to IDs if applicable
        resolved_id, resolved_values = resolver.resolve_property_name_to_id(
            database_id, prop_name, prop_values
        )

        if resolved_id and resolved_values:
            print(f"  ✓ Migrated: {prop_name} → {property_id}")
            if isinstance(prop_values, list):
                print(f"    Values: {prop_values} → {resolved_values}")
            else:
                print(f"    Value: {prop_values} → {resolved_values}")
            new_filters[property_id] = resolved_values
        else:
            print(f"  WARNING: Could not resolve values for '{prop_name}', keeping name")
            new_filters[prop_name] = prop_values

    return new_filters


async def migrate_config(config_path: str, dry_run: bool = False):
    """
    Migrate the entire config file to ID-based property_filters.

    Args:
        config_path: Path to the config file
        dry_run: If True, don't write changes
    """
    print(f"Loading config from: {config_path}")

    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)

    databases = config.get('databases', {})
    if not databases:
        print("No databases found in config")
        return

    print(f"Found {len(databases)} databases")

    resolver = PropertyResolver()
    changes_made = False

    for db_name, db_config in databases.items():
        if db_config.get('source_type') != 'notion':
            print(f"\nSkipping {db_name} (not a Notion database)")
            continue

        property_filters = db_config.get('property_filters', {})
        if not property_filters:
            print(f"\nSkipping {db_name} (no property_filters)")
            continue

        print(f"\n{'='*60}")
        print(f"Migrating: {db_name}")
        print(f"{'='*60}")

        database_id = db_config.get('database_id')
        if not database_id:
            print(f"  ERROR: No database_id found, skipping")
            continue

        # Create connector for this database
        connector = NotionConnector(db_config)

        try:
            # Migrate filters
            new_filters = await migrate_database_filters(
                database_id,
                property_filters,
                connector,
                resolver
            )

            # Update config
            if new_filters != property_filters:
                db_config['property_filters'] = new_filters
                changes_made = True
                print(f"  ✓ Updated property_filters for {db_name}")
            else:
                print(f"  No changes needed for {db_name}")

        except Exception as e:
            print(f"  ERROR migrating {db_name}: {e}")
            import traceback
            traceback.print_exc()

    if not changes_made:
        print("\n" + "="*60)
        print("No changes needed - all filters are already ID-based or no Notion databases found")
        print("="*60)
        return

    if dry_run:
        print("\n" + "="*60)
        print("DRY RUN - Changes not saved")
        print("="*60)
        print("\nNew config preview:")
        print(json.dumps(config, indent=2))
        return

    # Save backup
    backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\nSaving backup to: {backup_path}")
    shutil.copy2(config_path, backup_path)

    # Write new config
    print(f"Writing updated config to: {config_path}")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print("\n" + "="*60)
    print("Migration complete!")
    print("="*60)
    print(f"Backup saved to: {backup_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate promaia.config.json to ID-based property filters"
    )
    parser.add_argument(
        '--config',
        default='promaia.config.json',
        help='Path to config file (default: promaia.config.json)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show changes without writing them'
    )

    args = parser.parse_args()

    # Check config exists
    if not Path(args.config).exists():
        print(f"ERROR: Config file not found: {args.config}")
        return 1

    # Run migration
    asyncio.run(migrate_config(args.config, args.dry_run))
    return 0


if __name__ == '__main__':
    exit(main())
