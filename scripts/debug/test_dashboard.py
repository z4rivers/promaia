"""Verify dashboard.py compiles and _get_brain_data works with libSQL."""
import os, sys, json
sys.path.insert(0, "/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"

# Step 1: compile check
try:
    import py_compile
    py_compile.compile("/home/zack/dev/promaia/promaia/web/routers/dashboard.py", doraise=True)
    print("1. COMPILE: OK")
except py_compile.PyCompileError as e:
    print(f"1. COMPILE: FAIL - {e}")
    sys.exit(1)

# Step 2: import check
try:
    from promaia.web.routers.dashboard import _get_brain_data
    print("2. IMPORT: OK")
except Exception as e:
    print(f"2. IMPORT: FAIL - {e}")
    sys.exit(1)

# Step 3: data check
try:
    data = _get_brain_data()
    print(f"3. DATA: OK")
    print(f"   brain_status: {json.dumps(data['brain_status'])}")
    print(f"   actions: {len(data['actions'])} items")
    print(f"   projects: {len(data['projects'])} items")
    print(f"   recent_memories: {len(data['recent_memories'])} items")
    if data['projects']:
        print(f"   first project: {data['projects'][0]['name']}")
    if data['recent_memories']:
        print(f"   latest memory: {data['recent_memories'][0]['content'][:60]}...")
except Exception as e:
    print(f"3. DATA: FAIL - {e}")
    import traceback
    traceback.print_exc()
