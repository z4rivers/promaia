#!/usr/bin/env python3
"""
Overnight Property Embeddings Sync Script

Syncs all Notion databases for the last 90 days to populate property embeddings.
Handles rate limits, logs progress, and runs unattended.

Features:
- Only syncs Notion databases (skips Discord, Gmail, etc.)
- Idempotent: tracks progress and can resume after interruption
- Automatic retry on rate limits

Usage:
    python sync_all_properties_overnight.py           # Resume from last run
    python sync_all_properties_overnight.py --reset   # Start fresh
"""

import subprocess
import time
import json
import re
from datetime import datetime
from pathlib import Path
import sys

# Configuration
DAYS_TO_SYNC = 90  # Last 3 months
RETRY_DELAY = 300  # 5 minutes between retries for rate limits
MAX_RETRIES = 3
LOG_FILE = "sync_overnight_log.txt"
STATE_FILE = "sync_overnight_state.json"

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log(message, color=None, also_print=True):
    """Log message to file and optionally print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"

    # Write to log file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")

    # Print to console with color
    if also_print:
        if color:
            print(f"{color}{log_message}{Colors.ENDC}")
        else:
            print(log_message)


def load_state():
    """Load sync state from file."""
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {'completed': [], 'failed': [], 'last_run': None}
    return {'completed': [], 'failed': [], 'last_run': None}


def save_state(state):
    """Save sync state to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"⚠️  Failed to save state: {e}", Colors.WARNING)


def reset_state():
    """Reset state file."""
    if Path(STATE_FILE).exists():
        Path(STATE_FILE).unlink()
    log("🔄 State file reset", Colors.OKCYAN)


def get_notion_databases():
    """Get all Notion databases from config (only actual Notion databases)."""
    try:
        with open('promaia.config.json', 'r') as f:
            config = json.load(f)

        databases = []
        skipped = []

        for db_name, db_config in config.get('databases', {}).items():
            source_type = db_config.get('source_type', 'unknown')

            # ONLY include actual Notion databases
            if source_type == 'notion':
                workspace = db_config.get('workspace', 'unknown')

                # Construct full name: add workspace prefix if not already present
                if db_name.startswith(f"{workspace}."):
                    full_name = db_name  # Already has workspace prefix (e.g., "trass.journal")
                else:
                    full_name = f"{workspace}.{db_name}"  # Add prefix (e.g., "koii" + "journal" = "koii.journal")

                databases.append({
                    'name': db_name,
                    'workspace': workspace,
                    'full_name': full_name,
                    'sync_enabled': db_config.get('sync_enabled', True),
                    'source_type': source_type
                })
            else:
                # Track non-Notion databases
                skipped.append(f"{db_name} ({source_type})")

        if skipped:
            log(f"ℹ️  Skipping {len(skipped)} non-Notion databases: {', '.join(skipped[:5])}", Colors.OKBLUE)
            if len(skipped) > 5:
                log(f"   ... and {len(skipped) - 5} more", Colors.OKBLUE)

        return databases

    except Exception as e:
        log(f"❌ Error reading config: {e}", Colors.FAIL)
        return []


def sync_database(db_name, days=DAYS_TO_SYNC, force=True):
    """
    Sync a single database with retry logic.

    Returns:
        (success: bool, pages_synced: int, error: str)
    """
    cmd = ['maia', 'sync', '--source', f"{db_name}:{days}"]
    if force:
        cmd.append('--force')

    log(f"🔄 Syncing {db_name} (last {days} days)...", Colors.OKCYAN)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout (for large databases)
            )

            output = result.stdout + result.stderr

            # Check for success indicators
            if "✅" in output or "SUCCESSFUL" in output:
                # Extract pages synced
                pages_synced = 0

                # Extract just the database name without workspace for matching
                # e.g., "koii.journal" -> "journal"
                db_name_only = db_name.split('.')[-1] if '.' in db_name else db_name

                for line in output.split('\n'):
                    # Look for lines like "✅ journal: 7 saved, 0 skipped"
                    if 'saved' in line.lower():
                        try:
                            # Try multiple patterns
                            if '💾' in line:
                                # Pattern: "💾 7 saved"
                                parts = line.split('💾')
                                if len(parts) > 1:
                                    pages_str = parts[1].split('saved')[0].strip()
                                    pages_synced = max(pages_synced, int(pages_str))
                            elif db_name_only in line:
                                # Pattern: "✅ journal: 7 saved, 0 skipped"
                                match = re.search(r'(\d+)\s+saved', line)
                                if match:
                                    pages_synced = int(match.group(1))
                        except:
                            pass

                log(f"✅ {db_name}: {pages_synced} pages synced", Colors.OKGREEN)
                return (True, pages_synced, None)

            # Check for rate limit errors
            elif "rate limit" in output.lower() or "429" in output:
                if attempt < MAX_RETRIES:
                    log(f"⚠️  Rate limited on {db_name}, waiting {RETRY_DELAY}s before retry {attempt}/{MAX_RETRIES}...",
                        Colors.WARNING)
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    return (False, 0, "Rate limited after max retries")

            # Check for other errors
            elif result.returncode != 0:
                error_msg = output[-500:] if len(output) > 500 else output
                return (False, 0, f"Exit code {result.returncode}: {error_msg}")

            else:
                # Sync completed but maybe no new pages
                log(f"ℹ️  {db_name}: No new pages to sync", Colors.OKBLUE)
                return (True, 0, None)

        except subprocess.TimeoutExpired:
            if attempt < MAX_RETRIES:
                log(f"⏱️  Timeout on {db_name}, retrying {attempt}/{MAX_RETRIES}...", Colors.WARNING)
                time.sleep(60)
                continue
            else:
                return (False, 0, "Timeout after max retries")

        except Exception as e:
            return (False, 0, str(e))

    return (False, 0, "Unknown error")


