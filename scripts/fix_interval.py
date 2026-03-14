"""Fix remaining INTERVAL patterns in SQL."""
import os

PROJECT_ROOT = "/home/zack/dev/promaia"

fixes = {
    "promaia/brain/heartbeat.py": [
        (
            "WHERE CURRENT_TIMESTAMP - c.last_updated > c.stale_threshold_days * INTERVAL '1 day'",
            "WHERE julianday('now') - julianday(c.last_updated) > c.stale_threshold_days"
        ),
    ],
    "promaia/agents/cost_tracker.py": [
        (
            "WHERE created_at >= CURRENT_DATE - INTERVAL '? days'",
            "WHERE created_at >= datetime('now', '-' || ? || ' days')"
        ),
    ],
}

for rel_path, replacements in fixes.items():
    fpath = os.path.join(PROJECT_ROOT, rel_path)
    with open(fpath) as f:
        content = f.read()
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"  Fixed: {rel_path} — {old[:50]}...")
        else:
            print(f"  Not found in {rel_path}: {old[:50]}...")
    with open(fpath, "w") as f:
        f.write(content)

print("\nDone")
