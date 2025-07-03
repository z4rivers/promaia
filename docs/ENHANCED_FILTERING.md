# Enhanced Filtering for Maia Chat Command

## Overview

The Maia chat command supports advanced filtering to help you select specific content from your databases as context sources. This is particularly useful for blog posts, research, or any scenario where you need to focus on specific types of content.

## Syntax

### Single Source Filtering
For a single source, you can use filters with or without source prefixes:

```bash
# Both of these work for single sources
maia chat -s cms -f '"Reference"=true'
maia chat -s cms -f 'cms:"Reference"=true'
```

### Multi-Source Filtering ⭐ NEW
For multiple sources, **all filters must specify a source prefix** to avoid ambiguity:

```bash
# ✅ Correct: Source-specific filters
maia chat -s cms -s journal -f 'cms:"Reference"=true' -f 'journal:created_time>2025-01-01'

# ❌ Error: Global filter in multi-source scenario
maia chat -s cms -s journal -f '"Reference"=true'
```

## Filter Syntax Examples

### Basic Property Filters
```bash
# Boolean properties
maia chat -s cms -f 'cms:"Reference"=true'
maia chat -s cms -f 'cms:"Published"=false'

# Text properties
maia chat -s cms -f 'cms:"Status"=live'
maia chat -s cms -f 'cms:"Category"=blog'

# Properties with spaces (always use quotes)
maia chat -s cms -f 'cms:"Blog status"=live'
maia chat -s cms -f 'cms:"Content type"=article'
```

### Date Filters
```bash
# Recent content
maia chat -s journal -f 'journal:created_time>2025-01-01'
maia chat -s cms -f 'cms:last_edited_time<2024-12-31'

# Specific date ranges
maia chat -s cms -f 'cms:created_time>2025-01-01' -f 'cms:created_time<2025-02-01'
```

### Complex Expressions
You can use `and`/`or` operators within a single source:

```bash
# AND conditions
maia chat -s cms -f 'cms:"Reference"=true and "Blog status"=live'

# OR conditions  
maia chat -s cms -f 'cms:"Status"=draft or "Status"=review'

# Mixed conditions
maia chat -s cms -f 'cms:"Reference"=true and ("Status"=live or "Status"=published)'
```

### Multi-Source Complex Examples
```bash
# Different filters for different sources
maia chat -s cms -s journal -f 'cms:"Reference"=true and "Blog status"=live' -f 'journal:created_time>2025-01-01'

# Multiple filters per source (AND-ed together)
maia chat -s cms -s journal \
  -f 'cms:"Reference"=true' \
  -f 'cms:"Blog status"=live' \
  -f 'journal:created_time>2025-06-01'
```

## Property Names

### Built-in Properties
- `created_time` - When the page was created
- `last_edited_time` - When the page was last modified  
- `title` - Page title
- `page_id` - Unique page identifier

### Custom Properties
Any custom property from your Notion database can be used. Properties with spaces must be quoted:

```bash
# Custom checkbox property
maia chat -s cms -f 'cms:"Reference"=true'

# Custom select property
maia chat -s cms -f 'cms:"Blog status"=live'

# Custom multi-select property
maia chat -s cms -f 'cms:"Tags"=research'
```

## Filter Logic

### Single Filters
Each `-f` flag creates one filter condition.

### Multiple Filters  
Multiple `-f` flags are combined with AND logic:
```bash
# This means: Reference=true AND Status=live
maia chat -s cms -f 'cms:"Reference"=true' -f 'cms:"Status"=live'
```

### Within Filter Expressions
Within a single filter expression, you can use `and`/`or`:
```bash
# This means: Reference=true AND (Status=live OR Status=published)  
maia chat -s cms -f 'cms:"Reference"=true and ("Status"=live or "Status"=published)'
```

## Error Messages

### Multi-Source Global Filter Error
```
Error: In multi-source scenarios, all filters must specify a source prefix.
Example: Instead of '"Reference"=true', use 'source:"Reference"=true'
Available sources: cms, journal
```

### Invalid Source Error
```
Error: Filter source 'invalid' not found in specified sources.
Available sources: cms, journal
```

## Migration from Global Filters

If you're upgrading from the old global filter system:

### Before (Single Source - Still Works)
```bash
maia chat -s cms -f '"Reference"=true'
```

### After (Multi-Source - Required)
```bash
maia chat -s cms -s journal -f 'cms:"Reference"=true'  
```

## Best Practices

1. **Use source prefixes consistently** even for single sources to future-proof your commands
2. **Quote property names with spaces** to avoid parsing errors
3. **Test complex expressions** with debug mode: `MAIA_DEBUG=1 maia chat ...`
4. **Start simple** and build up complex filters incrementally

## Debug Mode

Enable debug mode to see how filters are parsed and applied:

```bash
MAIA_DEBUG=1 maia chat -s cms -s journal -f 'cms:"Reference"=true'
```

This will show:
- How filters are parsed
- Which filters apply to which sources  
- Filter summary before content loading
- Detailed processing information 