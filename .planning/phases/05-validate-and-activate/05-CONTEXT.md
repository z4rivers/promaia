# Phase 5 Context: Validate & Activate

**Phase Goal:** Agents produce real, useful output from live data -- no hallucinated facts, no broken queries, no missing context
**Requirements:** VALID-01, VALID-02, VALID-03, VALID-04

## Decisions

### 1. Gmail Context Loading Strategy

**Decision:** Implementation details are delegated -- no user involvement needed. Optimize for compatibility with upstream Promaia so updates don't break the integration.

- The executor currently expects `.md` files on disk but Gmail data is in Postgres. Fix the executor to load from Postgres directly.
- Keep the interface shape compatible with how Promaia's mail module already structures data, so cherry-picks from upstream don't require rework.
- **Schedule change:** Email-triage does NOT need to run every 2 hours. Zack is not mail-driven. Run email checks **3x/day**: morning, midday, and afternoon. Adjust the agent scheduler accordingly.

### 2. Content Completeness

**Decision:** Full message bodies required, not just snippets.

- `message_content` is currently NULL for all Gmail rows -- only `body_snippet` is populated. This must be fixed in the sync pipeline.
- Context matters for understanding mail. Snippets alone are not enough for agents to produce useful analysis.
- Fix the Gmail sync to populate `message_content` with full message bodies.
- If full body retrieval fails for a specific message, fall back to snippet but flag it as incomplete.

### 3. Agent Output Validation

**Decision:** Be suspicious of everything. Verify against source data. Assume hallucinated unless proven otherwise.

- **Spot-check approach:** After agent runs, cross-reference claims in agent output against actual Postgres data (email subjects, dates, senders, calendar events, brain memories).
- **Verification pattern:** If an agent references an email, the email must exist in the database with matching subject/sender/date. If it references a calendar event, it must exist. If it references a memory, it must exist.
- **Automated where possible:** Build lightweight post-run checks that compare referenced entities against source tables. Log discrepancies.
- **Manual spot-check:** For subjective quality (tone, usefulness, relevance), manual review during development. No need for ongoing automated quality scoring.

### 4. Error & Empty State Behavior

**Decision:** Always report what was checked, even when empty. Never silently skip or fabricate.

- When a data source returns nothing (no new emails, no calendar events, no pending actions), the agent must **explicitly say so**: "No new emails since last check" -- not silence, not filler.
- Knowing something was checked and found empty is valuable. It confirms the system is working.
- When SQL fails or a data source is unavailable, agents should **fail loud with clear error context** in logs, and produce partial output from whatever sources did work -- clearly noting what's missing.
- **Never hallucinate to fill gaps.** The first agent run fabricated facts when context was missing. The fix is: if you don't have data, say you don't have data.

## Known Bugs to Fix (from v1.0 agent runs)

These are documented and scoped -- not gray areas, just implementation targets:

1. **Gmail context loading** -- executor._load_initial_context() expects .md files on disk, Gmail pipeline writes to Postgres only. All 34 emails were skipped.
2. **SQL dialect bugs** -- gmail_labels is jsonb not array (ANY/ALL fails), email_date is text not timestamp, synced_time is text not timestamptz.
3. **message_content NULL** -- only body_snippet populated. Sync pipeline must store full bodies.
4. **Legacy mode token tracking** -- shows $0.00. SDK mode should track properly.
5. **Agent hallucination** -- first run claimed previous runs existed, cited fabricated costs. Root cause: missing context + no grounding validation.

## Schedule Change

| Agent | Old Schedule | New Schedule |
|-------|-------------|-------------|
| morning-briefing | Every 24h | Every 24h (no change) |
| email-triage | Every 2h | 3x/day (morning, midday, afternoon) |
| evening-digest | Every 24h | Every 24h (no change) |

## Deferred Ideas

None surfaced during discussion.

## Scope Boundary

This phase is strictly: fix existing bugs, load real data, validate output. No new agent capabilities, no new data sources, no new features. Make what exists work correctly.

---
*Discussed: 2026-03-06*
*Decisions by: Zack*
