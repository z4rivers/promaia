# Phase 10: MuninnDB Cognitive-First Implementation Plan

**Created:** 2026-03-07
**Source:** Gemini Deep Research (corrected brief -- MuninnDB as primary cognitive engine, not background coprocessor)
**Status:** Draft -- review and refine before execution

## Core Principle

MuninnDB is the cognitive engine. Postgres is the durable store and fallback. When MuninnDB is healthy, ACTIVATE is the PRIMARY retrieval path. When MuninnDB is down, the system should feel noticeably dumber, because it IS dumber without decay, Hebbian learning, and associative recall.

---

## 1. Cognitive-First Architecture

The architecture inverts the traditional RAG stack. Instead of stateless vector search, the system interacts with a living memory graph.

### Component Interaction Flow
1. **User Input** -> **Cognitive Gateway** (new middleware)
2. **Cognitive Gateway** checks MuninnDB health
   - *If Healthy:* Calls `ACTIVATE(context)` -> Returns ranked, decayed, associated engrams
   - *If Down:* Sets `cognitive_status="degraded"`, calls pgvector fallback, injects "Brain Offline" system prompt
3. **Agent Execution:** LLM receives context
   - **Profile Injection:** Via `ACTIVATE("user profile constraints")`
   - **Session Context:** Via `ACTIVATE("previous session summary")`
4. **Action/Response:** Agent generates output
5. **Dual-Write Commitment:**
   - **Postgres:** `INSERT INTO memories (...)` (Durability) -- blocks, must succeed
   - **MuninnDB:** `POST /engrams` (Cognition/Learning) -- parallel write

---

## 2. ACTIVATE as Primary Retrieval

ACTIVATE is not just search -- it updates the state of the database (reinforcing retrieved memories via Hebbian learning) on every call.

### Python Client Pattern (Async HTTPX)
```python
async def cognitive_activate(context_query: str, limit: int = 10):
    """PRIMARY retrieval path. Returns cognitively ranked memories and triggers Hebbian learning."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MUNINN_BASE}/api/activate",
                json={"vault": VAULT, "context": [context_query], "max_results": limit, "threshold": 0.1},
                timeout=2.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return {"status": "healthy", "activations": data.get("activations", []), "brief": data.get("brief", [])}
    except Exception as e:
        logging.error(f"MUNINNDB FAILURE: {e}")
        return {"status": "degraded", "activations": [], "error": str(e)}

async def fetch_memory(query: str):
    """Orchestrator: ACTIVATE first, pgvector fallback only if degraded."""
    result = await cognitive_activate(query)
    if result["status"] == "healthy":
        return format_engrams(result["activations"])
    else:
        notify_degradation()
        return await fallback_pgvector_search(query)
```

The pgvector fallback returns results based ONLY on cosine similarity -- no recency, no frequency, no associations. The user feels the loss.

---

## 3. Hebbian Learning Maximization Strategy

"Neurons that fire together, wire together." Hebbian links only form when multiple engrams are returned in the SAME ACTIVATE call.

### Strategy A: Context Stuffing
Send narrative queries that bridge concepts, not keyword searches.
- **Bad:** `ACTIVATE("project deadlines")` then `ACTIVATE("email draft")`
- **Good:** `ACTIVATE("drafting email regarding project deadlines and deployment schedule")`
- Result: MuninnDB retrieves "deadlines" and "deployment" engrams simultaneously, strengthening their Hebbian link

### Strategy B: The Associative Chain
Pass results of previous steps into context of next steps:
1. `results = ACTIVATE("Initial user request")`
2. `ACTIVATE("Refinement based on " + results.content)`
- Effect: Links initial request concepts to refinement concepts in Hebbian graph

### Strategy C: Context Accumulator Pattern
```python
async def run_agent_cycle(user_input, session_history):
    # Combine immediate input with session gist to maximize co-activation
    hebbian_context = f"{user_input}\nRELATED: {session_history[-1].summary}"
    memories = await cognitive_activate(hebbian_context)
    # Engine now increases weights between current topic, session context, and retrieved memories
```

---

## 4. Memory Tier Mapping (MuninnDB-Driven)

MEM-02 tiers are views on MuninnDB's dynamic scoring -- NOT separate Postgres labels.

