# Maia Test Suite

This directory contains comprehensive tests for the Maia CLI application.

## Test Categories

### 🧪 **Unit Tests**
- `test_cms_functionality.py` - Core CMS function tests with mocked data
- `test_chat_functionality.py` - Chat interface tests  
- `test_directory_structure.py` - File system organization tests

### 🌐 **Integration Tests**  
- `test_cms_real_content.py` - **NEW**: Real content CMS tests with live Notion API

### 📊 **Real Content Tests (test_cms_real_content.py)**

Tests CMS functionality against actual Notion data to ensure reliability:

#### **Test Coverage:**
1. **CMS Pull KOii Chat Context** - Verifies `maia cms pull` creates filtered content correctly
2. **Database Sync Unified Storage** - Tests `maia database sync --source cms` saves to proper locations  
3. **Content Filtering Comparison** - Ensures CMS pull vs database sync produce different filtered results
4. **Force Update Functionality** - Tests `--force` flag updates existing content
5. **Days Filter Options** - Validates filtering with different time ranges (7, 30, "all")
6. **Advanced Chat Filtering Syntax** - Tests property filtering: `cms.KOii_chat=true`, `cms:30.Reference=false`
7. **Help Commands** - Ensures all help commands work without errors

#### **What Gets Tested:**
- ✅ **Real API calls** to Notion using actual workspace credentials
- ✅ **Property filtering** with KOii chat and Reference checkboxes  
- ✅ **File structure** validation (JSON + markdown creation)
- ✅ **Content structure** verification (page ID, properties, content)
- ✅ **Metadata accuracy** (filters applied, page counts, timestamps)
- ✅ **Directory organization** (KOii-chat-context vs unified storage)
- ✅ **Advanced filtering syntax** parsing without shell escaping issues

#### **Running Real Content Tests:**
```bash
# Run all real content tests (requires API access)
python -m pytest tests/test_cms_real_content.py -v -s

# Run specific test
python -m pytest tests/test_cms_real_content.py::TestCMSRealContent::test_cms_pull_koii_chat_context -v -s

# Skip integration tests (if no API access)
python -m pytest tests/ -v -s -m "not integration"
```

## Test Results Summary

### ✅ **Verified Functionality:**
- **`maia cms pull`** correctly filters and saves 23 KOii chat pages
- **`maia database sync --source cms`** saves complete dataset to unified storage
- **Advanced filtering syntax** works without shell escaping: `cms.KOii_chat=true`
- **Property filtering** accurately filters by checkbox values
- **File structure** creates both JSON and markdown with proper content
- **Help commands** all function correctly

### 🎯 **Test Quality:**
- **Real data validation** - Tests against actual Notion content
- **Isolation** - Each test uses temporary workspace to avoid side effects  
- **Error handling** - Tests verify proper error messages and edge cases
- **Regression prevention** - Comprehensive coverage prevents future breakage

## Previous Test Documentation

The existing test suite includes:

### CMS Functionality Tests
- Notion client initialization validation
- Database querying with mocked responses
- Page property retrieval testing  
- Block content fetching validation
- Blog status filtering tests
- Data conversion testing
- CLI command functionality
- Configuration validation
- Field mapping verification

All tests are designed to prevent regressions and ensure the system remains reliable as new features are added.

## Running All Tests

```bash
# Run full test suite
python -m pytest tests/ -v -s

# Run with coverage
python -m pytest tests/ -v -s --cov=maia

# Run specific category
python -m pytest tests/test_cms_*.py -v -s
```

## Test Environment

Tests that involve real data syncing (like sync architecture tests) automatically:
1. Backup existing data before running
2. Create clean test environment
3. Restore original data after completion

This ensures tests don't interfere with your actual data. 