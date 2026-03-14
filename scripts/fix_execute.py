import os
import re

def fix_codebase():
    base_dir = r'/home/zack/dev/promaia' if os.name != 'nt' else r'C:\Users\Zachary Turner\dev\promaia'

    # Files containing the broken pattern
    files_to_fix = [
        "promaia/brain/core/memory_pipeline.py",
        "promaia/brain/channels/pc_scan.py",
        "promaia/brain/mcp/handlers/capture_ops.py",
        "promaia/brain/mcp/handlers/profile_ops.py",
        "promaia/telegram/brain_ops.py",
        "promaia/storage/vector_db.py",
        "promaia/storage/db_init.py"
    ]
    
    # We want to replace this generic pattern:
    # with db.get_connection() as conn:
    #     [optional spaces and register_vector(conn)]
    #     with conn.cursor() as cur:
    #         cur.execute(
    #             "...",
    #             (args)
    #         )
    # With:
    # db.execute("...", (args))
    
    # Because regexing AST over 7 files can be fragile, we'll do literal replacements
    # or regexes tailored to the exact formatting used in the codebase.
    
    for filepath in files_to_fix:
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            continue
            
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove register_vector entirely
        content = re.sub(r'^[ \t]*register_vector\(conn\)[ \t]*\n', '', content, flags=re.MULTILINE)
        
        # Replace `with db.get_connection() as conn:\n  with conn.cursor() as cur:\n    cur.execute(`
        # with `db.execute(` and fix indentation
        
        # Example from memory_pipeline.py:
        #         with db.get_connection() as conn:
        #             with conn.cursor() as cur:
        #                 cur.execute(
        #                     "UPDATE brain.memories SET embedding = %s WHERE id = %s",
        #                     (embedding_array, memory_id),
        #                 )
        
        pattern = r'([ \t]+)with (self\.)?db\.get_connection\(\) as conn:\n[ \t]+with conn\.cursor\(\) as (cur|cursor):\n[ \t]+(cur|cursor)\.(execute\()'
        
        def replacer(match):
            indent = match.group(1)
            self_db = match.group(2) or ""
            return f"{indent}{self_db}db.execute("
            
        content = re.sub(pattern, replacer, content)

        # Fix vector_db.py specifically for executemany
        pattern_executemany = r'([ \t]+)with (self\.)?db\.get_connection\(\) as conn:\n[ \t]+with conn\.cursor\(\) as (cur|cursor):\n[ \t]+(cur|cursor)\.(executemany\()'
        
        def replacer_executemany(match):
            indent = match.group(1)
            self_db = match.group(2) or ""
            return f"{indent}{self_db}db.execute_many("
            
        content = re.sub(pattern_executemany, replacer_executemany, content)

        # Fix the np.array(embedding) to json.dumps(embedding)
        # We need to change `embedding_array = np.array(embedding)`
        # to `embedding_array = json.dumps(embedding)`
        # BUT only if it's being used for DB insert. Actually, let's just make it json.dumps everywhere
        content = content.replace("np.array(embedding)", "json.dumps(embedding)")
        content = content.replace("np.array(sub_embedding)", "json.dumps(sub_embedding)")
        content = content.replace(", dtype=np.float32)", "") # clean up explicit dtypes if any
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    print("Codebase execute patterns and vector formats fixed")

if __name__ == '__main__':
    fix_codebase()
