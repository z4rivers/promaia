import os
import re

def fix_cost_tracker():
    filepath = r'/home/zack/dev/promaia/promaia/agents/cost_tracker.py' if os.name != 'nt' else r'C:\Users\Zachary Turner\dev\promaia\promaia\agents\cost_tracker.py'
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    content = content.replace("from promaia.storage.db_factory import db_connect", "from promaia.storage.db_factory import get_db")
    
    # ensure_table 
    pattern = r'with db_connect\(\) as conn:\s*cursor = conn\.cursor\(\)\s*cursor\.execute\("""(.*?)"""\)\s*cursor\.execute\("""(.*?)"""\)\s*cursor\.execute\("""(.*?)"""\)\s*cursor\.execute\("""(.*?)"""\)\s*conn\.commit\(\)'
    
    def replacer_table(match):
        t1, t2, t3, t4 = match.groups()
        # Translate dialect
        t1 = t1.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        t1 = t1.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        
        return f'''db = get_db()
            db.execute("""{t1}""")
            db.execute("""{t2}""")
            db.execute("""{t3}""")
            db.execute("""{t4}""")'''
            
    content = re.sub(pattern, "db = get_db()\n            db.execute(\"\"\"\\1\"\"\")\n            db.execute(\"\"\"\\2\"\"\")\n            db.execute(\"\"\"\\3\"\"\")\n            db.execute(\"\"\"\\4\"\"\")", content, flags=re.DOTALL)
    
    # Translate dialect manually since regex matching 4 executes was fragile
    content = content.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    content = content.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
    
    # Fix execution blocks generic
    # `with db_connect() as conn:` -> `db = get_db()`
    content = content.replace("with db_connect() as conn:\n                cursor = conn.cursor()\n", "db = get_db()\n                ")
    content = content.replace("cursor.execute(", "db.execute(")
    content = content.replace("cursor.fetchone()", "cur.fetchone()")
    content = content.replace("cursor.fetchall()", "cur.fetchall()")
    content = content.replace("cursor.description", "cur.description")
    
    content = content.replace("db.execute(\"\"\"\n                    INSERT", "cur = db.execute(\"\"\"\n                    INSERT")
    content = content.replace("db.execute(\"\"\"\n                    SELECT", "cur = db.execute(\"\"\"\n                    SELECT")
    
    content = content.replace("conn.commit()\n", "")
    
    # Interval query fix
    content = content.replace("WHERE created_at >= CURRENT_DATE - INTERVAL '%s days'", "WHERE created_at >= date('now', '-' || %s || ' days')")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed cost_tracker.py")

if __name__ == '__main__':
    fix_cost_tracker()
