# Onboarding Session Learnings - 2025-10-02

### 🔴 High Priority - Blockers

- [x] **README Update: pip3 and python3** - ✅ COMPLETED
  - Updated all references from `pip` to `pip3` and `python` to `python3`

- [x] **Virtual Environment Setup Missing from README** - ✅ COMPLETED
  - Added instructions for: `brew install uv` → `uv venv` → `source venv/bin/activate` → `uv pip install .` → `pip3 install -e .`
  - Included activation instructions and environment setup guidance

- [x] **Config File Template Issue** - ✅ COMPLETED
  - Created clean `promaia.config.template.json` with no personal data
  - Template has empty databases and workspaces objects
  - Ready for fresh installs without personal config pollution

- [x] **Default Workspace Hard-coded** - ✅ COMPLETED
  - Changed default workspace from "koii" to "default" throughout codebase
  - Updated `promaia/config/workspaces.py` and `promaia/config/databases.py`
  - No longer hard-codes personal workspace names

### 🟡 Medium Priority - UX Issues

- [x] **Command Line Argument Standard** - ✅ COMPLETED
  - Changed `maia workspace add` to use `--api-key` flag instead of positional argument
  - Updated `maia database add` to support both `--id` and `--database-id` with help text
  - README examples updated to reflect new standard format

- [x] **Notion Database ID Instructions** - ✅ COMPLETED
  - Added inline help text in CLI: `--id` flag shows example URL format
  - Added instructions in README Initial Setup section
  - Clarified: ID is between slash and question mark in Notion URL

- [ ] **Environment Setup Script** - Consider creating an interactive onboarding script
  - Guide users through adding environment variables
  - Would reduce need for IDE during initial setup
  - Lower priority since users need IDE for config anyway

- [ ] **Split Promaia into a separate repo from the main branch which holds the koii chat features

### 🟢 Low Priority - Documentation & Polish

- [x] **Notion Integration Requirement** - ✅ COMPLETED
  - Added note in README that Notion is optional for basic chat
  - Clarified that basic `maia chat` works with just AI API keys
  - Notion integration enhances functionality but isn't strictly required

- [x] **API Key Format Documentation** - ✅ COMPLETED
  - Added "Environment Variables & API Keys" section to README
  - Shows template literal format with examples
  - Explains how `.env` values are interpolated at runtime

- [x] **Workspace vs Database Concept** - ✅ COMPLETED
  - Added "Understanding Workspaces & Databases" section in README
  - Clearly explains workspace = Notion account/team
  - Clarifies database = individual Notion databases
  - Notes that schema is adaptive to any database structure

---

## ✅ Implementation Summary (2025-10-02)

All selected high and medium priority onboarding issues have been resolved:

### Code Changes:
1. **CLI Commands** - Updated to use standard `--api-key` flag format
2. **Default Workspace** - Changed from "koii" to "default" throughout codebase
3. **Config Template** - Created clean `promaia.config.template.json`

### Documentation Updates:
1. **Virtual Environment Setup** - Added comprehensive uv installation guide
2. **Notion Database ID** - Added instructions and inline help
3. **Environment Variables** - Documented template literal format
4. **Notion Requirement** - Clarified it's optional for basic chat
5. **Workspace/Database Concepts** - Added explanatory section

### Files Modified:
- `README.md` - Enhanced with setup instructions and clarifications
- `promaia/cli/workspace_commands.py` - CLI argument standard
- `promaia/cli/database_commands.py` - Added help text for database ID
- `promaia/config/workspaces.py` - Fixed hard-coded workspace name
- `promaia/config/databases.py` - Fixed hard-coded workspace name
- `promaia.config.template.json` - New clean template created

### Remaining Items:
- Environment setup script (nice-to-have)
- Split web app into separate repo (architectural decision)