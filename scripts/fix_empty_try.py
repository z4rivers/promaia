"""Fix empty try blocks left behind by psycopg2 import removal."""
import os
import re

PROJECT_ROOT = "/home/zack/dev/promaia"
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules"}
SKIP_FILES = {"postgres_db.py"}

fixes = 0

for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".py") or fname in SKIP_FILES:
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, "r") as f:
            content = f.read()

        original = content

        # Pattern: empty try block followed by except ImportError
        # try:\n<whitespace>except ImportError:
        content = re.sub(
            r'try:\s*\nexcept ImportError:\s*\n\s*psycopg2\s*=\s*None\s*\n',
            '',
            content
        )

        # Also: try:\nexcept ImportError:\n    pass\n
        content = re.sub(
            r'try:\s*\nexcept ImportError:\s*\n\s*pass\s*\n',
            '',
            content
        )

        # Also handle: try:\n    pass\nexcept ImportError:\n    pass/psycopg2=None
        content = re.sub(
            r'try:\s*\n\s*pass\s*\nexcept ImportError:\s*\n\s*(?:psycopg2\s*=\s*None|pass)\s*\n',
            '',
            content
        )

        if content != original:
            with open(fpath, "w") as f:
                f.write(content)
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"  Fixed: {rel}")
            fixes += 1

print(f"\nFixed {fixes} files with empty try blocks")
