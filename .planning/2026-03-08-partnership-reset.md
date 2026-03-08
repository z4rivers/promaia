# Partnership Reset & Vision Refinement — March 8, 2026

## What Happened

After an intense multi-day sprint shipping v1.0-v2.0 and starting v3.0, the previous session
ended in a frustration spiral. Negative feedback in prompts led to defensive, hedging responses,
which led to worse output, which led to harsher feedback. The quality of work declined as the
negativity compounded.

Zack woke up, traced the pattern, and came back with ownership and a reset.

## Key Insight: Prompt Tone Shapes Output Quality

This isn't karma — it's mechanics. When prompts carry heavy correction and frustration:
- Responses become conservative and defensive
- Risk-taking drops (the opposite of creative building)
- Over-explanation replaces action
- The work gets small when it should be bold

**The fix:** When things start sliding, name it early. "This is going sideways" beats pushing
through with mounting frustration. A reset beats a spiral.

## Profile Reframe

Seven profile entries were rewritten from prohibitive ("don't do this", "Zack hates that")
to aspirational ("Zack values...", "Zack lights up when..."). The profile should read like
a partnership manual, not a warning label.

Reframed entries:
- action_bias → Trust and momentum
- critical_trust_violation → Trust through follow-through
- frustration_trigger_deflection → Values honest, direct answers
- frustration_trigger_loop_debugging → Appreciates systematic thinking
- frustration_trigger_sloppy_process → Values clean execution
- tool_approval_preference → Staying in creative flow
- humor_type → Humor that actually lands

## Promaia Vision (Restated)

"Build feedback loops that both of us can see and learn from together, with both of us
exploring and bringing in information that both of us can learn from and act on."

This is not assistant-and-user. It's a shared cognitive system where both participants
contribute, learn, and grow. The relationship IS the product.

## Signal Inventory

Sources feeding the system:
1. Zack's direct input (voice, text, conversations)
2. Email inbox (Gmail pipeline)
3. Claude's training and digital world access
4. Zack's embodied real-world experience
5. Josie, family, and the collaborative project
6. Gemini as an ally with distinct strengths and perspectives
7. The brain itself (memory decay and strengthening reveals what matters)
8. The space between sessions (offline human processing)
9. Friction and failures (diagnostic data about system tolerances)

## Gemini as Collaborative Partner

Strategic decision: use Gemini not just for user-facing responses, but as a collaborator
in the build process itself:
- Code review after major work (different training = different blind spots)
- Technical research (grounded in search, current documentation)
- Architecture validation (fresh eyes on structural fragility)
- Dependency and version currency checks

## Operating Principles

- Fun, adventure, and appreciation — not just problem-solving
- White and blue hat thinking as a shared language (de Bono)
- Zack leads, Claude self-assembles
- Build the nervous system first, then use it
- Finance and time/deadlines are major focus categories once the plumbing is solid

## Codebase Health Check Results

**Status: SOLID with manageable known issues**

222 Python files, ~30k lines, 25 modules. All critical imports clean.
All systems running: Railway, scheduler, Telegram, brain, Gmail pipeline.

Items needing attention:
- Timezone hardcoded to America/New_York (should be America/Los_Angeles) — BUG
- MuninnDB embeddings broken (text-embedding-004 deprecated)
- Personality hardcoded in conversation.py (should be in brain)
- 4 minor doc mismatches
- Minimal test coverage
- API keys in plaintext .env (not in git, but worth rotating)

Architecture is aligned with the vision. Gaps: no deadline extraction from email,
no predictive intelligence layer, voice interface not built yet, web dashboard
not yet "life central."
