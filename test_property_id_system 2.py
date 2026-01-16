#!/usr/bin/env python3
"""
Test the ID-based property system with the trass.stories database.

This script tests:
1. Schema extraction and metadata storage
2. Property ID and option ID resolution
3. Filter resolution from IDs to names
"""
import asyncio
import json
from promaia.config.databases import get_database_manager
from promaia.connectors.notion_connector import NotionConnector
from promaia.storage.property_resolver import PropertyResolver


async def test_schema_extraction():
    """Test extracting and storing property metadata."""
    print("="*60)
    print("Test 1: Schema Extraction and Storage")
    print("="*60)

    # Get the trass.stories database config
    db_manager = get_database_manager()
    db_config = db_manager.get_database("trass.stories")

    if not db_config:
        print("ERROR: Could not find trass.stories database")
        return False

    print(f"Database: {db_config.name}")
    print(f"Database ID: {db_config.database_id}")
    print(f"Current filters: {db_config.property_filters}")

    # Create connector
    connector = NotionConnector(db_config.to_dict())

    # Sync property metadata
    print("\nSyncing property metadata from Notion...")
    try:
        await connector.sync_property_metadata()
        print("✓ Property metadata synced successfully")
    except Exception as e:
        print(f"✗ Failed to sync metadata: {e}")
        return False

    return True


async def test_property_resolution():
    """Test resolving property and option names to IDs."""
    print("\n" + "="*60)
    print("Test 2: Property Resolution")
    print("="*60)

    db_manager = get_database_manager()
    db_config = db_manager.get_database("trass.stories")
    database_id = db_config.database_id

    resolver = PropertyResolver()

    # Test 1: Get property ID for "Team"
    print("\n1. Resolving property name 'Team' to ID:")
    team_property_id = resolver.get_property_id(database_id, "Team")
    if team_property_id:
        print(f"   ✓ Team property ID: {team_property_id}")
    else:
        print("   ✗ Could not resolve Team property")
        return False

    # Test 2: Get property name from ID
    print(f"\n2. Resolving property ID '{team_property_id}' back to name:")
    team_property_name = resolver.get_property_name(database_id, team_property_id)
    if team_property_name:
        print(f"   ✓ Property name: {team_property_name}")
    else:
        print("   ✗ Could not resolve property ID")
        return False

    # Test 3: Get all options for Team property
    print(f"\n3. Getting all options for Team property:")
    options = resolver.get_all_options(database_id, team_property_id)
    if options:
        print(f"   ✓ Found {len(options)} options:")
        for opt in options:
            print(f"     - {opt['name']} (ID: {opt['id']}, Color: {opt['color']})")
    else:
        print("   ✗ No options found")
        return False

    # Test 4: Resolve "Consumer Product" option name to ID
    print(f"\n4. Resolving option name 'Consumer Product' to ID:")
    option_id = resolver.get_option_id(database_id, team_property_id, "Consumer Product")
    if option_id:
        print(f"   ✓ Consumer Product option ID: {option_id}")
    else:
        print("   ✗ Could not resolve Consumer Product option")
        return False

    # Test 5: Resolve option ID back to name
    print(f"\n5. Resolving option ID '{option_id}' back to name:")
    option_name = resolver.get_option_name(database_id, team_property_id, option_id)
    if option_name:
        print(f"   ✓ Option name: {option_name}")
    else:
        print("   ✗ Could not resolve option ID")
        return False

    return True


async def test_filter_resolution():
    """Test resolving filters from IDs to names."""
    print("\n" + "="*60)
    print("Test 3: Filter Resolution")
    print("="*60)

    db_manager = get_database_manager()
    db_config = db_manager.get_database("trass.stories")
    database_id = db_config.database_id

    resolver = PropertyResolver()

    # First, get the IDs we need
    team_property_id = resolver.get_property_id(database_id, "Team")
    consumer_product_option_id = resolver.get_option_id(database_id, team_property_id, "Consumer Product")

    if not team_property_id or not consumer_product_option_id:
        print("   ✗ Could not get necessary IDs for testing")
        return False

    # Test single value filter
    print(f"\n1. Testing single value filter resolution:")
    print(f"   Input: property_id={team_property_id}, value={consumer_product_option_id}")
    prop_name, value = resolver.resolve_filter_value(database_id, team_property_id, consumer_product_option_id)
    if prop_name and value:
        print(f"   ✓ Resolved to: {prop_name} = {value}")
    else:
        print("   ✗ Failed to resolve filter")
        return False

    # Test multi-value filter (if we have multiple options)
    options = resolver.get_all_options(database_id, team_property_id)
    if len(options) >= 2:
        print(f"\n2. Testing multi-value filter resolution:")
        option_ids = [opt['id'] for opt in options[:2]]
        print(f"   Input: property_id={team_property_id}, values={option_ids}")
        prop_name, values = resolver.resolve_filter_value(database_id, team_property_id, option_ids)
        if prop_name and values:
            print(f"   ✓ Resolved to: {prop_name} in {values}")
        else:
            print("   ✗ Failed to resolve multi-value filter")
            return False

    return True


async def test_name_to_id_conversion():
    """Test converting name-based filters to ID-based."""
    print("\n" + "="*60)
    print("Test 4: Name to ID Conversion")
    print("="*60)

    db_manager = get_database_manager()
    db_config = db_manager.get_database("trass.stories")
    database_id = db_config.database_id

    resolver = PropertyResolver()

    print(f"\n1. Converting 'Team' / 'Consumer Product' to IDs:")
    property_id, option_id = resolver.resolve_property_name_to_id(
        database_id, "Team", "Consumer Product"
    )
    if property_id and option_id:
        print(f"   ✓ Property ID: {property_id}")
        print(f"   ✓ Option ID: {option_id}")
    else:
        print("   ✗ Failed to convert to IDs")
        return False

    # Test multi-value
    print(f"\n2. Converting 'Team' / ['Consumer Product', ...] to IDs:")
    options = resolver.get_all_options(database_id, property_id)
    if len(options) >= 2:
        option_names = [opt['name'] for opt in options[:2]]
        property_id2, option_ids = resolver.resolve_property_name_to_id(
            database_id, "Team", option_names
        )
        if property_id2 and option_ids:
            print(f"   ✓ Property ID: {property_id2}")
            print(f"   ✓ Option IDs: {option_ids}")
        else:
            print("   ✗ Failed to convert multi-value to IDs")
            return False

    return True


async def main():
    """Run all tests."""
    print("\nTesting ID-Based Property System")
    print("="*60 + "\n")

    # Test 1: Schema extraction
    success = await test_schema_extraction()
    if not success:
        print("\n✗ Schema extraction test failed")
        return 1

    # Test 2: Property resolution
    success = await test_property_resolution()
    if not success:
        print("\n✗ Property resolution test failed")
        return 1

    # Test 3: Filter resolution
    success = await test_filter_resolution()
    if not success:
        print("\n✗ Filter resolution test failed")
        return 1

    # Test 4: Name to ID conversion
    success = await test_name_to_id_conversion()
    if not success:
        print("\n✗ Name to ID conversion test failed")
        return 1

    print("\n" + "="*60)
    print("✓ All tests passed!")
    print("="*60)
    return 0


if __name__ == '__main__':
    exit(asyncio.run(main()))
