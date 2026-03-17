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

import asyncio
import json
from pathlib import Path


class TestHealthChecks(unittest.TestCase):
    def test_detect_environment_local(self):
        from promaia.brain.health import detect_environment
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAILWAY_ENVIRONMENT", None)
            os.environ.pop("PYTHON_ENV", None)
            self.assertEqual(detect_environment(), "local")

    def test_check_database_returns_dict(self):
        from promaia.brain.health import check_database
        result = asyncio.run(check_database())
        self.assertIn("status", result)
        self.assertIn("backend", result)

    def test_check_env_vars_returns_dict(self):
        from promaia.brain.health import check_env_vars
        result = asyncio.run(check_env_vars())
        self.assertIn("status", result)
        self.assertIn("missing", result)

    def test_check_mcp_registration_returns_dict(self):
        from promaia.brain.health import check_mcp_registration
        result = asyncio.run(check_mcp_registration(
            host="127.0.0.1", port=8751, expected_token="test-token"
        ))
        self.assertIn("status", result)

    def test_run_checks_returns_full_structure(self):
        from promaia.brain.health import run_checks
        result = asyncio.run(run_checks())
        self.assertIn("status", result)
        self.assertIn("checks", result)
        self.assertIn("environment", result)
        self.assertIn("database", result["checks"])
        self.assertIn("env_vars", result["checks"])

    def test_check_server_port_returns_dict(self):
        from promaia.brain.health import check_server_port
        result = asyncio.run(check_server_port(port=8751))
        self.assertIn("status", result)

    def test_aggregate_status_logic(self):
        from promaia.brain.health import aggregate_status
        self.assertEqual(aggregate_status({"db": {"status": "ok"}, "env": {"status": "ok"}},
                                          critical=["db", "env"], non_critical=[]), "ok")
        self.assertEqual(aggregate_status({"db": {"status": "ok"}, "muninn": {"status": "unavailable"}},
                                          critical=["db"], non_critical=["muninn"]), "degraded")
        self.assertEqual(aggregate_status({"db": {"status": "error"}, "muninn": {"status": "ok"}},
                                          critical=["db"], non_critical=["muninn"]), "error")


if __name__ == "__main__":
    unittest.main()
