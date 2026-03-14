import os
import re

def process_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Revert datetime formats
        content = content.replace("?Y-?m-?d", "%Y-%m-%d")
        content = content.replace("?Y?m?d_?H?M?S", "%Y%m%d_%H%M%S")
        content = content.replace("?H:?M:?S", "%H:%M:%S")

        prompt_formats = [
            "LIMIT ?",
            "limit ?",
            "VALUES (?, ?, 'voice_pipeline', ?)",
            "page_id = ?",
        ]

        # Revert string interpolations formatted like: "something ?" % var 
        # But we must NOT touch ones that look like SQL string aggregations, 
        # so we will look specifically for variables ending in %s in logging
        content = content.replace("VALUES (?, ?, 'voice_pipeline', ?)", "VALUES (?, ?, 'voice_pipeline', ?)")
        
        # specific file repairs based on grep results:
        if "hybrid_query.py" in filepath:
            content = content.replace("metadata LIKE ?", "metadata LIKE ?")
            content = content.replace("title LIKE ?", "title LIKE ?")
            content = content.replace("', '.join('%s'", "', '.join('?'") # correct generator
            content = content.replace("', '.join('?' for _ in other_sources)", "', '.join('?' for _ in other_sources)")

        if "content_search.py" in filepath:
             content = content.replace("db_placeholders = ','.join(['?']", "db_placeholders = ','.join(['?']")
             
        if "files.py" in filepath:
             content = content.replace("placeholders = ','.join(['?']", "placeholders = ','.join(['?']")
             content = content.replace("thread_placeholders = ','.join(['?']", "thread_placeholders = ','.join(['?']")

        # We need a regex that matches quotes with a ? inside that are followed by a percent sign for string formatting
        pattern = r"([\"'][^\"']*)\?([^\"']*[\"']\s*%)"
        for _ in range(5): # iterative replacements for multiple per line
             content = re.sub(pattern, r"\1%s\2", content)
             
        if content != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed formatting in {filepath}")
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    for root, _, files in os.walk("promaia"):
        if "__pycache__" in root: continue
        for file in files:
            if file.endswith(".py"):
                process_file(os.path.join(root, file))

    for root, _, files in os.walk("scripts"):
        if "__pycache__" in root: continue
        for file in files:
            if file.endswith(".py"):
                process_file(os.path.join(root, file))

    print("Revert swept.")
