import os
import re
from pathlib import Path

# The patterns we want to replace
IMPORT_PATTERN1 = re.compile(r'from promaia\.storage\.postgres_db import .*get_db.*')
IMPORT_PATTERN2 = re.compile(r'from promaia\.storage\.postgres_db import .*db_connect.*')
CALL_PATTERN1 = re.compile(r'get_db\(\)')
CALL_PATTERN2 = re.compile(r'db_connect\(')
# Also catch the PostgresDB type hints if any
TYPE_PATTERN = re.compile(r': PostgresDB')

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    original_content = content
    modified = False

    # 1. Replace the imports
    if 'from promaia.storage.postgres_db import' in content:
        # Complex replacements: if it imports get_db AND db_connect
        if 'get_db' in content and 'db_connect' in content:
            content = re.sub(r'from promaia\.storage\.postgres_db import[^(\n]*get_db[^(\n]*db_connect[^(\n]*', 
                             'from promaia.storage.db_factory import get_db, db_connect', content)
            modified = True
        elif 'get_db' in content:
            content = re.sub(r'from promaia\.storage\.postgres_db import[^(\n]*get_db[^(\n]*', 
                             'from promaia.storage.db_factory import get_db', content)
            modified = True
        elif 'db_connect' in content:
            content = re.sub(r'from promaia\.storage\.postgres_db import[^(\n]*db_connect[^(\n]*', 
                             'from promaia.storage.db_factory import db_connect', content)
            modified = True
            
        # Handle multiline imports if they exist (crude fallback)
        if 'from promaia.storage.db_factory import (' in content:
            if 'get_db' in content:
                content = content.replace('get_db', 'get_db')
                modified = True
            if 'db_connect' in content:
                content = content.replace('db_connect', 'db_connect')
                modified = True
            content = content.replace('from promaia.storage.db_factory import (', 'from promaia.storage.db_factory import (')

        # Still have some postgres_db? Just do a blanket replacement if it matches exactly
        content = content.replace('from promaia.storage.postgres_db import get_db', 'from promaia.storage.db_factory import get_db')
        content = content.replace('from promaia.storage.postgres_db import db_connect', 'from promaia.storage.db_factory import db_connect')
        content = content.replace('from promaia.storage.db_factory import get_db, db_connect

    # 2. Replace the function calls
    if 'get_db()' in content:
        content = content.replace('get_db()', 'get_db()')
        modified = True
        
    if 'db_connect(' in content:
        content = content.replace('db_connect(', 'db_connect(')
        modified = True
        
    # 3. Clean up the variable names for clarity (optional, but good)
    # _db = get_db()  -> _db = get_db() is handled above
    # db = get_db() -> db = get_db() is handled above

    if content != original_content:
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    base_dir = Path('/home/zack/dev/promaia')
    if not base_dir.exists():
        base_dir = Path(r'C:\Users\Zachary Turner\dev\promaia')
        
    count = 0
    # Skip directories
    exclude_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.tmp'}
    
    # We shouldn't touch these central files
    exclude_files = {'postgres_db.py', 'libsql_db.py', 'db_factory.py'}
    
    for root, dirs, files in os.walk(base_dir):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if not file.endswith('.py'):
                continue
            if file in exclude_files:
                continue
                
            filepath = os.path.join(root, file)
            if process_file(filepath):
                print(f"Fixed: {os.path.relpath(filepath, base_dir)}")
                count += 1
                
    print(f"\nMigration sweep complete. Modified {count} files.")

if __name__ == "__main__":
    main()
