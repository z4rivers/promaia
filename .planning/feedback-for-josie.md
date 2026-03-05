# Feedback for Josie (Koii Benvenutto)

Issues encountered while building zBrain on the `zbrain` branch. These are things that might affect the main Promaia platform too.

---

## Issue 1: MCP env var interpolation doesn't work

**Commit:** 8c1b8a7
**Problem:** `.mcp.json` had `"env": {"DATABASE_URL": "${DATABASE_URL}"}` expecting Claude Code to interpolate shell variables. It doesn't — the MCP server started with no database credentials or API keys, so it silently failed to connect.

**Fix:** Removed `env` block from `.mcp.json`. The MCP server now loads `.env` itself using `python-dotenv` at import time (walks up from `mcp_server.py` to find the project root `.env`).

**Upstream impact:** If Promaia ever registers other MCP servers via `.mcp.json`, don't rely on `${VAR}` interpolation in the env block. Use dotenv inside the server instead.

---

## Issue 2: Gemini embeddings returned wrong dimensions

**Commit:** bd5a1dc
**Problem:** `vector_db.py` called `genai_client.models.embed_content(model='gemini-embedding-001', contents=text)` without specifying output dimensions. `gemini-embedding-001` defaults to 3072 dimensions, but the database column is `vector(768)`. Inserts failed with a dimension mismatch.

**Fix:** Added `config={'output_dimensionality': 768}` to the `embed_content()` call. This tells the API to return 768-dim vectors matching the schema.

**Upstream impact:** If Promaia uses `gemini-embedding-001` anywhere, the dimension must be explicitly set. The default (3072) is probably not what you want — it's wasteful and requires huge vector columns.

---

*Last updated: 2026-03-04*
*Will add more issues as they come up.*
