import os
import sys

# Add promaia to path if not running from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from promaia.storage.libsql_db import get_libsql_db

def test_libsql_db():
    print("Testing LibSQLDB wrapper...")
    db = get_libsql_db("test_wrapper.db")
    
    # 1. Test DDL
    print("1. Creating table...")
    db.execute("""
        CREATE TABLE IF NOT EXISTS wrapper_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_active BOOLEAN,
            metadata TEXT,
            name TEXT
        )
    """)
    db.execute("DELETE FROM wrapper_test")
    
    # 2. Test execute with params (%s -> ?)
    print("2. Testing execute with parameters...")
    rowcount = db.execute("INSERT INTO wrapper_test (name, is_active, metadata) VALUES (%s, %s, %s)", 
                          ("john", True, '{"role": "admin"}'))
    print(f"Rowcount after insert: {rowcount}")
    
    # 3. Test fetch_one & smart data handling
    print("3. Testing fetch_one with smart deserialization...")
    res = db.fetch_one("SELECT * FROM wrapper_test WHERE name = %s", ("john",))
    print(f"Fetched (john): {res}")
    assert res['is_active'] is True, "Boolean coercion failed"
    assert isinstance(res['metadata'], dict), "JSON deserialization failed"
    
    # 4. Test table_exists / column_exists
    print("4. Testing schema discovery...")
    assert db.table_exists("wrapper_test"), "table_exists failed"
    assert db.column_exists("wrapper_test", "name"), "column_exists failed"
    
    # 5. Test upsert
    print("5. Testing upsert...")
    db.upsert("wrapper_test", 
              {"id": res['id'], "name": "john_updated", "is_active": False, "metadata": '{"role": "user"}'},
              conflict_columns=["id"])
              
    res2 = db.fetch_one("SELECT * FROM wrapper_test WHERE id = %s", (res['id'],))
    print(f"Fetched (upserted): {res2}")
    assert res2['name'] == "john_updated"
    assert res2['is_active'] is False
    
    # 6. Test insert_returning
    print("6. Testing insert_returning...")
    new_id = db.insert_returning("INSERT INTO wrapper_test (name) VALUES (%s) RETURNING id", ("alice",))
    print(f"Returned ID: {new_id}")
    assert new_id is not None
    
    print("\nAll wrapper tests passed!")

if __name__ == "__main__":
    test_libsql_db()
