# Test: Browser Context Restoration from Chat History

## Issue
When restoring a chat from history that was created with a browse command (e.g., `maia chat -b trass`), the browser was launching but not restoring the original selections. Instead, it showed default or incorrect selections.

## Fix Applied
Modified `promaia/chat/interface.py` (lines 1465-1481) to:
1. Use `launch_unified_browser` instead of `launch_workspace_browser`
2. Pass saved `browse_selections` from history as `current_sources` parameter
3. This pre-selects the original sources when the browser launches

## Test Steps

### Setup
1. Ensure you have a workspace configured (e.g., `trass`)
2. The workspace should have multiple sources including Discord channels

### Test Case 1: Save and Restore Browse Command

1. **Create a new chat with browse command:**
   ```bash
   maia chat -b trass
   ```

2. **In the browser that appears:**
   - Deselect all default sources
   - Select specific Discord channels (e.g., 3 channels like):
     - `trass.yp#announcements`
     - `trass.yp#plush-and-merch-general`
     - `trass.yp#plush-announcements`
   - Confirm selection

3. **Have a conversation:**
   - Send a message and get a response
   - Note which sources were selected (should be shown at the top)

4. **Save the conversation:**
   ```
   /save
   ```
   - Note the saved conversation name

5. **Exit the chat:**
   ```
   /exit
   ```

6. **Load the conversation from history:**
   ```bash
   maia h
   ```
   - Select the conversation you just saved
   - Press Enter to load

7. **Verify browser restoration:**
   - The browser should launch again
   - **EXPECTED**: The same 3 Discord channels should be pre-selected
   - **PREVIOUS BUG**: Different sources were selected instead

8. **Confirm or adjust selections:**
   - Confirm the browser selections
   - Verify the chat shows the correct sources were loaded

### Test Case 2: Continue Conversation After Restore

1. **After loading from history (from Test Case 1):**
   - Send a new message referencing the Discord channels
   - Verify the AI has context from the correct channels

2. **Save again:**
   ```
   /save
   ```
   - This should update the existing conversation

3. **Load again:**
   ```bash
   maia h
   ```
   - Load the same conversation
   - Verify selections are still correct

### Expected Results

- ✅ Browser launches with the exact same sources pre-selected
- ✅ Source count matches the original selection
- ✅ Discord channels (if any) are correctly restored
- ✅ Regular database sources (if any) are correctly restored
- ✅ Conversation context is properly restored
- ✅ User sees the same "Context: maia chat -b <workspace>" message

### Common Issues to Check

1. **Wrong sources selected**: Should now be fixed with `current_sources` parameter
2. **No sources selected**: Check if `browse_selections` was saved correctly in history
3. **Browser doesn't launch**: Check workspace exists and is configured
4. **Error loading history**: Check `~/.maia_chat_history.json` is not corrupted

## Technical Details

### Changes Made

**File**: `promaia/chat/interface.py`

**Before** (lines ~1470-1471):
```python
from promaia.cli.workspace_browser import launch_workspace_browser
selected_sources = launch_workspace_browser(actual_workspace)
```

**After** (lines 1471-1481):
```python
from promaia.cli.workspace_browser import launch_unified_browser

# Check if we have saved browse_selections from history
saved_selections = context_state.get('browse_selections')
if saved_selections:
    debug_print(f"Restoring {len(saved_selections)} browse selections from history: {saved_selections}")

selected_sources = launch_unified_browser(
    workspace=actual_workspace,
    current_sources=saved_selections if saved_selections else None
)
```

### Why This Works

1. **`browse_selections` are saved** when using `/save` command (already working)
2. **`browse_selections` are passed** to `chat()` function when loading from history (already working)
3. **`browse_selections` are now used** to pre-populate the browser via `current_sources` parameter (NEW FIX)

### Debug Mode

To see detailed logging, enable debug mode:
```bash
export MAIA_DEBUG=1
maia h
```

Look for messages like:
- `"Restoring N browse selections from history: [...]"`
- `"STORED browse_selections in context_state: [...]"`

## Cleanup

After testing, you can clear your test history:
```python
from promaia.storage.chat_history import ChatHistoryManager
history_manager = ChatHistoryManager()
history_manager.clear_history()
```

Or manually delete: `~/.maia_chat_history.json`
