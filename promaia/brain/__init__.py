"""
Brain package for zBrain — persistent memory and AI OS layer.

This package provides:
- schema.sql.postgres-legacy: Archived legacy DDL (not executable against libSQL)
- Brain table creation now lives in promaia/storage/db_init.py (apply_brain_schema)
  and scripts/create_brain_tables_windows.py
- engine.py: 8 deterministic functions for mode detection, guardrails,
  time tracking, budget management, and context save/restore
"""
