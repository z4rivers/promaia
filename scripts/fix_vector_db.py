import os
import re

def rewrite_vector_db():
    filepath = r'/home/zack/dev/promaia/promaia/storage/vector_db.py' if os.name != 'nt' else r'C:\Users\Zachary Turner\dev\promaia\promaia\storage\vector_db.py'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Remove _register_vector_on_connection and _get_vector_connection
    # They are around line 59 to 71
    content = re.sub(
        r'^[ \t]*def _register_vector_on_connection\(self\):.*?^[ \t]*def _init_embedding_function\(self\):',
        '    def _init_embedding_function(self):',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # 2. Fix the init method which calls _register_vector_on_connection
    content = content.replace("            self._register_vector_on_connection()", "            pass # Vector registry handled by generic DB schema in LibSQL")
    
    # 3. Fix delete_property_embedding
    pattern = r'self\.db\.execute\(\s*"DELETE FROM property_embeddings WHERE page_id = %s AND property_name = %s",\s*\[page_id, property_name\]\s*\)\s*deleted = cur\.rowcount > 0'
    replacement = r'''cur = self.db.execute("DELETE FROM property_embeddings WHERE page_id = %s AND property_name = %s", [page_id, property_name])
            deleted = cur.rowcount > 0'''
    content = re.sub(pattern, replacement, content)
    
    # 4. Fix delete_property_embeddings
    pattern = r'self\.db\.execute\(sql, params\)\s*count = cur\.rowcount'
    replacement = r'''cur = self.db.execute(sql, params)
            count = cur.rowcount'''
    content = re.sub(pattern, replacement, content)
    
    # 5. Fix search_property
    # Needs to replace `<=> %s::vector` with `vector_distance_cos(embedding, %s)`
    # Note: For libSQL, vector_distance_cos(embedding, ?) returns cosine distance.
    # So 1 - distance is similarity_score.
    content = content.replace("1 - (embedding <=> %s::vector) AS similarity_score,", "1 - vector_distance_cos(embedding, %s) AS similarity_score,")
    content = content.replace("ORDER BY embedding <=> %s::vector", "ORDER BY vector_distance_cos(embedding, %s)")
    
    # Fix the execution
    pattern = r'with self\.db\.get_connection\(\) as conn:\s*with conn\.cursor\(cursor_factory=psycopg2\.extras\.RealDictCursor\) as cur:\s*cur\.execute\(sql, params\)\s*rows = cur\.fetchall\(\)'
    replacement = r'''cur = self.db.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]'''
    content = re.sub(pattern, replacement, content)
    
    # 6. Fix search
    # Replace `<=> %s::vector` with `vector_distance_cos`
    content = content.replace("1 - (embedding <=> %s::vector) AS similarity_score,", "1 - vector_distance_cos(embedding, %s) AS similarity_score,")
    content = content.replace("ORDER BY embedding <=> %s::vector", "ORDER BY vector_distance_cos(embedding, %s)")
    
    # 7. Fix check_exists
    pattern = r'self\.db\.execute\("SELECT 1 FROM content_embeddings WHERE page_id = %s LIMIT 1", \[page_id\]\)\s*return cur\.fetchone\(\) is not None'
    replacement = r'''cur = self.db.execute("SELECT 1 FROM content_embeddings WHERE page_id = %s LIMIT 1", [page_id])
            return cur.fetchone() is not None'''
    content = re.sub(pattern, replacement, content)
    
    # 8. Fix get_stats
    pattern = r'self\.db\.execute\("SELECT COUNT\(\*\) FROM content_embeddings"\)\s*content_count = cur\.fetchone\(\)\[0\]\s*cur\.execute\("SELECT COUNT\(\*\) FROM property_embeddings"\)\s*property_count = cur\.fetchone\(\)\[0\]'
    replacement = r'''cur = self.db.execute("SELECT COUNT(*) FROM content_embeddings")
            content_count = cur.fetchone()[0]

            cur = self.db.execute("SELECT COUNT(*) FROM property_embeddings")
            property_count = cur.fetchone()[0]'''
    content = re.sub(pattern, replacement, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed vector_db.py")

if __name__ == '__main__':
    rewrite_vector_db()