def main():
    """Main execution function."""
    start_time = datetime.now()

    # Check for --reset flag
    if '--reset' in sys.argv:
        reset_state()

    # Load previous state
    state = load_state()

    # Header
    log("=" * 80, Colors.HEADER)
    log("🌙 OVERNIGHT PROPERTY EMBEDDINGS SYNC", Colors.HEADER)
    log("=" * 80, Colors.HEADER)
    log(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Syncing last {DAYS_TO_SYNC} days for all Notion databases")
    log(f"Log file: {LOG_FILE}")

    if state['last_run']:
        log(f"📋 Resuming from previous run: {state['last_run']}")
        log(f"   Already completed: {len(state['completed'])} databases")

    log("=" * 80, Colors.HEADER)
    log("")

    # Get all databases
    databases = get_notion_databases()

    if not databases:
        log("❌ No Notion databases found in config!", Colors.FAIL)
        return 1

    # Filter to only enabled databases
    enabled_dbs = [db for db in databases if db.get('sync_enabled', True)]

    # Filter out already completed databases
    already_completed = set(state['completed'])
    databases_to_sync = [db for db in enabled_dbs if db['full_name'] not in already_completed]

    if already_completed:
        log(f"⏭️  Skipping {len(already_completed)} already completed databases")
        log("")

    if not databases_to_sync:
        log("✅ All databases already synced! Use --reset to start fresh.", Colors.OKGREEN)
        return 0

    log(f"📊 Found {len(databases_to_sync)} databases to sync (out of {len(enabled_dbs)} total)")
    log("")

    # Track results
    results = {
        'success': [],
        'failed': [],
        'total_pages': 0
    }

    # Sync each database
    for i, db in enumerate(databases_to_sync, 1):
        db_name = db['full_name']

        log("─" * 80)
        log(f"📦 Database {i}/{len(databases_to_sync)}: {db_name}", Colors.BOLD)
        log("─" * 80)

        success, pages, error = sync_database(db_name, DAYS_TO_SYNC, force=True)

        if success:
            results['success'].append(db_name)
            results['total_pages'] += pages

            # Update state immediately after success
            state['completed'].append(db_name)
            state['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_state(state)
        else:
            results['failed'].append({
                'name': db_name,
                'error': error
            })

            # Update state with failure
            state['failed'].append({
                'name': db_name,
                'error': error,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            state['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_state(state)

            log(f"❌ Failed: {error}", Colors.FAIL)

        log("")

        # Small delay between databases to be nice to APIs
        if i < len(databases_to_sync):
            time.sleep(2)

    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time

    log("=" * 80, Colors.HEADER)
    log("🎉 SYNC COMPLETE - SUMMARY", Colors.HEADER)
    log("=" * 80, Colors.HEADER)
    log("")
    log(f"⏱️  Duration: {duration}")
    log(f"✅ Successful: {len(results['success'])}/{len(enabled_dbs)} databases")
    log(f"📄 Total pages synced: {results['total_pages']}")
    log("")

    if results['success']:
        log("✅ Successfully synced:", Colors.OKGREEN)
        for db_name in results['success']:
            log(f"   • {db_name}", Colors.OKGREEN)
        log("")

    if results['failed']:
        log(f"❌ Failed ({len(results['failed'])} databases):", Colors.FAIL)
        for item in results['failed']:
            log(f"   • {item['name']}: {item['error']}", Colors.FAIL)
        log("")

    # Property embeddings info
    log("🔍 Property Embeddings Status:", Colors.OKCYAN)
    log("   Property embeddings are created automatically during sync!")
    log("   All synced pages now have property embeddings in ChromaDB.")
    log("")

    if results['failed']:
        log("⚠️  Some databases failed. Check the log above for details.", Colors.WARNING)
        log("   You may need to manually sync the failed databases.", Colors.WARNING)
        log("")

    log("=" * 80, Colors.HEADER)
    log(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Full log saved to: {LOG_FILE}")
    log("=" * 80, Colors.HEADER)

    return 0 if not results['failed'] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\n⚠️  Interrupted by user", Colors.WARNING)
        sys.exit(130)
    except Exception as e:
        log(f"\n❌ Fatal error: {e}", Colors.FAIL)
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
