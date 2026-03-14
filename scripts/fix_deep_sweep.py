"""
DEFINITIVE libSQL Migration Sweep
==================================
Handles ALL remaining PostgreSQL → libSQL conversions in one pass.
Run order matters — patterns are applied in dependency order.

Categories:
1. psycopg2 imports → removed or made conditional
2. register_vector() calls → removed (libSQL uses native vector)
3. cursor_factory=RealDictCursor → removed (LibSQLCursorWrapper returns dicts)
4. conn.cursor() patterns → use db.get_cursor() or direct db methods
5. %s parameter placeholders → ? (only inside SQL strings, not Python formatting)
6. <=> pgvector operator → vector_distance_cos()
7. ?::vector casts → ? (already handled but verify)
"""
import os
import re

PROJECT_ROOT = "/home/zack/dev/promaia"
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules", ".eggs"}
# postgres_db.py is the PostgreSQL adapter — leave it intact as fallback
SKIP_FILES = {"schema_libsql.sql", "postgres_db.py", "fix_libsql_migration.py",
              "fix_pg_syntax.py", "fix_execute.py", "fix_deep_sweep.py", "init_libsql.py"}

files_changed = 0
total_replacements = 0
log_lines = []

def log(msg):
    log_lines.append(msg)

def process_file(fpath, rel_path):
    global files_changed, total_replacements

    with open(fpath, "r") as f:
        content = f.read()

    original = content
    file_fixes = 0

    # ================================================================
    # 1. Remove pgvector imports (register_vector, psycopg2 vector utils)
    # ================================================================
    # Remove:     content, n = re.subn(
        r'^from pgvector\.psycopg2 import register_vector\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    # Remove register_vector(conn) calls (with optional whitespace/indentation)
    content, n = re.subn(
        r'^\s*register_vector\(conn\)\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    # ================================================================
    # 2. Make psycopg2 imports conditional or remove them
    #    Keep postgres_db.py intact (it's in SKIP_FILES)
    # ================================================================
    # Remove standalone psycopg2 imports
    content, n = re.subn(
        r'^import psycopg2\.extras\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    content, n = re.subn(
        r'^import psycopg2\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    content, n = re.subn(
        r'^from psycopg2 import extras\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    # Indented psycopg2 imports (inside try blocks, functions, etc.)
    content, n = re.subn(
        r'^(\s+)import psycopg2\.extras\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    content, n = re.subn(
        r'^(\s+)import psycopg2\s*\n',
        '', content, flags=re.MULTILINE
    )
    file_fixes += n

    # ================================================================
    # 3. Replace pgvector <=> operator with vector_distance_cos()
    # Pattern: embedding <=> ?::vector AS distance
    # Replace: vector_distance_cos(embedding, ?) AS distance
    # ================================================================
    content, n = re.subn(
        r'(\w+)\s*<=>\s*\?(?:::vector)?\s+AS\s+(\w+)',
        r'vector_distance_cos(\1, ?) AS \2',
        content
    )
    file_fixes += n

    # Also handle: 1 - (embedding <=> %s::vector) AS similarity_score
    content, n = re.subn(
        r'1\s*-\s*\((\w+)\s*<=>\s*[%?]s?(?:::vector)?\)\s*AS\s+(\w+)',
        r'(1 - vector_distance_cos(\1, ?)) AS \2',
        content
    )
    file_fixes += n

    # ================================================================
    # 4. Replace %s with ? in SQL strings
    #    This is the trickiest part — we only want to replace %s inside
    #    SQL query strings, not in Python string formatting like logger calls.
    #    Strategy: Find multi-line strings (triple-quoted) and single-line
    #    strings that look like SQL, and replace %s within them.
    # ================================================================

    def replace_percent_s_in_sql(match):
        """Replace %s with ? inside SQL-like strings."""
        sql_string = match.group(0)
        # Count replacements for logging
        count = sql_string.count('%s')
        if count > 0:
            return sql_string.replace('%s', '?')
        return sql_string

    # Triple-quoted strings containing SQL keywords
    sql_keywords = r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|FROM|WHERE|INTO|VALUES|SET|JOIN|TABLE|INDEX)'
    # Match triple-quoted strings that contain SQL keywords
    content_new = re.sub(
        r'"""[^"]*?' + sql_keywords + r'[^"]*?"""',
        replace_percent_s_in_sql,
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    if content_new != content:
        n = content.count('%s') - content_new.count('%s')  # approximate
        file_fixes += max(n, 1)
        content = content_new

    # Single-quoted strings containing SQL
    content_new = re.sub(
        r"'[^']*?" + sql_keywords + r"[^']*?'",
        replace_percent_s_in_sql,
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    if content_new != content:
        n = content.count('%s') - content_new.count('%s')
        file_fixes += max(n, 1)
        content = content_new

    # Also handle f-strings with SQL — these often use {var} but may still have %s
    content_new = re.sub(
        r'f"""[^"]*?' + sql_keywords + r'[^"]*?"""',
        replace_percent_s_in_sql,
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    if content_new != content:
        n = content.count('%s') - content_new.count('%s')
        file_fixes += max(n, 1)
        content = content_new

    # ================================================================
    # 5. Replace cursor patterns
    #    conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    #    → (leave as-is, the LibSQLCursorWrapper handles dict returns)
    #    But remove the cursor_factory argument since it references psycopg2
    # ================================================================
    content, n = re.subn(
        r'conn\.cursor\(cursor_factory\s*=\s*psycopg2\.extras\.RealDictCursor\)',
        'conn.cursor()',
        content
    )
    file_fixes += n

    content, n = re.subn(
        r'conn\.cursor\(cursor_factory\s*=\s*extras\.RealDictCursor\)',
        'conn.cursor()',
        content
    )
    file_fixes += n

    # ================================================================
    # 6. Remaining cast removals
    # ================================================================
    content, n = re.subn(r'\?::vector', '?', content)
    file_fixes += n

    content, n = re.subn(r'%s::vector', '?', content)
    file_fixes += n

    # ================================================================
    # Write if changed
    # ================================================================
    if content != original:
        with open(fpath, "w") as f:
            f.write(content)
        log(f"  📝 {rel_path}: {file_fixes} fixes")
        files_changed += 1
        total_replacements += file_fixes


# Walk the project
for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".py") or fname in SKIP_FILES:
            continue
        fpath = os.path.join(root, fname)
        rel = os.path.relpath(fpath, PROJECT_ROOT)
        process_file(fpath, rel)

# Print results
for line in log_lines:
    print(line)
print(f"\n✅ Deep sweep complete: {total_replacements} fixes across {files_changed} files")

# Verification: check for remaining PostgreSQL artifacts
print("\n🔍 Verification scan for remaining PostgreSQL artifacts:")
remaining = 0
for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".py") or fname in SKIP_FILES:
            continue
        fpath = os.path.join(root, fname)
        with open(fpath) as f:
            content = f.read()

        issues = []
        if 'register_vector' in content:
            issues.append('register_vector')
        if 'psycopg2' in content:
            issues.append('psycopg2')
        if '<=>' in content and 'embedding' in content:
            issues.append('<=>')
        # Check for %s in SQL-like contexts (rough heuristic)
        if re.search(r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE).*%s', content, re.DOTALL | re.IGNORECASE):
            issues.append('%s in SQL')

        if issues:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"  ⚠️  {rel}: {', '.join(issues)}")
            remaining += 1

if remaining == 0:
    print("  ✅ No remaining PostgreSQL artifacts found!")
else:
    print(f"  ⚠️  {remaining} files still have PostgreSQL artifacts (may need manual review)")
