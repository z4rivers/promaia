# Deferred Items - Phase 01

## Out-of-Scope Discoveries

### Backup file copies with old imports
- **Found during:** Plan 03, Task 1 verification
- **Files:** `promaia/storage/vector_db 2.py`, `promaia/ai/nl_orchestrator 2.py`, `promaia/utils/image_processing 3.py`, `promaia/write/interface 2.py`, `promaia/write/interface 3.py`
- **Issue:** These are macOS-style file copies (note spaces in filenames) with old chromadb and google.generativeai imports
- **Impact:** None -- these are not imported by any module. Python ignores files with spaces in names.
- **Recommendation:** Delete these backup files to keep the repo clean. They pre-date all zbrain changes.
