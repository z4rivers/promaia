import logging
logging.basicConfig(level=logging.INFO)

from promaia.utils.config import load_environment
load_environment()

from promaia.storage.vector_db import get_vector_db_manager

try:
    vdb = get_vector_db_manager()
    page_id = 'test-libsql-vector-1'
    content = 'This is a test of the libSQL semantic search capabilities running locally in WSL.'
    
    # 1. Test Insert (F32_BLOB packing)
    insert_res = vdb.add_content(
        page_id=page_id,
        content_text=content,
        metadata={'workspace': 'default', 'database_name': 'test_db'}
    )
    
    if insert_res:
        print('VECTOR INSERT SUCCESS')
    else:
        print('VECTOR INSERT FAILED')
        
    # 2. Test Search (DiskANN similarity score)
    search_res = vdb.search(
        query_text='local semantic search',
        filters={'workspace': 'default'},
        n_results=1
    )
    
    if search_res:
        print('VECTOR SEARCH SUCCESS: Found', len(search_res), 'results.')
        print('Top match score:', search_res[0].get('similarity_score'))
    else:
        print('VECTOR SEARCH FAILED: No results returned.')
        
except Exception as e:
    import traceback
    print('VECTOR EXCEPTION:', e)
    traceback.print_exc()