| Tier | MuninnDB Condition | Meaning |
|------|-------------------|---------|
| **Core** | `confidence > 0.9` AND tagged "core" | Fundamental facts, high-trust |
| **Active** | `relevance > 0.8` | Recently accessed or heavily reinforced |
| **Warm** | `0.4 < relevance <= 0.8` | Accessible via association but fading |
| **Cold** | `0.1 < relevance <= 0.4` | Fading, requires strong cue to recall |
| **Archive** | `relevance <= 0.1` | Near decay floor, effectively forgotten unless exact match |

These tiers are computed properties of the cognitive engine, not stored status fields.

---

## 5. Session Continuity Protocol (MEM-05)

### Session End
- Generate session summary
- Write to MuninnDB: `POST /engrams {content: summary, tags: ["session_summary", "2026-03-07"]}`
- Summary enters the graph, connected to everything discussed

### Session Start (Next Day)
- Retrieve last summary: `ACTIVATE("last session summary", limit=1)`
- Warm-up call: Take summary content, run `ACTIVATE(summary_content)`
- Effect: Re-activates all memories discussed yesterday, resets their decay curves
- The brain "remembers" context through Hebbian reinforcement, not log replay

---

## 6. Dynamic Profile via ACTIVATE (MEM-04)

Instead of a static 200-token system prompt, query MuninnDB for the most RELEVANT profile traits:

```python
async def get_dynamic_profile():
    profile_engrams = await cognitive_activate(
        "user identity preferences communication style constraints work patterns",
        limit=5,
    )
    if not profile_engrams["activations"]:
        return STATIC_FALLBACK_PROFILE
    profile_text = "\n".join([e["content"] for e in profile_engrams["activations"]])
    return f"CURRENT USER CONTEXT (Cognitively Active):\n{profile_text}"
```

The profile adapts: if the user has been doing HVAC work all week, HVAC preferences score higher than coding preferences due to recency/Hebbian activation.

---

## 7. Embedding Provider Selection

### Selected: Ollama (Local) with nomic-embed-text

**Rationale:**
- Zero external API dependency -- no more deprecation surprises
- Free, low-latency, runs on localhost
- nomic-embed-text provides excellent semantic clustering that feeds the Hebbian engine
- MuninnDB's cognitive scoring (decay, Hebbian, Bayesian) does the heavy lifting on top of embeddings

### Configuration
```bash
set MUNINN_OLLAMA_URL=http://localhost:11434
set MUNINN_EMBEDDING_MODEL=nomic-embed-text
```

**Alternative:** If Ollama is too heavy on the machine, use `MUNINN_GOOGLE_KEY` pointed at a current Gemini embedding model (not the deprecated text-embedding-004). Verify which model MuninnDB selects.

---

## 8. Degradation Communication Strategy

When MuninnDB goes down, the system tells the user:

1. **System Alert:** Warning icon on dashboard -- "Cognitive Engine Offline. Using static database fallback. Learning disabled."
2. **Chat Injection:** First agent message prefixed: `[COGNITIVE ENGINE OFFLINE -- running in basic recall mode]`
3. **Dashboard Health:** Widget turns red with explanation
4. **Recovery:** When MuninnDB comes back, run ACTIVATE on recent session summaries to re-warm the cognitive cache

---

## 9. Agent Integration (How Each Agent Uses ACTIVATE)

### Pre-Run Hook (Context Loading)
```python
# Before sending to LLM
relevant_memories = await cognitive_activate(user_message)
prompt = f"""
COGNITIVE CONTEXT (ranked by relevance, association, and recency):
{format_for_llm(relevant_memories)}

USER QUERY:
{user_message}
"""
```

### Search/Recall Tools
When agent calls search_memory: route to ACTIVATE, not pgvector. Return the "Why" scoring breakdown so the LLM understands why it remembered something.

### Post-Run Hook (Learning)
```python
# After LLM generates response -- close the learning loop
new_memory = f"User asked: {query}. Context: {summary_of_response}"
await muninn_write(content=new_memory, concept="interaction_log", tags=["session"])
```

---

## 10. Seeding for Maximum Early Association

### Step 1: Import
Loop through 56 Postgres memories, POST each to MuninnDB individually (batch endpoint has vault bug in v0.3.6).

