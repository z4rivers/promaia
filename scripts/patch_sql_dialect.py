import os
import re
from pathlib import Path

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    original_content = content

    # 1. LIKE -> LIKE
    content = re.sub(r'\bILIKE\b', 'LIKE', content)
    
    # 2. , , 
    content = content.replace('', '')
    content = content.replace('', '')
    content = content.replace('', '')
    
    # 3. INTERVAL issues in tests/prompts
    content = content.replace("datetime('now', '-%s days')", "datetime('now', '-%s days')")
    content = content.replace("datetime('now', '-7 days')", "datetime('now', '-7 days')")
    content = content.replace("'-N days'", "'-N days'")
    
    # 4. register_vector leftovers
    content = content.replace("from pgvector.psycopg2 import register_vector\n", "")
    content = content.replace("import register_vector\n", "")  # just in case
    
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
    exclude_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.tmp'}
    
    # We shouldn't touch these since they are already fully SQLite or irrelevant
    exclude_files = {'libsql_db.py', 'postgres_db.py'}
    
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if not file.endswith('.py'):
                continue
            if file in exclude_files:
                continue
                
            filepath = os.path.join(root, file)
            if process_file(filepath):
                print(f"Patched: {os.path.relpath(filepath, base_dir)}")
                count += 1
                
    print(f"\nPhase 2 finalize complete. Modified {count} files.")

if __name__ == "__main__":
    main()
