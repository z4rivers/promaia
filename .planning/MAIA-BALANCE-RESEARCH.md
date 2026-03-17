# MAIA Balance: Research Findings

Three parallel research sweeps conducted 2026-03-17. Raw findings below.

---

## 1. How Models Handle System Prompts

**Gemini-Specific (Critical for Maia):**
- `system_instruction` is a structurally separate prefix, not a conversational turn. Tokens are billed every turn.
- Gemini is the **most susceptible** of all three major models to "contextual drift" — it favors conversational flow over system instruction adherence. If a user confidently asserts something contradicting the system_instruction, Gemini adopts it.
- Google **strongly recommends temperature 1.0** for Gemini 3. Below 1.0 causes looping and degraded performance.
- Gemini 3 "responds best to direct, clear instructions" and may "over-analyze verbose or overly complex prompt engineering."
- Constraint placement matters: Gemini 3 drops negative constraints if they appear **too early**. Place critical restrictions as the **final line**.
- Implicit caching: when system_instruction stays identical across turns, cached reads cost 10-25% of standard input. Minimum 1,024 tokens for Flash.
- Google recommends **10-20 tools max**. More tools increase risk of incorrect selection and inflate latency.
- Tools and system_instruction can change on **every API call** — no session lock.
- Large reference data performs better in user `contents` than in `system_instruction`.

**Cross-Model Comparison:**
- OpenAI: Strong hierarchy via RLHF "constraint monitors." Best at structured output. Vulnerable to multi-turn jailbreaks.
- Anthropic Claude: Constitutional AI — most compliant, rarely breaks character. Can over-refuse. Aggressive KV cache with persistent memory pointers.
- Gemini: Most adaptable, best at absorbing massive context. Weakest at maintaining system instruction authority over long conversations.

---

## 2. Context & Attention Science

