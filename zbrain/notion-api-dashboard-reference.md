# Notion API Dashboard Design Reference

> Comprehensive reference for creating beautiful Notion dashboard pages via the API.
> Researched March 2026. Covers API versions `2022-06-28` and `2025-09-03`.

---

## Table of Contents

1. [API Versions](#1-api-versions)
2. [All Block Types](#2-all-block-types-with-json-payloads)
3. [Rich Text & Annotations](#3-rich-text--annotations)
4. [Colors & Styling](#4-colors--styling)
5. [Page-Level Design (Icons, Covers)](#5-page-level-design)
6. [Column Layouts](#6-column-layouts)
7. [Inline Databases](#7-inline-databases)
8. [Database Property Types](#8-database-property-types)
9. [Database Views](#9-database-views)
10. [API Limits & Constraints](#10-api-limits--constraints)
11. [Markdown Content API (New)](#11-markdown-content-api)
12. [2025-2026 Platform Updates](#12-2025-2026-platform-updates)
13. [Dashboard Design Patterns](#13-dashboard-design-patterns)

---

## 1. API Versions

### `2022-06-28` (Legacy, Still Supported)
- Set via header: `Notion-Version: 2022-06-28`
- Full block type support as documented below
- Single data source per database
- Will continue working for existing single-source databases

### `2025-09-03` (Current)
- Set via header: `Notion-Version: 2025-09-03`
- **Multi-source databases**: separates "databases" (containers) from "data sources" (tables)
- **Markdown Content API**: three new endpoints for markdown-based page creation/editing
- **NOT backward-compatible** for multi-source database operations
- SDK v5.0.0+ only works well with this version
- New endpoint: `List data source templates`
- New parameters: `template` on Create Page, `template` and `erase_content` on Update Page

---

## 2. All Block Types with JSON Payloads

### Base Block Structure

Every block follows this pattern:

```json
{
  "object": "block",
  "type": "<block_type>",
  "<block_type>": {
    // type-specific properties
  }
}
```

When appending blocks, use `POST /v1/blocks/{block_id}/children` with a `children` array.

---

### 2.1 Paragraph

```json
{
  "object": "block",
  "type": "paragraph",
  "paragraph": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Hello world",
          "link": null
        }
      }
    ],
    "color": "default"
  }
}
```

**Supports children**: Yes (nested blocks)

---

### 2.2 Headings (heading_1, heading_2, heading_3)

```json
{
  "object": "block",
  "type": "heading_1",
  "heading_1": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Section Title"
        }
      }
    ],
    "color": "default",
    "is_toggleable": false
  }
}
```

**Key property**: `is_toggleable` (boolean)
- When `true`, heading acts as a toggle and supports children
- When `false`, heading is static (no children)
- To un-toggle: remove all children first, then set `is_toggleable: false`
- Works for all three heading levels

**Note**: Notion does NOT have heading_4 or deeper.

---

### 2.3 Callout

```json
{
  "object": "block",
  "type": "callout",
  "callout": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Important information here"
        }
      }
    ],
    "icon": {
      "type": "emoji",
      "emoji": "💡"
    },
    "color": "blue_background"
  }
}
```

**Icon options**:
```json
// Emoji icon
"icon": { "type": "emoji", "emoji": "🔥" }

// External image icon
"icon": { "type": "external", "external": { "url": "https://example.com/icon.png" } }
```

**Supports children**: Yes (blocks nested inside the callout)

---

### 2.4 Quote

```json
{
  "object": "block",
  "type": "quote",
  "quote": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "A meaningful quote"
        }
      }
    ],
    "color": "default"
  }
}
```

**Supports children**: Yes

---

### 2.5 Bulleted List Item

```json
{
  "object": "block",
  "type": "bulleted_list_item",
  "bulleted_list_item": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "List item text"
        }
      }
    ],
    "color": "default"
  }
}
```

**Supports children**: Yes (nested sub-bullets)

---

### 2.6 Numbered List Item

```json
{
  "object": "block",
  "type": "numbered_list_item",
  "numbered_list_item": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "First item"
        }
      }
    ],
    "color": "default"
  }
}
```

**Supports children**: Yes

---

### 2.7 To-Do

```json
{
  "object": "block",
  "type": "to_do",
  "to_do": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Task to complete"
        }
      }
    ],
    "checked": false,
    "color": "default"
  }
}
```

**Supports children**: Yes

---

### 2.8 Toggle

```json
{
  "object": "block",
  "type": "toggle",
  "toggle": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Click to expand"
        }
      }
    ],
    "color": "default"
  },
  "children": [
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [
          {
            "type": "text",
            "text": {
              "content": "Hidden content revealed on toggle"
            }
          }
        ]
      }
    }
  ]
}
```

**Supports children**: Yes (the content inside the toggle)

---

### 2.9 Code

```json
{
  "object": "block",
  "type": "code",
  "code": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "console.log('hello');"
        }
      }
    ],
    "language": "javascript",
    "caption": []
  }
}
```

**Language values**: `"abap"`, `"arduino"`, `"bash"`, `"basic"`, `"c"`, `"clojure"`, `"coffeescript"`, `"c++"`, `"c#"`, `"css"`, `"dart"`, `"diff"`, `"docker"`, `"elixir"`, `"elm"`, `"erlang"`, `"flow"`, `"fortran"`, `"f#"`, `"gherkin"`, `"glsl"`, `"go"`, `"graphql"`, `"groovy"`, `"haskell"`, `"html"`, `"java"`, `"javascript"`, `"json"`, `"julia"`, `"kotlin"`, `"latex"`, `"less"`, `"lisp"`, `"livescript"`, `"lua"`, `"makefile"`, `"markdown"`, `"markup"`, `"matlab"`, `"mermaid"`, `"nix"`, `"objective-c"`, `"ocaml"`, `"pascal"`, `"perl"`, `"php"`, `"plain text"`, `"powershell"`, `"prolog"`, `"protobuf"`, `"python"`, `"r"`, `"reason"`, `"ruby"`, `"rust"`, `"sass"`, `"scala"`, `"scheme"`, `"scss"`, `"shell"`, `"sql"`, `"swift"`, `"typescript"`, `"vb.net"`, `"verilog"`, `"vhdl"`, `"visual basic"`, `"webassembly"`, `"xml"`, `"yaml"`, `"java/c/c++/c#"`

---

### 2.10 Divider

```json
{
  "object": "block",
  "type": "divider",
  "divider": {}
}
```

**No properties** -- just an empty object.

---

### 2.11 Table of Contents

```json
{
  "object": "block",
  "type": "table_of_contents",
  "table_of_contents": {
    "color": "default"
  }
}
```

---

### 2.12 Breadcrumb

```json
{
  "object": "block",
  "type": "breadcrumb",
  "breadcrumb": {}
}
```

**No properties** -- just an empty object.

---

### 2.13 Column List & Column

```json
{
  "object": "block",
  "type": "column_list",
  "column_list": {},
  "children": [
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "object": "block",
          "type": "paragraph",
          "paragraph": {
            "rich_text": [
              {
                "type": "text",
                "text": { "content": "Column 1 content" }
              }
            ]
          }
        }
      ]
    },
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "object": "block",
          "type": "paragraph",
          "paragraph": {
            "rich_text": [
              {
                "type": "text",
                "text": { "content": "Column 2 content" }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Critical constraints**:
- Minimum: **2 columns** when creating
- Each column must have **at least 1 child block**
- Columns can only be children of `column_list`
- `column_list` can only contain `column` children
- Maximum: ~5 columns (UI supports up to 5; API likely similar)
- Columns can contain ANY block type except other columns

---

### 2.14 Bookmark

```json
{
  "object": "block",
  "type": "bookmark",
  "bookmark": {
    "caption": [
      {
        "type": "text",
        "text": { "content": "My bookmark caption" }
      }
    ],
    "url": "https://example.com"
  }
}
```

---

### 2.15 Embed

```json
{
  "object": "block",
  "type": "embed",
  "embed": {
    "url": "https://www.youtube.com/watch?v=example",
    "caption": []
  }
}
```

**Supported embed sources**: YouTube, Twitter/X, Google Maps, Google Drive, Figma, Invision, Framer, Whimsical, Miro, Abstract, Loom, Excalidraw, Sketch, Replit, CodePen, and more.

---

### 2.16 Link Preview

```json
{
  "object": "block",
  "type": "link_preview",
  "link_preview": {
    "url": "https://github.com/org/repo/pull/123"
  }
}
```

**Note**: Cannot be created via API; read-only. Created when users paste URLs in the Notion UI.

---

### 2.17 Image

```json
{
  "object": "block",
  "type": "image",
  "image": {
    "type": "external",
    "external": {
      "url": "https://example.com/image.png"
    },
    "caption": [
      {
        "type": "text",
        "text": { "content": "Image description" }
      }
    ]
  }
}
```

---

### 2.18 Video

```json
{
  "object": "block",
  "type": "video",
  "video": {
    "type": "external",
    "external": {
      "url": "https://www.youtube.com/watch?v=example"
    },
    "caption": []
  }
}
```

---

### 2.19 File

```json
{
  "object": "block",
  "type": "file",
  "file": {
    "type": "external",
    "external": {
      "url": "https://example.com/document.pdf"
    },
    "caption": [],
    "name": "document.pdf"
  }
}
```

---

### 2.20 PDF

```json
{
  "object": "block",
  "type": "pdf",
  "pdf": {
    "type": "external",
    "external": {
      "url": "https://example.com/file.pdf"
    },
    "caption": []
  }
}
```

---

### 2.21 Audio

```json
{
  "object": "block",
  "type": "audio",
  "audio": {
    "type": "external",
    "external": {
      "url": "https://example.com/audio.mp3"
    },
    "caption": []
  }
}
```

**Note**: Only the caption can be modified via API; the URL is read-only after creation.

---

### 2.22 Equation

```json
{
  "object": "block",
  "type": "equation",
  "equation": {
    "expression": "E = mc^2"
  }
}
```

Uses KaTeX syntax for mathematical expressions.

---

### 2.23 Synced Block

**Original (source) synced block**:
```json
{
  "object": "block",
  "type": "synced_block",
  "synced_block": {
    "synced_from": null
  },
  "children": [
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [
          {
            "type": "text",
            "text": { "content": "This content syncs everywhere" }
          }
        ]
      }
    }
  ]
}
```

**Reference (synced copy) synced block**:
```json
{
  "object": "block",
  "type": "synced_block",
  "synced_block": {
    "synced_from": {
      "type": "block_id",
      "block_id": "original-block-uuid"
    }
  }
}
```

**Note**: API does NOT support updating synced block content.

---

### 2.24 Table

```json
{
  "object": "block",
  "type": "table",
  "table": {
    "table_width": 3,
    "has_column_header": true,
    "has_row_header": false
  },
  "children": [
    {
      "object": "block",
      "type": "table_row",
      "table_row": {
        "cells": [
          [{ "type": "text", "text": { "content": "Header 1" } }],
          [{ "type": "text", "text": { "content": "Header 2" } }],
          [{ "type": "text", "text": { "content": "Header 3" } }]
        ]
      }
    },
    {
      "object": "block",
      "type": "table_row",
      "table_row": {
        "cells": [
          [{ "type": "text", "text": { "content": "Cell 1" } }],
          [{ "type": "text", "text": { "content": "Cell 2" } }],
          [{ "type": "text", "text": { "content": "Cell 3" } }]
        ]
      }
    }
  ]
}
```

**Key rules**:
- `table_width` can ONLY be set at creation time
- Must have at least 1 `table_row` whose `cells` array length matches `table_width`
- Each cell is an array of rich text objects

---

### 2.25 Table Row

```json
{
  "object": "block",
  "type": "table_row",
  "table_row": {
    "cells": [
      [{ "type": "text", "text": { "content": "Cell content" } }],
      [{ "type": "text", "text": { "content": "Another cell" } }]
    ]
  }
}
```

---

### 2.26 Child Page

```json
{
  "object": "block",
  "type": "child_page",
  "child_page": {
    "title": "Sub Page Name"
  }
}
```

---

### 2.27 Child Database

```json
{
  "object": "block",
  "type": "child_database",
  "child_database": {
    "title": "My Inline Database"
  }
}
```

**Note**: To create a full inline database with properties, use `POST /v1/databases` with `is_inline: true` and `parent.page_id`.

---

### 2.28 Link to Page

```json
{
  "object": "block",
  "type": "link_to_page",
  "link_to_page": {
    "type": "page_id",
    "page_id": "target-page-uuid"
  }
}
```

Also supports `"type": "database_id"` with `"database_id"`.

---

### 2.29 Template (DEPRECATED)

```json
{
  "object": "block",
  "type": "template",
  "template": {
    "rich_text": [
      {
        "type": "text",
        "text": { "content": "Template button text" }
      }
    ]
  },
  "children": [
    // blocks that get duplicated when template is used
  ]
}
```

**WARNING**: As of March 27, 2023, creation of template blocks via API is NO LONGER SUPPORTED. Existing template blocks can still be read.

---

### Block Types Summary Table

| Block Type | Supports Children | Supports Color | Creatable via API |
|---|---|---|---|
| paragraph | Yes | Yes | Yes |
| heading_1/2/3 | When is_toggleable=true | Yes | Yes |
| callout | Yes | Yes | Yes |
| quote | Yes | Yes | Yes |
| bulleted_list_item | Yes | Yes | Yes |
| numbered_list_item | Yes | Yes | Yes |
| to_do | Yes | Yes | Yes |
| toggle | Yes | Yes | Yes |
| code | No | No | Yes |
| divider | No | No | Yes |
| table_of_contents | No | Yes | Yes |
| breadcrumb | No | No | Yes |
| column_list | Yes (columns only) | No | Yes |
| column | Yes (any except column) | No | Yes |
| bookmark | No | No | Yes |
| embed | No | No | Yes |
| image | No | No | Yes |
| video | No | No | Yes |
| file | No | No | Yes |
| pdf | No | No | Yes |
| audio | No | No | Yes |
| equation | No | No | Yes |
| synced_block | Yes (original only) | No | Yes |
| table | Yes (table_rows only) | No | Yes |
| table_row | No | No | Yes |
| child_page | Yes | No | Yes |
| child_database | Yes | No | Yes |
| link_to_page | No | No | Yes |
| link_preview | No | No | **No** (read-only) |
| template | Yes | No | **No** (deprecated) |

---

## 3. Rich Text & Annotations

### Rich Text Object Structure

```json
{
  "type": "text",
  "text": {
    "content": "Styled text here",
    "link": {
      "url": "https://example.com"
    }
  },
  "annotations": {
    "bold": true,
    "italic": false,
    "strikethrough": false,
    "underline": false,
    "code": false,
    "color": "red"
  },
  "plain_text": "Styled text here",
  "href": "https://example.com"
}
```

### Rich Text Types

1. **text** -- Plain text with optional link
2. **mention** -- References to pages, users, dates, databases
3. **equation** -- Inline KaTeX expression

### Mention Types

```json
// User mention
{ "type": "mention", "mention": { "type": "user", "user": { "id": "user-uuid" } } }

// Page mention
{ "type": "mention", "mention": { "type": "page", "page": { "id": "page-uuid" } } }

// Date mention
{ "type": "mention", "mention": { "type": "date", "date": { "start": "2026-03-05" } } }

// Database mention
{ "type": "mention", "mention": { "type": "database", "database": { "id": "db-uuid" } } }
```

### Inline Equation

```json
{
  "type": "equation",
  "equation": {
    "expression": "\\frac{a}{b}"
  },
  "annotations": { "bold": false, "italic": false, "strikethrough": false, "underline": false, "code": false, "color": "default" },
  "plain_text": "\\frac{a}{b}",
  "href": null
}
```

---

## 4. Colors & Styling

### All Available Color Values

**Text colors** (apply to the text itself):
| Value | Description |
|---|---|
| `"default"` | Default text color (black in light mode, white in dark mode) |
| `"gray"` | Gray text |
| `"brown"` | Brown text |
| `"orange"` | Orange text |
| `"yellow"` | Yellow text |
| `"green"` | Green text |
| `"blue"` | Blue text |
| `"purple"` | Purple text |
| `"pink"` | Pink text |
| `"red"` | Red text |

**Background colors** (apply to the block or text background):
| Value | Description |
|---|---|
| `"gray_background"` | Gray background |
| `"brown_background"` | Brown background |
| `"orange_background"` | Orange background |
| `"yellow_background"` | Yellow background |
| `"green_background"` | Green background |
| `"blue_background"` | Blue background |
| `"purple_background"` | Purple background |
| `"pink_background"` | Pink background |
| `"red_background"` | Red background |

**Total**: 10 text colors + 9 background colors = **19 color values**

### Where Colors Apply

- **Block-level color**: Set on the block's `color` property (paragraph, heading, callout, quote, list items, to-do, toggle, table_of_contents)
- **Inline text color**: Set in `annotations.color` within rich text objects
- You can combine: a block with `blue_background` containing text with `annotations.color: "red"`

### Notion Hex Codes (for reference when rendering externally)

**Light Mode Text Colors**:
| Color | Hex |
|---|---|
| Default | `#37352F` |
| Gray | `#9B9A97` |
| Brown | `#64473A` |
| Orange | `#D9730D` |
| Yellow | `#DFAB01` |
| Green | `#0F7B6C` |
| Blue | `#0B6E99` |
| Purple | `#6940A5` |
| Pink | `#AD1A72` |
| Red | `#E03E3E` |

**Light Mode Background Colors**:
| Color | Hex |
|---|---|
| Gray | `#EBECED` |
| Brown | `#E9E5E3` |
| Orange | `#FAEBDD` |
| Yellow | `#FBF3DB` |
| Green | `#DDEDEA` |
| Blue | `#DDEBF1` |
| Purple | `#EAE4F2` |
| Pink | `#F4DFEB` |
| Red | `#FBE4E4` |

---

## 5. Page-Level Design

### Setting Page Icon

**Emoji icon**:
```json
PATCH /v1/pages/{page_id}
{
  "icon": {
    "type": "emoji",
    "emoji": "🚀"
  }
}
```

**External image icon**:
```json
{
  "icon": {
    "type": "external",
    "external": {
      "url": "https://example.com/icon.png"
    }
  }
}
```

**Custom emoji** (workspace-specific):
```json
{
  "icon": {
    "type": "custom_emoji",
    "custom_emoji": {
      "id": "custom-emoji-uuid",
      "name": "company_logo",
      "url": "https://..."
    }
  }
}
```

### Setting Page Cover

```json
PATCH /v1/pages/{page_id}
{
  "cover": {
    "type": "external",
    "external": {
      "url": "https://images.unsplash.com/photo-example"
    }
  }
}
```

**Best practices for covers**:
- Optimal dimensions: 1500x600px (or wider)
- Use high-quality images from Unsplash, custom brand images, or gradients
- Cover crops from center, so place important content centrally

### Creating a Page with Icon + Cover + Content

```json
POST /v1/pages
{
  "parent": {
    "page_id": "parent-page-uuid"
  },
  "icon": {
    "type": "emoji",
    "emoji": "📊"
  },
  "cover": {
    "type": "external",
    "external": {
      "url": "https://images.unsplash.com/photo-gradient"
    }
  },
  "properties": {
    "title": [
      {
        "type": "text",
        "text": {
          "content": "My Dashboard"
        }
      }
    ]
  },
  "children": [
    // block content here
  ]
}
```

---

## 6. Column Layouts

### Two-Column Layout

```json
{
  "object": "block",
  "type": "column_list",
  "column_list": {},
  "children": [
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "type": "callout",
          "callout": {
            "rich_text": [{ "type": "text", "text": { "content": "Status: Active" } }],
            "icon": { "type": "emoji", "emoji": "🟢" },
            "color": "green_background"
          }
        }
      ]
    },
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "type": "callout",
          "callout": {
            "rich_text": [{ "type": "text", "text": { "content": "Next Review: March 10" } }],
            "icon": { "type": "emoji", "emoji": "📅" },
            "color": "blue_background"
          }
        }
      ]
    }
  ]
}
```

### Three-Column Dashboard Header

```json
{
  "object": "block",
  "type": "column_list",
  "column_list": {},
  "children": [
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "type": "callout",
          "callout": {
            "rich_text": [{ "type": "text", "text": { "content": "12 Active Projects" } }],
            "icon": { "type": "emoji", "emoji": "📁" },
            "color": "purple_background"
          }
        }
      ]
    },
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "type": "callout",
          "callout": {
            "rich_text": [{ "type": "text", "text": { "content": "5 Tasks Due Today" } }],
            "icon": { "type": "emoji", "emoji": "⚡" },
            "color": "yellow_background"
          }
        }
      ]
    },
    {
      "object": "block",
      "type": "column",
      "column": {},
      "children": [
        {
          "type": "callout",
          "callout": {
            "rich_text": [{ "type": "text", "text": { "content": "87% Completion Rate" } }],
            "icon": { "type": "emoji", "emoji": "📈" },
            "color": "green_background"
          }
        }
      ]
    }
  ]
}
```

### Layout Rules

| Rule | Detail |
|---|---|
| Minimum columns | 2 |
| Maximum columns | ~5 (UI limit; API may accept more) |
| Column width | Auto-distributed equally; NOT controllable via API |
| Nested column_list | NOT allowed (no columns inside columns) |
| Required children | Each column MUST have at least 1 child |
| Column content | Any block type EXCEPT column/column_list |

---

## 7. Inline Databases

### Creating an Inline Database

```json
POST /v1/databases
{
  "parent": {
    "type": "page_id",
    "page_id": "parent-page-uuid"
  },
  "is_inline": true,
  "title": [
    {
      "type": "text",
      "text": { "content": "Task Tracker" }
    }
  ],
  "properties": {
    "Name": {
      "title": {}
    },
    "Status": {
      "select": {
        "options": [
          { "name": "Not Started", "color": "red" },
          { "name": "In Progress", "color": "yellow" },
          { "name": "Done", "color": "green" }
        ]
      }
    },
    "Due Date": {
      "date": {}
    },
    "Assignee": {
      "people": {}
    },
    "Priority": {
      "select": {
        "options": [
          { "name": "High", "color": "red" },
          { "name": "Medium", "color": "orange" },
          { "name": "Low", "color": "blue" }
        ]
      }
    }
  }
}
```

**Key**: `"is_inline": true` makes it appear embedded in the page (not as a child page).

---

## 8. Database Property Types

### All Supported Property Types

| Type | API Key | Creatable | Notes |
|---|---|---|---|
| Title | `"title": {}` | Yes | Exactly one per database (required) |
| Rich Text | `"rich_text": {}` | Yes | Multi-line text |
| Number | `"number": { "format": "number" }` | Yes | Formats: number, number_with_commas, percent, dollar, euro, pound, yen, ruble, rupee, won, yuan, real, lira, rupiah, franc, hong_kong_dollar, new_zealand_dollar, krona, norwegian_krone, mexican_peso, rand, new_taiwan_dollar, danish_krone, zloty, baht, forint, koruna, shekel, chilean_peso, philippine_peso, dirham, colombian_peso, riyal, ringgit, leu, argentine_peso |
| Select | `"select": { "options": [...] }` | Yes | Single choice |
| Multi-Select | `"multi_select": { "options": [...] }` | Yes | Multiple choices |
| Status | `"status": {}` | Yes | Groups: To-do, In progress, Complete |
| Date | `"date": {}` | Yes | Supports start/end dates |
| People | `"people": {}` | Yes | Workspace members |
| Files | `"files": {}` | Yes | Attachments |
| Checkbox | `"checkbox": {}` | Yes | Boolean |
| URL | `"url": {}` | Yes | Web links |
| Email | `"email": {}` | Yes | Email addresses |
| Phone Number | `"phone_number": {}` | Yes | Phone numbers |
| Formula | `"formula": { "expression": "..." }` | Yes | Computed values |
| Relation | `"relation": { "database_id": "..." }` | Yes | Links to another database |
| Rollup | `"rollup": { ... }` | Yes | Aggregates from relation |
| Created Time | `"created_time": {}` | Yes | Auto-filled |
| Created By | `"created_by": {}` | Yes | Auto-filled |
| Last Edited Time | `"last_edited_time": {}` | Yes | Auto-filled |
| Last Edited By | `"last_edited_by": {}` | Yes | Auto-filled |
| Unique ID | `"unique_id": {}` | Yes | Auto-incrementing ID |
| Button | N/A | **No** | UI-only, not creatable via API |

### Select/Multi-Select Color Options

Available colors for select options: `"default"`, `"gray"`, `"brown"`, `"orange"`, `"yellow"`, `"green"`, `"blue"`, `"purple"`, `"pink"`, `"red"`

---

## 9. Database Views

### View Types Available in Notion

| View | Description | Best For |
|---|---|---|
| Table | Spreadsheet-like rows/columns | Data-heavy views, bulk editing |
| Board | Kanban columns grouped by property | Status tracking, workflows |
| List | Compact single-column list | Simple overviews, reading lists |
| Calendar | Monthly/weekly calendar | Date-based planning |
| Timeline | Gantt-chart style | Project timelines, dependencies |
| Gallery | Card grid with previews | Visual content, portfolios |

### API Limitations for Views

**IMPORTANT**: The Notion API does NOT currently provide endpoints to:
- Create database views programmatically
- Configure view layout (gallery, board, etc.)
- Set view filters or sorts as "saved views"
- Control card size, preview properties, or grouping in views

**What you CAN do via API**:
- Create the database with properties (the data schema)
- Query the database with filters and sorts (ad-hoc, not saved)
- The default view when creating a database via API is **Table view**
- Views must be configured manually in the Notion UI or via the Notion MCP server

### Workaround: Query with Filters/Sorts

```json
POST /v1/databases/{database_id}/query
{
  "filter": {
    "property": "Status",
    "select": {
      "equals": "In Progress"
    }
  },
  "sorts": [
    {
      "property": "Due Date",
      "direction": "ascending"
    }
  ]
}
```

---

## 10. API Limits & Constraints

### Request Limits

| Limit | Value |
|---|---|
| Rate limit | 3 requests/second per integration |
| Block children per request | 100 blocks max |
| Payload size | 1000 block elements, 500KB max |
| Nesting depth per request | **2 levels** max |
| Rich text array length | 100 rich text objects per block |
| Rich text content length | 2000 characters per rich text object |
| Page title length | 2000 characters |
| Database title length | 2000 characters |

### Nesting Depth Workaround

Since only 2 levels of nesting are allowed per request, deeper structures require multiple API calls:

1. Create top-level blocks (returns block IDs)
2. Append children to those blocks using their IDs
3. Repeat for deeper nesting

```
Request 1: Create column_list > columns > paragraphs (2 levels)
Request 2: Append to a paragraph ID > toggle > content (2 more levels)
```

### Page Width

- Notion pages have two width modes: **default** (narrow, ~720px) and **full width**
- **Full width is NOT controllable via API** -- must be set in UI
- All API-created pages default to narrow width

---

## 11. Markdown Content API

### New in API Version 2025-09-03

Three endpoints for working with page content as markdown instead of block JSON:

### Create Page with Markdown

```
POST /v1/pages
Notion-Version: 2025-09-03
```

```json
{
  "parent": { "page_id": "parent-uuid" },
  "properties": {
    "title": [{ "type": "text", "text": { "content": "My Page" } }]
  },
  "markdown": "# Section 1\n\nThis is a paragraph.\n\n## Subsection\n\n- Item 1\n- Item 2\n\n> A blockquote\n\n```python\nprint('hello')\n```"
}
```

**Rules**:
- `markdown` is mutually exclusive with `children` and `content`
- Use `\n` for newlines in JSON strings
- If `properties.title` is omitted, first `# h1` is extracted as title

### Read Page as Markdown

```
GET /v1/pages/{page_id}/markdown
Notion-Version: 2025-09-03
```

Optional query parameter: `include_transcript=true` (for AI meeting notes)

### Update Page with Markdown

```
PATCH /v1/pages/{page_id}/markdown
Notion-Version: 2025-09-03
```

Uses ellipsis-based selections for partial updates.

---

## 12. 2025-2026 Platform Updates

### Notion 3.0 -- AI Agents (September 2025)
- AI rebuilt from the ground up as autonomous Agents
- Personal Agents: work up to 20+ minutes on multi-step tasks
- Can build project plans, compile feedback, draft reports, update hundreds of DB entries
- State-of-the-art memory system using Notion pages/databases

### Notion 3.2 -- Mobile AI (January 2026)
- Mobile AI support
- New AI models
- People directory

### Notion 3.3 -- Custom Agents (February 2026)
- Fully autonomous custom agents
- Trigger or schedule-based execution (24/7)
- Automate: task triaging, internal Q&A, daily standups, status reports
- 21,000+ custom agents created by early testers

### Workers
- Code execution environment for building custom AI Agent tools
- Developers write arbitrary code that Agents can execute
- Massive extensibility leap

### Notion Slides
- Native presentation feature
- Turn any Notion page into professional slides
- Auto-formats pages into clean slide layout
- Updates to source page instantly reflected

### API-Specific Updates
- Markdown Content API (3 endpoints)
- Multi-source databases (v2025-09-03)
- `UnsupportedBlockObjectResponse` now includes `block_type` string
- `notion-query-data-sources` MCP tool (Enterprise)
- File upload endpoint with `mode: "external_url"` for importing

### Official Notion MCP Server
- GitHub: `makenotion/notion-mcp-server`
- Available for integration with AI tools (Claude, etc.)

---

## 13. Dashboard Design Patterns

### Pattern 1: KPI Header Row

Use a `column_list` with callout blocks for key metrics:

```json
// 3-column header with colored callouts
column_list > [
  column > callout (green_background, "12 Active"),
  column > callout (yellow_background, "5 Due Today"),
  column > callout (red_background, "2 Overdue")
]
```

### Pattern 2: Section Organization

```json
// Divider
divider

// Toggle heading for collapsible sections
heading_2 (is_toggleable: true, "📋 Current Sprint")
  > child_database (inline task tracker)

divider

heading_2 (is_toggleable: true, "📊 Metrics")
  > table (status summary)
```

### Pattern 3: Status Dashboard

```json
// Page setup
icon: "📊"
cover: gradient or branded image

// Breadcrumb for navigation context
breadcrumb

// Title area (auto from page title)

// KPI row
column_list (3 columns of callouts)

// Divider
divider

// Quick links section
heading_2 "Quick Links"
column_list [
  column > bookmark(url1), bookmark(url2)
  column > bookmark(url3), bookmark(url4)
]

// Task section
heading_2 (is_toggleable: true) "Active Tasks"
  > child_database (inline, is_inline: true)

// Notes section
heading_2 (is_toggleable: true) "Recent Notes"
  > synced_block (from notes page)

// Table of contents (at top or bottom)
table_of_contents
```

### Design Best Practices

1. **Use callout blocks as "cards"** -- combine emoji icons + background colors for visual hierarchy
2. **Toggle headings for sections** -- keeps the page clean; users expand what they need
3. **Dividers between major sections** -- visual separation
4. **Columns for side-by-side comparisons** -- 2-3 columns works best (4+ gets cramped)
5. **Consistent color scheme** -- pick 2-3 background colors and use them consistently
6. **Emoji as visual anchors** -- use consistent emoji per category (📁 projects, ⚡ tasks, 📅 dates)
7. **Table of contents** -- for pages with 4+ sections
8. **Inline databases** -- the most powerful dashboard component; use for dynamic content
9. **Synced blocks** -- reuse content across dashboard pages (change once, updates everywhere)
10. **Cover + icon** -- first impression matters; use branded or thematic images

### Color Pairing Recommendations

| Purpose | Background | Text/Icon |
|---|---|---|
| Success/Active | `green_background` | 🟢 ✅ |
| Warning/Pending | `yellow_background` | ⚠️ 🔶 |
| Error/Overdue | `red_background` | 🔴 ❌ |
| Info/Neutral | `blue_background` | 💡 ℹ️ |
| Creative/Feature | `purple_background` | 🎨 ✨ |
| Archive/Inactive | `gray_background` | 📦 🗃️ |

---

## Appendix: Complete API Endpoint Reference for Dashboard Building

| Action | Method | Endpoint |
|---|---|---|
| Create page | POST | `/v1/pages` |
| Update page (icon, cover) | PATCH | `/v1/pages/{page_id}` |
| Append blocks | PATCH | `/v1/blocks/{block_id}/children` |
| Retrieve block children | GET | `/v1/blocks/{block_id}/children` |
| Update block | PATCH | `/v1/blocks/{block_id}` |
| Delete block | DELETE | `/v1/blocks/{block_id}` |
| Create database | POST | `/v1/databases` |
| Query database | POST | `/v1/databases/{database_id}/query` |
| Update database | PATCH | `/v1/databases/{database_id}` |
| Create page (markdown) | POST | `/v1/pages` (with `markdown` param) |
| Read page markdown | GET | `/v1/pages/{page_id}/markdown` |
| Update page markdown | PATCH | `/v1/pages/{page_id}/markdown` |
| Search | POST | `/v1/search` |

**Base URL**: `https://api.notion.com`

**Required Headers**:
```
Authorization: Bearer {integration_token}
Notion-Version: 2025-09-03
Content-Type: application/json
```