### Step 2: Hebbian Bootstrap
After seeding, don't leave memories as isolated nodes. Run targeted ACTIVATE queries that co-activate related memories:

```python
# Group memories by domain/topic, then co-activate
groups = {
    "identity": ["user work context", "user communication preferences", "user values"],
    "promaia": ["promaia architecture", "brain MCP tools", "agent scheduler"],
    "projects": ["heatpup HVAC tool", "maybe cat answer engine", "hope cookie"],
}
for group_name, concepts in groups.items():
    combined = " ".join(concepts)
    await cognitive_activate(combined)  # Forces co-activation, builds initial Hebbian links
```

The brain starts pre-wired with meaningful associations instead of 56 disconnected nodes.

---

## 11. Dashboard Cognitive Metrics

- **Health Status:** Green/Red from `/api/health`
- **Association Graph:** Visualize engram nodes and Hebbian weight edges
- **Decay Distribution:** Histogram of memories across relevance tiers (Core/Active/Warm/Cold/Archive)
- **"Why" Inspector:** Debug box -- type a query, see raw ACTIVATE response with hebbian_boost, recency_score, semantic_similarity, bm25_score breakdown
- **Hebbian Density:** Count of non-zero Hebbian links vs total possible -- measures how "wired" the brain is

---

## 12. Implementation Order

1. **Infrastructure Prep**
   - Verify MuninnDB v0.3.6 running on ports 8475/8476
   - Install Ollama, pull nomic-embed-text
   - Configure MuninnDB embedding env vars, restart, verify index_size > 0
   - Set up NSSM Windows service for auto-start

2. **Client Development**
   - Formalize muninn.py with ACTIVATE-first retrieval and degradation logic
   - Add health monitoring (5-minute cycle, alert to Telegram when down)

3. **Seeding & Bootstrapping**
   - Migrate 56 Postgres memories to MuninnDB
   - Run Hebbian bootstrap script to pre-wire associations

4. **Integration Phase 1 (Retrieval)**
   - Replace primary retrieval in MCP search/recall tools with ACTIVATE
   - Add visible degradation indicator to dashboard and agent messages

5. **Integration Phase 2 (Context & Profile)**
   - Dynamic profile loading via ACTIVATE (MEM-04)
   - Session continuity: save summary -> warm-up ACTIVATE on session start (MEM-05)

6. **Integration Phase 3 (Learning)**
   - Agent post-run writes interaction summaries back to MuninnDB
   - Verify Hebbian weights building from real usage (hebbian_boost > 0)

7. **Dashboard**
   - Connect cognitive metrics widgets to MuninnDB stats/health endpoints
   - Decay tier visualization, association graph, "Why" inspector

---

## Windows Service Setup (NSSM)

```powershell
# Install NSSM, then:
nssm install MuninnDB "C:\Users\Zachary Turner\AppData\Local\muninn\muninn.exe" "start"
nssm set MuninnDB AppDirectory "C:\Users\Zachary Turner\AppData\Local\muninn"
nssm set MuninnDB Description "Cognitive Memory Layer for zBrain"
nssm set MuninnDB Start SERVICE_AUTO_START
nssm set MuninnDB AppEnvironmentExtra "MUNINN_OLLAMA_URL=http://localhost:11434" "MUNINN_EMBEDDING_MODEL=nomic-embed-text"
nssm set MuninnDB AppStdout "C:\Users\Zachary Turner\.muninn\data\service.log"
nssm set MuninnDB AppStderr "C:\Users\Zachary Turner\.muninn\data\service.err"
Start-Service MuninnDB
```

---

## Open Questions for Implementation

1. Does MuninnDB v0.3.6 actually support MUNINN_OLLAMA_URL? Verify from startup log or docs.
2. What exact embedding model does MUNINN_GOOGLE_KEY select? May be a viable alternative to Ollama.
3. Is there a v0.3.7+ release that fixes the embedding deprecation? (Release tracker research pending)
4. How does `muninn start` interact with NSSM -- does the binary daemonize itself, or does NSSM need to manage the foreground process?
5. Optimal ACTIVATE threshold for 56-1000 memories (0.1 may be too aggressive, 0.3 may filter too much)

---

*Source: Gemini Deep Research, corrected 2026-03-07*
*Posture: MuninnDB is the cognitive engine, Postgres is the filing cabinet behind it*
