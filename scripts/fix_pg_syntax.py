"""
Phase 2 of libSQL migration: Convert remaining PostgreSQL-specific SQL syntax to SQLite/libSQL.

Replacements:
1. SERIAL PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
2. TIMESTAMPTZ DEFAULT NOW() -> TEXT DEFAULT CURRENT_TIMESTAMP
3. TIMESTAMPTZ -> TEXT
4. DEFAULT NOW() -> DEFAULT CURRENT_TIMESTAMP
5. NOW() in queries -> datetime('now')
6. NOW() - '-N days' -> datetime('now', '-N days')
7. NOW() - INTERVAL 'N hours' -> datetime('now', '-N hours')
8. ? -> ?
9. %s::vector -> ? (parameterized)
10. BOOLEAN -> INTEGER
11. JSONB -> TEXT
"""
import os
import re

PROJECT_ROOT = "/home/zack/dev/promaia"
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules"}
SKIP_FILES = {"schema_libsql.sql", "postgres_db.py"}

files_changed = 0
total_replacements = 0

replacements = [
    # DDL type conversions
    (r'SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
    (r'BIGSERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
    (r"TIMESTAMPTZ\s+DEFAULT\s+NOW\(\)", 'TEXT DEFAULT CURRENT_TIMESTAMP'),
    (r"TIMESTAMP\s+DEFAULT\s+NOW\(\)", 'TEXT DEFAULT CURRENT_TIMESTAMP'),
    (r'TIMESTAMPTZ', 'TEXT'),
    (r'BOOLEAN\b', 'INTEGER'),
    (r'\bJSONB\b', 'TEXT'),

    # NOW() with INTERVAL patterns - must come before plain NOW()
    (r"NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s*days?'", r"datetime('now', '-\1 days')"),
    (r"NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s*hours?'", r"datetime('now', '-\1 hours')"),
    (r"NOW\(\)\s*\+\s*INTERVAL\s*'(\d+)\s*days?'", r"datetime('now', '+\1 days')"),
    (r"NOW\(\)\s*\*\s*INTERVAL\s*'(\d+)\s*days?'", r"datetime('now', '-\1 days')"),  # likely typo in source

    # Plain NOW()
    (r'\bNOW\(\)', "CURRENT_TIMESTAMP"),

    # Cast removal
    (r'\?', '?'),
    (r'\?', '?'),
    (r'%s::vector', '?'),
    (r'%s', '%s'),

    # PostgreSQL-specific parameter placeholders in cursor.execute
    # NOTE: We do NOT replace all %s -> ? here because that would be too broad
    # and could break string formatting. The db_factory layer handles this.
]

for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".py") or fname in SKIP_FILES:
            continue

        fpath = os.path.join(root, fname)
        with open(fpath, "r") as f:
            content = f.read()

        original = content
        file_count = 0

        for pattern, replacement in replacements:
            content, count = re.subn(pattern, replacement, content, flags=re.IGNORECASE)
            file_count += count

        if file_count > 0:
            with open(fpath, "w") as f:
                f.write(content)
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"  📝 {rel}: {file_count} replacements")
            files_changed += 1
            total_replacements += file_count

print(f"\n✅ PostgreSQL syntax migration complete: {total_replacements} replacements across {files_changed} files")
