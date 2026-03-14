"""Fix incorrect datetime.CURRENT_TIMESTAMP replacements in Python code.
The sweep incorrectly converted Python's datetime.now() to datetime.CURRENT_TIMESTAMP.
CURRENT_TIMESTAMP is SQL syntax, not Python.
"""
import os
import re

PROJECT_ROOT = "/home/zack/dev/promaia"
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules"}
fixes = 0

for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, "r") as f:
            content = f.read()
        original = content

        # Fix: datetime.CURRENT_TIMESTAMP -> datetime.now()
        content = content.replace("datetime.CURRENT_TIMESTAMP", "datetime.now()")

        # Also check for: datetime.datetime.CURRENT_TIMESTAMP
        content = content.replace("datetime.datetime.CURRENT_TIMESTAMP", "datetime.datetime.now()")

        if content != original:
            with open(fpath, "w") as f:
                f.write(content)
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"  Fixed: {rel}")
            fixes += 1

print(f"\nFixed {fixes} files with incorrect datetime.CURRENT_TIMESTAMP")
