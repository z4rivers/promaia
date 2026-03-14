import libsql_experimental
import json

conn = libsql_experimental.connect("test_capabilities.db")
conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, is_active BOOLEAN, data TEXT)")
conn.execute("DELETE FROM test")

# Test RETURNING
res = conn.execute("INSERT INTO test (name, is_active, data) VALUES ('zack', True, '{\"key\": \"val\"}') RETURNING id")
row_id = res.fetchone()[0]
print(f"RETURNING support: OK, id={row_id}")

# Test Boolean and JSON parsing natively
res = conn.execute("SELECT name, is_active, data FROM test WHERE id = ?", (row_id,))
row = res.fetchone()
print(f"Native fetch data: {row}")
print(f"Boolean type: {type(row[1])} (Value: {row[1]})")
print(f"JSON data type: {type(row[2])} (Value: {row[2]})")

conn.execute("DROP TABLE test")
