"""Test if the web app imports cleanly."""
import sys
sys.path.insert(0, "/home/zack/dev/promaia")
import os
os.chdir("/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"

try:
    from promaia.web.main import app
    print("SUCCESS: Web app imports cleanly")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()
