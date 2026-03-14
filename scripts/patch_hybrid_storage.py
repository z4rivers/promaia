import os
import re

def patch_hybrid_storage():
    filepath = '/home/zack/dev/promaia/promaia/storage/hybrid_storage.py'
    if not os.path.exists(filepath):
        filepath = r'C:\Users\Zachary Turner\dev\promaia\promaia\storage\hybrid_storage.py'
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. information_schema.tables -> sqlite_master
    content = content.replace(
        "SELECT COUNT(*) FROM information_schema.tables",
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    content = content.replace(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=%s"
    )
    content = content.replace(
        "SELECT table_name FROM information_schema.tables\n                    WHERE table_schema = 'public' AND table_name LIKE 'notion_%%'",
        "SELECT name FROM sqlite_master\n                    WHERE type = 'table' AND name LIKE 'notion_%%'"
    )
    
    # 2. information_schema.columns -> PRAGMA table_info
    # Old:
    # SELECT column_name, data_type 
    # FROM information_schema.columns 
    # WHERE table_schema = 'public' AND table_name = %s
    #     """, (table_name,))
    # columns = {row[0]: row[1] for row in cursor.fetchall()}
    
    # New:
    # PRAGMA table_info({table_name})
    # columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    # We will use regex to find this entire block and replace it
    old_col_query = r"""cursor\.execute\(""" + r'"""' + r"""\s*SELECT column_name\s*,\s*data_type\s*FROM information_schema\.columns\s*WHERE table_schema = 'public' AND table_name = %s\s*""" + r'"""' + r""", \(table_name,\)\)\s*columns = \{row\[0\]: row\[1\] for row in cursor\.fetchall\(\)\}"""
    
    new_col_query = """cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = {row[1]: row[2] for row in cursor.fetchall()}"""
                    
    content = re.sub(old_col_query, new_col_query, content, flags=re.MULTILINE)

    # 3. jsonb_build_object -> json_object
    content = content.replace('jsonb_build_object(', 'json_object(')
    
    # 4. View casts removals
    content = content.replace('NULL', 'NULL')
    content = content.replace('NULL', 'NULL')
    content = content.replace(") as metadata", ") as metadata")
    content = content.replace("\" if metadata_fields else \"NULL\"", "\" if metadata_fields else \"NULL\"")
    
    # 5. json_extract and casts
    content = content.replace("metadata->>'status'", "json_extract(metadata, '$.status')")
    content = content.replace("(metadata->>'featured')", "json_extract(metadata, '$.featured')")
    content = content.replace("metadata->>'priority'", "json_extract(metadata, '$.priority')")
    content = content.replace("metadata->>'category'", "json_extract(metadata, '$.category')")
    content = content.replace("metadata as metadata", "metadata")
    
    # 6. GIN index removal
    content = content.replace(" USING GIN (gmail_labels)", "")
    
    # 7. SERIAL PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
    content = content.replace("id SERIAL PRIMARY KEY", "id INTEGER PRIMARY KEY AUTOINCREMENT")
    
    # 8. CREATE OR REPLACE VIEW -> CREATE VIEW
    content = content.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("hybrid_storage.py patched successfully")

if __name__ == '__main__':
    patch_hybrid_storage()
