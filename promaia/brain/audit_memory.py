"""
Memory auditor: Gemini sweeps planning docs against codebase reality.

Reads MEMORY.md, STATE.md, ROADMAP.md, and key source files, then asks
Gemini to find contradictions, stale info, wrong counts, and outdated statuses.

Usage:
    python -m promaia.brain.audit_memory
    python -m promaia.brain.audit_memory --fix  # also writes corrected MEMORY.md
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

from google import genai
from google.genai import types

from promaia.ai.models import GOOGLE_MODELS

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Memory file location
MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-Zachary-Turner-dev-promaia" / "memory"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"

# Planning docs to audit
PLANNING_DOCS = [
    ".planning/STATE.md",
    ".planning/ROADMAP.md",
    ".planning/MILESTONES.md",
    ".planning/v3.0-PLANS.md",
    ".planning/v3.0-VISION.md",
]

# Codebase files to cross-reference claims against
CODEBASE_FILES = [
    "promaia/brain/mcp_server.py",
    "promaia/brain/schema.sql",
    "promaia/telegram/bot.py",
    "promaia/telegram/conversation.py",
    "promaia/agents/scheduler.py",
    "promaia/runner.py",
    "promaia.config.json",
]

AUDIT_PROMPT = """You are a memory auditor. Your job is to find WRONG, STALE, or CONTRADICTORY information.

You are given two types of documents:
1. **Planning/memory docs** — these contain claims about the project's state, what's built, what's live, versions, counts, dates, and statuses.
2. **Codebase source files** — these are the ground truth of what actually exists.

## Your task

Cross-reference every factual claim in the planning/memory docs against the codebase source files. Report:

### Category 1: WRONG — Claims that contradict the source code
- Tool counts that don't match the actual tool registrations
- Table lists that don't match schema.sql
- Function names or signatures that don't match the code
- File paths that reference files that don't exist in the provided sources
- Agent configurations (intervals, schedules, models) that don't match the config

### Category 2: STALE — Information that was once true but has been superseded
- Sections describing v2.0 as "in progress" when it's complete
- "Next steps" that have already been done
- Status markers (NOT STARTED, IN PROGRESS) that should be COMPLETE
- Profile percentages or counts that are outdated
- Bug reports for bugs that have been fixed
- "UNFIXED" or "BLOCKED" items that may have been resolved

### Category 3: CONTRADICTIONS — Places where planning docs disagree with each other
- STATE.md says one thing, ROADMAP.md says another
- MEMORY.md claims a milestone status that conflicts with MILESTONES.md
- Version numbers or phase counts that don't align across files

### Category 4: MISSING — Important things in the codebase not reflected in docs
- New tables, tools, or modules that exist in code but aren't documented in MEMORY.md
- Capabilities that are live but not mentioned in planning docs

## Output format

For each finding, report:
- **File**: which planning doc contains the issue
- **Line/Section**: where in the doc
- **Issue**: what's wrong
- **Evidence**: what the source code actually shows
- **Severity**: HIGH (actively misleading) / MEDIUM (outdated but not harmful) / LOW (minor inaccuracy)

If everything checks out and there are no issues, say "CLEAN — no issues found."

Be precise. Cite specific line content and specific source code evidence. Do NOT speculate — only report issues you can prove from the provided files."""


def _read_file(path: Path) -> str | None:
    """Read a file, return contents or None if not found."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"Could not read {path}: {e}")
        return None


def _build_audit_payload() -> str:
    """Assemble all docs and source files into a single audit payload."""
    sections = []

    # Memory file
    memory_content = _read_file(MEMORY_FILE)
    if memory_content:
        sections.append(f"=== MEMORY.md (planning/memory doc) ===\n{memory_content}")
    else:
        sections.append("=== MEMORY.md === NOT FOUND")

    # Planning docs
    for rel_path in PLANNING_DOCS:
        full_path = PROJECT_ROOT / rel_path
        content = _read_file(full_path)
        if content:
            sections.append(f"=== {rel_path} (planning doc) ===\n{content}")
        else:
            sections.append(f"=== {rel_path} === NOT FOUND")

    # Codebase files
    for rel_path in CODEBASE_FILES:
        full_path = PROJECT_ROOT / rel_path
        content = _read_file(full_path)
        if content:
            sections.append(f"=== {rel_path} (source code — ground truth) ===\n{content}")
        else:
            sections.append(f"=== {rel_path} === NOT FOUND")

    return "\n\n".join(sections)


async def run_audit() -> str:
    """Run the memory audit via Gemini and return findings."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "ERROR: GOOGLE_API_KEY not set. Cannot run audit."

    client = genai.Client(api_key=api_key)
    payload = _build_audit_payload()

    print(f"Audit payload: {len(payload):,} chars across {len(PLANNING_DOCS) + len(CODEBASE_FILES) + 1} files")
    print("Sending to Gemini for analysis...")

    response = await asyncio.wait_for(
        client.aio.models.generate_content(
            model=GOOGLE_MODELS["pro"],
            contents=payload,
            config=types.GenerateContentConfig(
                system_instruction=AUDIT_PROMPT,
                temperature=0.2,
                max_output_tokens=16384,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=8192,
                ),
            ),
        ),
        timeout=180.0,
    )

    result = response.text

    # Log cost
    if response.usage_metadata:
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
        print(f"\nAudit cost: {input_tokens:,} in / {output_tokens:,} out = ${cost:.4f}")

    return result


async def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    print("=" * 60)
    print("MEMORY AUDITOR -- Gemini Pro cross-reference sweep")
    print("=" * 60)
    print()

    result = await run_audit()

    # Write findings to file FIRST (before print, in case of encoding issues)
    findings_path = PROJECT_ROOT / ".planning" / "AUDIT-FINDINGS.md"
    findings_path.write_text(
        f"# Memory Audit Findings\n\n"
        f"*Generated: {__import__('datetime').datetime.now().isoformat()}*\n\n"
        f"{result}\n",
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("AUDIT FINDINGS")
    print("=" * 60)
    print()
    print(result)
    print(f"\nFindings saved to: {findings_path}")


if __name__ == "__main__":
    asyncio.run(main())
