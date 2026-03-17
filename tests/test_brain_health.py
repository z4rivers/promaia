# tests/test_brain_health.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import time

class TestLibSQLSyncTracking(unittest.TestCase):
    def test_sync_age_returns_float(self):
        """LibSQLDB should track time since last sync."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        age = db.sync_age()
        self.assertIsInstance(age, float)
        self.assertGreaterEqual(age, 0.0)

    def test_try_sync_returns_bool(self):
        """try_sync() returns True on success, False on failure."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        result = db.try_sync()
        self.assertIsInstance(result, bool)

    def test_sync_age_updates_after_try_sync(self):
        """sync_age should reset after a successful try_sync."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        time.sleep(0.1)
        old_age = db.sync_age()
        if db.try_sync():
            new_age = db.sync_age()
            self.assertLess(new_age, old_age)

if __name__ == "__main__":
    unittest.main()