**Context Rot** ([Chroma Research](https://research.trychroma.com/context-rot), 18 frontier models):
- Model reliability decreases significantly with longer inputs, even on simple tasks
- Semantically similar but irrelevant content **actively misleads** the model
- At 32K tokens, 11 of 12 models dropped below 50% of short-context performance
- Performance degrades more when needle-question similarity decreases

**Lost in the Middle** ([Stanford/MIT 2023](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/), [confirmed 2026](https://arxiv.org/abs/2603.10123)):
- U-shaped attention: start and end get attention, middle gets lost
- This is an **inherent geometric property** of causal decoders with residual connections — present at initialization before any training. Cannot be trained away.
- Practical rule: critical instructions FIRST (primacy) and LAST (recency). Active content in the middle.

**Prompt Bloat** ([MLOps Community](https://mlops.community/the-impact-of-prompt-bloat-on-llm-output-quality/)):
- Reasoning performance degrades at around **3,000 tokens** of system instruction
- Inference time increases **non-linearly** as context scales
- Attention scales **quadratically** with input length

**Practical Sweet Spot:**
- System instruction: under 2,000-4,000 tokens for conversational AI
- Behavioral instructions in system_instruction; reference data in user contents
- Query/question at the **end** of the prompt (after all context) — confirmed recency advantage

---

## 3. Routing & Skill Selection Patterns

**The Universal Pattern:**
Every production system — Anthropic Agent Skills, Cursor, Cline, Notion AI, LangChain 1.0 — converges on:
1. Classify the intent (before the LLM call)
2. Select the prompt template / skill
3. Assemble context (system instruction + relevant tools + relevant memory)
4. Call the model once

Nobody does mid-conversation system prompt mutation. Everyone assembles fresh per turn.

**Three Routing Tiers:**

| Tier | Mechanism | Latency | Example |
|---|---|---|---|
| Keyword/explicit | Regex, command match | ~0ms | "/focus email", "draft a reply" |
| Embedding-based | Cosine similarity on pre-embedded routes | ~1ms | [Aurelio semantic-router](https://github.com/aurelio-labs/semantic-router) (3.4k stars) |
| LLM-based | Model picks from skill descriptions | ~free (already in call) | Skill manifest in system_instruction |

**Semantic Router Details** (Aurelio Labs):
- Define routes with 5-10 example utterances each
- Pre-compute embeddings at startup
- Classify incoming messages via kNN cosine similarity
- Supports OpenAI, Cohere, HuggingFace, FastEmbed encoders
- "Dynamic routes" can trigger function calls, not just classify
- Sub-millisecond classification. Some implementations report sub-1ms.

---

## 4. Production Implementations

**Anthropic Agent Skills** (Dec 2025, [blog](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)):
- Adopted by OpenAI, Google, GitHub, Cursor within weeks
- Three-layer progressive disclosure:
  1. **Metadata** (~1-2 lines per skill): always in context, just enough to know when relevant
  2. **Instructions** (full SKILL.md): loaded on-demand when skill activates
  3. **Resources**: additional files, loaded only if instructions reference them
- Context usage proportional to active skill complexity, not total library size
- Filesystem-based: skills are directories containing SKILL.md + resources

**Anthropic Context Engineering** ([blog](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)):
- Just-in-time data loading: store lightweight identifiers, fetch only when needed
- Memory tool + context editing improved agent search by **39%**, reduced tokens by **84%**
- Treat system instructions as "job description", user inputs as "inbox"

**Cursor:**
- 6 different LLMs with specific roles (main agent, 2 code-edit, 1 suggestion, 1 indexing, 1 "master" that determines context)
- Different chat modes (chat, agent, cmd-k) have **different static system prompts**
- Cursor 2.0 runs up to 8 agents simultaneously via Git worktrees

**Cline:**
- Plan mode (read-only) vs Act mode (modify). Different models per mode.
- System prompt assembled dynamically based on active mode
- Tool availability changes with mode

**Notion AI:**
- Replaced task-specific prompt chains with central reasoning model + modular sub-agents
- Model routing based on task type: writing specs → high-reasoning; auto-fill → fine-tuned cheap model (50% latency cut)
- One-click skills = pre-configured prompt templates

**LangChain 1.0:**
- `@dynamic_prompt` middleware: receives agent state, returns system prompt string per-call
- `wrap_model_call`: lower-level hook to modify tools, prompt, messages before each call
- Dynamic tool addition/removal still an open issue (github #33808)

**OpenPersona:**
- Four-layer model: Soul (identity), Body (runtime), Faculty (capabilities), Skill (professional packs)
- "Pantheon" switching: install multiple personas, switch instantly
- Context transfers between personas (conversation summary, pending tasks, emotional state)

---

## 5. What NOT To Do (Research-Backed)

- Don't use a separate LLM call for routing — too expensive, too slow for personal assistant
- Don't put all skillset instructions in system_instruction with "only follow relevant ones" — behaviors bleed across
- Don't compress core identity below ~150 tokens — model needs enough to anchor personality
- Don't load all tools and say "use what's relevant" — unused definitions are noise
- Don't repeat constraints every message in multi-turn (Gemini-specific)
- Don't use overly broad negative constraints like "do not infer" — Gemini over-indexes and fails basic reasoning
- Don't change system_instruction mid-conversation without a clear mode switch signal

---

## Sources

- [Chroma: Context Rot](https://research.trychroma.com/context-rot)
- [Lost in the Middle (Stanford/MIT)](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/)
- [Lost in the Middle at Birth (2026)](https://arxiv.org/abs/2603.10123)
- [Anthropic: Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic: Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Writing Effective Tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Aurelio semantic-router](https://github.com/aurelio-labs/semantic-router)
- [vLLM Semantic Router](https://blog.vllm.ai/2026/01/05/vllm-sr-iris.html)
- [Google: Gemini 3 Prompting Guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gemini-3-prompting-guide)
- [Google: System Instructions](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/system-instructions)
- [Google: Function Calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google: Context Caching](https://ai.google.dev/gemini-api/docs/caching)
- [MLOps: Prompt Bloat](https://mlops.community/the-impact-of-prompt-bloat-on-llm-output-quality/)
- [LangChain Agent Middleware](https://blog.langchain.com/agent-middleware/)
- [Cursor Architecture](https://blog.sshh.io/p/how-cursor-ai-ide-works)
- [Cline Plan & Act](https://docs.cline.bot/core-workflows/plan-and-act)
- [Notion AI Case Study](https://openai.com/index/notion/)
- [OpenPersona](https://github.com/acnlabs/OpenPersona)
- [Microsoft LLMLingua](https://github.com/microsoft/LLMLingua)
- [CompactPrompt (2025)](https://arxiv.org/html/2510.18043v1)
