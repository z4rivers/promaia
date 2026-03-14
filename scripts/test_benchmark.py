"""Quick benchmark to show off libSQL speeds."""
import os, sys, time
sys.path.insert(0, '/home/zack/dev/promaia')
os.environ['STORE_BACKEND'] = 'libsql'

from promaia.storage.db_factory import get_db
db = get_db()
print('========== libSQL SPEED BENCHMARKS ==========')

t0 = time.time()
counts = db.fetch_one("SELECT count(*) as c FROM memories")
t1 = time.time()
print(f"1. Count 900+ memories: {int((t1-t0)*1000)}ms")

t0 = time.time()
actions = db.fetch_all("SELECT * FROM actions WHERE status='pending'")
t1 = time.time()
print(f"2. Load 400+ pending actions: {int((t1-t0)*1000)}ms")

try:
    from promaia.storage.vector_db import get_vector_db
    vdb = get_vector_db()
    t0 = time.time()
    # Dummy embedding vector (768 dims for text-embedding-3-small)
    dummy_vector = [0.01] * 768
    results = vdb.search(dummy_vector, limit=5, table_name="memories")
    t1 = time.time()
    print(f"3. DiskANN Vector Semantic Search (768 dims, top 5): {int((t1-t0)*1000)}ms")
except Exception as e:
    print(f"3. Vector Search Error: {e}")
