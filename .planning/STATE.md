# State: zBrain

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-04 — Milestone v1.0 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-04)

**Core value:** Claude has persistent, cross-session memory across all of Zack's projects — eliminating the amnesia problem.
**Current focus:** Milestone initialization

## Accumulated Context

- Extensive design session completed (see docs/plans/2026-03-04-zbrain-promaia-merge-design.md)
- Promaia codebase explored: 359 files, Python, connectors architecture, agent orchestration in dev
- Daughter's postgres-sql-changeover branch reviewed: 586-line schema, PostgresDB singleton, connection pooling
- Previous "Open Brain" plan at ~/.claude/plans/vast-gathering-widget.md — superseded by Promaia merge approach
- 5 YouTube videos analyzed (Nate Jones, Obsidian+Claude, NotebookLM)
- OpenClaw research completed — heartbeat pattern adopted, but staying in Claude ecosystem

## Blockers

None currently.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter is re-initializing the repo to remove personal identifiers. Before that happens, export zbrain work as patches: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`. After re-init, clone fresh repo, create new zbrain branch, apply patches with `git am`. Additive work (new files) applies cleanly. Modified files (vector_db.py, postgres_db.py) may need manual re-application.

## Pending Todos

- [x] Create zbrain branch (done — branch exists, first commit made)
- [ ] Merge postgres-sql-changeover into zbrain
- [ ] Write ZBRAIN.md (running changelog of all changes for daughter's visibility)
- [ ] Update memory files with Promaia/zBrain context
- [ ] Export patches before daughter's re-init
