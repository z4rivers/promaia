# 🌙 Overnight Property Embeddings Sync

This script will sync all your Notion databases for the last 3 months and automatically create property embeddings.

## 🚀 Quick Start

Run this before bed:

```bash
cd ~/Documents/dev/promaia
python sync_all_properties_overnight.py
```

That's it! The script will:
- ✅ Sync all enabled Notion databases for the last 90 days
- ✅ Automatically create property embeddings during sync
- ✅ Handle rate limits with automatic retries
- ✅ Log everything to `sync_overnight_log.txt`
- ✅ Continue even if one database fails
- ✅ Track progress and resume automatically if interrupted
- ✅ Show beautiful progress with colors

### Resume After Interruption

If the script is interrupted (e.g., laptop closed, network issue, rate limit):

```bash
# Just run it again - it will automatically resume!
python sync_all_properties_overnight.py
```

The script tracks which databases have been completed in `sync_overnight_state.json` and skips them on the next run.

### Start Fresh

To ignore previous progress and sync everything from scratch:

```bash
python sync_all_properties_overnight.py --reset
```

## ⏱️ Expected Duration

- **Small databases** (journal, stories, epics): 5-15 minutes each
- **Medium databases** (cms, projects): 10-30 minutes each
- **Large databases** (gmail, yp): 30-90 minutes each
- **Total**: 2-4 hours for all databases

## 📊 What You'll See

```
================================================================================
🌙 OVERNIGHT PROPERTY EMBEDDINGS SYNC
================================================================================
Started at: 2025-10-26 22:30:00
Syncing last 90 days for all Notion databases
Log file: sync_overnight_log.txt
================================================================================

📊 Found 12 enabled Notion databases to sync

────────────────────────────────────────────────────────────────────────────────
📦 Database 1/12: koii.journal
────────────────────────────────────────────────────────────────────────────────
[2025-10-26 22:30:02] 🔄 Syncing koii.journal (last 90 days)...
[2025-10-26 22:32:15] ✅ koii.journal: 382 pages synced

...

================================================================================
🎉 SYNC COMPLETE - SUMMARY
================================================================================

⏱️  Duration: 2:34:12
✅ Successful: 12/12 databases
📄 Total pages synced: 8,425

✅ Successfully synced:
   • koii.journal
   • koii.stories
   • koii.cms
   ...

🔍 Property Embeddings Status:
   Property embeddings are created automatically during sync!
   All synced pages now have property embeddings in ChromaDB.

================================================================================
```

## 🛠️ Configuration

Edit the script to customize:

```python
DAYS_TO_SYNC = 90        # How many days back to sync (default: 3 months)
RETRY_DELAY = 300        # Seconds to wait on rate limits (default: 5 min)
MAX_RETRIES = 3          # Max retry attempts (default: 3)
```

## 📝 Monitoring Progress

While it runs:
```bash
# Watch live progress
tail -f sync_overnight_log.txt

# Check how many databases completed
grep "✅" sync_overnight_log.txt | wc -l

# Check for errors
grep "❌" sync_overnight_log.txt
```

## 🔧 Troubleshooting

### Rate Limited
The script will automatically wait 5 minutes and retry (up to 3 times).

### Script Crashed or Interrupted
Just run it again! The script tracks progress in `sync_overnight_state.json` and will automatically skip already-completed databases.

```bash
# Resume from where it left off
python sync_all_properties_overnight.py

# Check what's been completed so far
cat sync_overnight_state.json
```

### Specific Database Failed
The script continues even if one database fails. Check the summary at the end for failed databases, then manually sync:
```bash
maia sync --source koii.journal:90 --force
```

### Want to Re-sync Everything
Use the `--reset` flag to clear progress and start fresh:
```bash
python sync_all_properties_overnight.py --reset
```

### Want to Skip Gmail/Large Databases
Edit your `promaia.config.json` and set `sync_enabled: false` for those databases:

```json
{
  "databases": {
    "gmail": {
      "sync_enabled": false,
      ...
    }
  }
}
```

## 🎯 After Completion

Once the script finishes, verify property embeddings:

```bash
# Check property embeddings count
python3 << 'EOF'
from promaia.storage.vector_db import VectorDBManager
vector_db = VectorDBManager()
count = vector_db.property_collection.count()
print(f"Property embeddings: {count}")
EOF

# Test a property search
maia chat "stories with epic holiday launch"
```

## 🔄 Maintenance

After this initial sync, you only need regular maintenance:

```bash
# Daily/weekly - just sync recent content
maia sync --source journal:7

# Property embeddings are created automatically!
```

## 💡 Tips

1. **Run overnight** - Some databases are large (12k+ pages)
2. **Close laptop lid** - macOS will keep running background processes
3. **Check WiFi** - Stable connection is important
4. **Clear disk space** - Ensure you have 1-2 GB free

## 🆘 Need Help?

- Check `sync_overnight_log.txt` for detailed logs
- Look for lines with `❌` for errors
- Re-run the script - it's idempotent and safe!

---

**That's it! Sleep well, and wake up to fully embedded properties! 🎉**
