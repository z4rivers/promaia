"""
Complete the libSQL migration:
1. Add execute() method to LibSQLDB for PostgresDB compatibility
2. Strip 'brain.' schema prefix from all SQL statements (PostgreSQL → SQLite)
"""
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# Step 1: Add execute() method to LibSQLDB
# ============================================================
libsql_path = os.path.join(PROJECT_ROOT, "promaia", "storage", "libsql_db.py")
with open(libsql_path, "r") as f:
    content = f.read()

if "def execute(self" not in content:
    # Insert execute() method before execute_query()
    old = "    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:"
    new = '''    def execute(self, query: str, params=None):
        """Convenience alias matching PostgresDB.execute() interface."""
        return self.execute_query(query, params)

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:'''
    content = content.replace(old, new)
    with open(libsql_path, "w") as f:
        f.write(content)
    print("✅ Added execute() method to LibSQLDB")
else:
    print("⏭️  execute() method already exists")

# ============================================================
# Step 2: Strip 'brain.' schema prefix from SQL in Python files
# ============================================================
# These are the specific SQL table names using the brain. schema
BRAIN_TABLES = [
    "actions", "agent_costs", "contexts", "conversation_sessions",
    "conversations", "domains", "events", "memories",
    "onboarding_progress", "onboarding_sessions", "profile",
    "profile_narrative", "timeline"
]

# Build a regex that matches brain.TABLE_NAME in SQL contexts
# We need to be careful not to match Python module references like brain.engine
pattern = re.compile(
    r'\bbrain\.(' + '|'.join(BRAIN_TABLES) + r')\b'
)

files_changed = 0
total_replacements = 0

for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "promaia")):
    # Skip __pycache__
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, "r") as f:
            original = f.read()
        
        new_content, count = pattern.subn(r'\1', original)
        
        if count > 0:
            with open(fpath, "w") as f:
                f.write(new_content)
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"  📝 {rel}: {count} replacements")
            files_changed += 1
            total_replacements += count

print(f"\n✅ Schema strip complete: {total_replacements} replacements across {files_changed} files")
