# Text Rendering Requirements

The Promaia display system has specific requirements for text rendering that balance visual appeal with copy-friendly functionality. This document outlines the key principles and implementation details.

## Core Principles

### 🎯 **Copy-First Design**
All text rendering must prioritize clean copy/paste functionality over visual effects. Users should be able to copy any output as clean, properly formatted markdown without artifacts.

### 🎨 **Subtle Visual Enhancement** 
While maintaining copyability, we use minimal, tasteful styling to improve readability:
- **Medium grey body text** (`white` style) for comfortable reading
- **Plain headings** without color to preserve markdown structure
- **Simple list formatting** using standard hyphens

## Key Benefits

✅ **No box characters** - Eliminates `┏━━━┓` artifacts that break copy/paste  
✅ **Dynamic width** - Automatically adapts to terminal window size  
✅ **Clean separators** - Uses simple dashes instead of complex borders  
✅ **Preserved structure** - Maintains markdown hierarchy when copied  
✅ **Configuration-driven** - Easy to customize via config file  
✅ **Copy-friendly lists** - Uses simple hyphens "-" instead of bullet characters  
✅ **Plain heading format** - Headings render without color styling, preserving `#` prefixes for perfect markdown copying  
✅ **Medium grey body text** - Perfect shade for comfortable reading while maintaining copy-friendly output
✅ **Fixed code block handling** - Code blocks now display properly without content skipping

## Text Styling Requirements

### Headers
- **H1**: `#` - Plain text, no styling
- **H2**: `##` - Plain text, no styling  
- **H3**: `###` - Plain text, no styling
- **Rationale**: Preserves exact markdown format when copied

### Body Text
- **Style**: Medium grey (`white`)
- **Rationale**: Perfect balance between readability and subtlety - not too dark, not too bright

### Inline Formatting
- **Bold**: `**text**` → `[bold]text[/bold]`
- **Italic**: `*text*` → `[italic]text[/italic]`
- **Code**: `` `text` `` → `[cyan]text[/cyan]`
- **Rationale**: Standard markdown formatting preserved, minimal color for readability

### Lists
- **Unordered**: Always use `-` (hyphen) for maximum compatibility
- **Ordered**: Preserve numbering `1.`, `2.`, etc.
- **Rationale**: Hyphens copy cleanly across all platforms

### Code Blocks
- **Style**: Minimal syntax highlighting
- **Background**: None (to avoid copy artifacts)
- **Rationale**: Clean code copying without terminal-specific formatting

## Implementation Notes

### Console Configuration
```python
# Copy-friendly console setup
Console(
    force_terminal=True,
    width=9999,  # Prevent wrapping
    soft_wrap=False,  # Disable automatic wrapping
    theme=minimal_theme
)
```

### Plain Mode Fallback
When `copy_friendly_mode=False`, the system falls back to completely plain text output without any styling.

## Testing Copy-Friendliness

To verify copy-friendly output:
1. Generate markdown content with headings, lists, code
2. Copy from terminal
3. Paste into markdown editor
4. Verify: No box characters, proper `#` prefixes, clean list formatting

Example of perfect copy output:
```markdown
# Main Heading
Regular body text content here.

## Sub Heading
- List item 1
- List item 2

### Details
**Bold text** and *italic text* with `code snippets`.
```

## Configuration

Set in `promaia.config.json`:
```json
{
  "copy_friendly_mode": true,
  "body_text_style": "white"
}
``` 