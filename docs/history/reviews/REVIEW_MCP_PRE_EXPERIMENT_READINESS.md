# MCP Pre-Experiment Readiness Review

**Date**: 2026-03-06
**Reviewer**: Claude Opus 4.6
**Scope**: Preamble, tool descriptions, context_hints, insight recording workflow
**Evidence base**: GPT trace (403 calls, task 4 AHC), Chain A (24 sessions, 19 relax + 5 bands), 3 audit documents

---

## 1. Preamble Assessment

### 1.1 Length and Structure

The preamble (`_MCP_INSTRUCTIONS` in `src/qmatsuite/mcp/app.py`) is **54 lines, ~320 words**. This is **good** — concise enough that an agent will actually read it, well under the 500-word threshold where attention starts dropping.

**Structure is clear**: two named modes (CALCULATION vs SYNTHESIS), a grade taxonomy, a WHEN TO RECORD section, and a closing instruction to search before calculating.

**Issues**:
1. The Fast/Normal track distinction in CALCULATION MODE is compressed into a dense 4-line + 3-line block. An agent encountering QMatSuite for the first time would need to parse two chains of arrow-separated tool names on first read. This is adequate but not optimal.

2. The Normal track chain shows:
   ```
   search_knowledge → create_calculation → ... → run_calculation → get_results_summary → record_insight(grade='finding')
   ```
   This is correct and includes `record_insight` at the end. **But the Fast track also includes `record_insight`**, which is good.

3. **Missing from the chain**: `record_intent` is never mentioned in either track. The tool exists but the preamble doesn't tell agents when to use it.

### 1.2 Demo/Configure Verbosity

The preamble mentions demos in exactly one line within the Fast track chain: `search_demos → (optional get_demo_results) → load_demo`. This is **proportional** — not over-explained.

The Normal track's configure workflow (`create_calculation → (optional auto_resolve_species_map or set_species_map) → (optional apply_preset) → (optional set_parameters)`) is listed inline with appropriate `(optional)` markers. This is **adequate** — verbose enough to be clear, not so verbose it drowns the knowledge workflow.

**Verdict**: Demo/configure verbosity is fine. No changes needed.

### 1.3 Knowledge Workflow Clarity

**KNOWLEDGE SYNTHESIS MODE** section:

```
list_insights(grade='finding') → identify trends →
  record_insight(grade='pattern', references=[...finding IDs])
list_insights(grade='pattern') → identify unifying mechanisms →
  record_insight(grade='principle', references=[...pattern IDs])
Use get_results_summary(calc_ulid=...) to drill into raw data
when needed (source_calculation field links findings to calculations).
```

**Strengths**:
- Clear escalation ladder: finding → pattern → principle
- Tells agents to use `list_insights` (not browse files)
- Mentions `source_calculation` linking

**Weaknesses**:
1. **No mention of `mode` parameter**: The tool has `mode='pending'` (default) vs `mode='recent'`, but the preamble doesn't explain when to use which. An agent might call `list_insights(grade='finding')` and get 0 results because all findings are `under_review` (contradiction bug), then conclude there's nothing to synthesize.

2. **"WHEN TO RECORD vs REPORT" is too conservative**: The current text says:
   > "A pattern based on 3 data points is likely premature"

   This actively discourages recording patterns. In Chain A, agents had 19 data points but never recorded a single pattern. The conservatism isn't the primary cause (task focus and timing were), but it provides a rationalisation for inaction.

3. **No mention of engineering/methodology insights**: The preamble frames everything as scientific findings ("verified result from one calculation"). There's no guidance that says "record methodology lessons, error recovery procedures, or parameter recommendations — not just numerical results."

### 1.4 Missing Guidance

**Critical gaps for AHC (QE→W90→postw90) workflow**:

| Needed Guidance | Present? | Impact |
|-----------------|----------|--------|
| What to do when a calculation fails | Partial — error enrichment exists, but preamble doesn't say "record failures as insights" | HIGH — GPT agent failed 3x on k-points, never recorded |
| Record methodology/engineering lessons | NO | HIGH — Chain A only recorded lattice constants, never methodology |
| Multiple insights per session are expected | NO | MEDIUM — Chain A averaged exactly 1 finding/session |
| Search knowledge BEFORE starting work | YES (last 2 lines) | LOW — present but easy to miss |
| Multi-step workflows need extra care | NO | HIGH — AHC requires explicit k-point handoff between QE/W90 |
| record_intent should be used before complex actions | NO | MEDIUM — tool exists, preamble never mentions it |

**The preamble's closing lines**:
```
Before starting new calculations:
- Search the knowledge base for relevant prior findings
- Check if similar compounds or workflows have been studied before
```

This is present but buried at the very end with no emphasis. It's a checklist item an agent might skip. More importantly, it says to search — but doesn't say what to DO with the results.

---

## 2. Tool Description Assessment

### 2.1 record_insight

**Tool docstring** (from `record_insight.py:45-66`):

```python
"""Record an agent-authored insight into the QMatSuite knowledge base.

All grades are recorded in the provenance journal. Findings, patterns, and
principles are additionally promoted into the searchable knowledge database.

Args:
    content: Distilled conclusion (short, enters knowledge base if promoted).
    grade: Quality tier — bookkeeping, observation, finding, pattern, or principle.
    reasoning: Detailed thought process (provenance only, not indexed).
    ...
"""
```

**Assessment**:

| Question | Answer | Problem? |
|----------|--------|----------|
| Multiple calls per session OK? | Not stated | YES — agents may self-limit to 1 |
| Engineering/methodology insights? | Not stated — only "distilled conclusion" | YES — implies scientific only |
| Failed calculations worth recording? | Not stated | YES — failures are invisible to future sessions |
| Include specific numbers? | Not stated | MEDIUM — vague findings are useless |
| Default grade is `observation` | Yes (parameter default) | MINOR — preamble says `finding`, creating confusion |

**context_hint after recording** (from `record_insight.py:243-258`):

For findings/patterns/principles (promoted):
```
"Insight recorded in knowledge base. Use search_knowledge() to verify it's findable."
```

For observations:
```
"Observation recorded in journal. Record more observations, then consolidate into a
finding with record_insight(grade='finding'). After several findings, synthesize a
pattern with record_insight(grade='pattern', references=[...])."
```

**Problem**: Neither hint says "consider recording additional insights from this session." The promoted hint just says "verify it's findable" — this is a dead-end prompt that doesn't encourage recording more. An agent naturally interprets this as "you're done with insight recording."

### 2.2 get_results_summary

**context_hint** (from `get_results_summary.py:95-107`):

For relax workflows:
```
"Results ready. Use promote_structure(calc_ulid='...') to extract the relaxed
geometry for use in subsequent calculations. Then record key numerical findings
(lattice constants, errors vs experiment) with record_insight(grade='finding')
for cross-compound comparison."
```

For other workflows:
```
"Results ready. Record key numerical findings (band gaps, k-point locations,
direct/indirect) with record_insight(grade='finding') for cross-compound
comparison in future sessions."
```

**Assessment**: This is **good** — it explicitly mentions `record_insight` and even specifies what to record (lattice constants, band gaps, etc.). The GPT agent received this exact hint and ignored it. This suggests the hint is necessary but insufficient — it's advice that competes with the agent's primary task directive.

**Missing**:
- No mention of recording methodology/engineering findings
- No mention of recording failures
- Doesn't say "record multiple insights if relevant" — implies a single finding

### 2.3 run_calculation

**context_hint on success** (from `run_calculation.py:123-131`):
```
"Use get_results_summary(calc_ulid='...') to see results."
```
Plus for relax: promote_structure suggestion.

**context_hint on failure** (from `error_enrichment.py:52-54`):
```
"Use set_parameters(calc_ulid='...', params=...) to apply a fix, then
run_calculation(calc_ulid='...') to retry."
```

**Critical gap**: On failure, the hint says "fix and retry." It **never** says "record this failure as an insight." This is the primary mechanism by which engineering knowledge gets lost. The GPT agent hit k-point mismatch 3 times. Each time it saw "fix and retry" — no prompt to record what happened.

On success, the hint points to `get_results_summary` but **does not mention `record_insight` directly**. The agent must follow the chain: `run_calculation` → `get_results_summary` → (hint mentions record_insight). If the agent skips `get_results_summary` (which the GPT agent often did), the record_insight prompt never arrives.

### 2.4 search_knowledge / list_insights

**search_knowledge description** (from `search_knowledge.py:22-39`):
```python
"""Search the QMatSuite knowledge base for DFT best practices and error recovery.

Uses BM25 full-text search over curated insights covering convergence,
smearing, error recovery, workflow guidance, and method-specific tips.
Searches both builtin and agent-recorded (local) knowledge.
"""
```

**Assessment**: Clear, well-written. Mentions error recovery explicitly. But nothing in the description says "you should call this at session start" — that guidance is only in the preamble's last two lines.

**context_hint** (from `search_knowledge.py:80-86`):
```
"Found N insight(s). Use these insights to inform your parameter choices
with set_parameters or apply_preset."
```

**Problem**: This hint says to use insights for parameter choices — a narrow framing. It doesn't say "use these to avoid known pitfalls" or "check if any findings contradict your approach."

**list_insights description** (from `list_insights.py:18-30`):
```python
"""List insights by grade for review or synthesis.

Default mode 'pending': shows findings not yet synthesized into a
higher-grade insight. Use when responding to a synthesis nudge.

Mode 'recent': shows most recent entries regardless of synthesis
status. Use to review the bigger picture or revisit older knowledge.
"""
```

**Assessment**: The `mode` parameter is well documented here. The phrase "Use when responding to a synthesis nudge" is good — it connects to the nudge mechanism. But:
1. The nudge was 100% ignored in Chain A
2. The `compound` parameter is documented but its behavior (matches tags) may not be obvious
3. No mention that `under_review` findings are included (they are, per `list_by_grade` SQL: `status IN ('active', 'under_review')`)

### 2.5 Other Tools

**create_calculation**: context_hint mentions `apply_preset`/`set_parameters`/`inspect_calculation`/`run_calculation` but NOT `search_knowledge`. An agent creating a calculation is never prompted to check prior knowledge first.

**quick_run**: context_hint on success says only `"Use get_results_summary(...) to see results."` — no mention of `record_insight`. Since `quick_run` combines create+run, agents who use it bypass the `create_calculation` → `search_knowledge` opportunity entirely.

**record_intent**: description is minimal but adequate. The real problem is that nothing in the system prompts agents to use it.

**inspect_calculation**: No knowledge-related hints. Reasonable — this is a configuration review tool.

---

## 3. Insight Recording Behavior

### 3.1 AHC Scenario Simulation

Putting myself in the position of a fresh Claude agent completing QE→W90→postw90 for AHC:

**What I encountered**:
1. K-point mismatch between NSCF and Wannier (pipeline failure)
2. Fixed by using explicit K_POINTS crystal lists
3. Got AHC = 701 S/cm vs literature 751 S/cm

**What I would record, given current preamble + tool descriptions**:

**Typical agent behavior** (not ideal): I would record exactly **1 finding**:
```
record_insight(
    content="BCC Fe AHC = 701 S/cm at 12x12x12 k-grid, ~6.6% below literature value of 751 S/cm",
    grade="finding",
    scope_engine="qe", scope_workflow="*", scope_system_type="metal", scope_method="dft",
    tags="Fe, AHC, wannier90, bcc",
    source_calculation="<calc_ulid>"
)
```

**What I would NOT record** (but should):
- K-point mismatch lesson: "QE NSCF k-points must be explicit crystal list for Wannier90 workflows; automatic grid causes pw2wannier90 failure"
- Fermi level lesson: "Re-extract Fermi energy from denser NSCF run; do not reuse SCF Fermi level"
- Pipeline configuration: "AHC workflow requires: SCF → NSCF(explicit k) → W90 → postw90 with berry_task=ahc"

**Why only 1**: The preamble shows `→ record_insight(grade='finding')` (singular). The `get_results_summary` hint says "record key numerical findings" (plural of findings content, but implies one `record_insight` call). After one `record_insight`, the context_hint says "Insight recorded in knowledge base. Use search_knowledge() to verify." — this is a termination signal. Nothing says "now record additional insights."

**Grade choice**: Everything would be `finding`. Nothing in the system encourages using `observation` for preliminary notes or `pattern` without multiple prior findings. The preamble says `pattern` needs evidence across a "chemical family or structural class" — a single AHC calculation doesn't qualify.

### 3.2 Multi-Insight Capability

**Code review**: `record_insight` can be called unlimited times per session. There is:
- No throttling
- No rate limiting
- No deduplication
- No per-session cap

The store's `add()` method checks for contradictions (same scope, different content) but doesn't prevent recording. Each call is independent.

**Conclusion**: The technical system supports multiple insights per session. The behavioral default of 1-per-session comes entirely from preamble framing and context_hint design — not from code limitations.

### 3.3 Failure Recording Gap

When a calculation fails, the agent sees the error enrichment response:

```python
# error_enrichment.py:52-54
hint = (
    f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, "
    f"then run_calculation(calc_ulid='{calc_ulid}') to retry."
)
```

**There is ZERO prompt to record the failure as an insight.** The entire error enrichment flow is:
1. Classify error → diagnostics + suggested_fixes
2. Return error with fix instructions
3. Agent applies fix and retries

At no point does the system say: "Before retrying, consider recording this failure and its resolution with `record_insight(grade='finding')` so future sessions can avoid this error."

This is the single most impactful gap in the system. The GPT agent hit k-point mismatch 3 times. If the first failure had been recorded, the second and third occurrences would have been avoidable via `search_knowledge`.

### 3.4 Chain A Evidence

**From CHAIN_LOG.md** (24 sessions analyzed):

| Metric | Value |
|--------|-------|
| Total sessions | 24 (19 relax + 5 bands) |
| Average `record_insight` calls per session | 3.8 (relax), 5.2 (bands) |
| Net new findings per session | **Exactly 1** |
| `list_insights` tool calls across ALL sessions | **0** |
| Patterns recorded | **0** |
| Principles recorded | **0** |

**Key insight**: Despite averaging ~4 `record_insight` calls per session, only 1 net finding was added. The extra calls were `grade='observation'` or `grade='bookkeeping'` — non-promoted entries that went to the journal only. The preamble's escalation ladder (observation → finding → pattern) was followed literally: agents made observations, consolidated into exactly one finding, and stopped.

**From AUDIT_NUDGE_RESPONSE.md**:
- Nudge appeared in 100% of eligible sessions (16/16)
- Nudge engagement: **0%**
- Nudge fired at 93-96% session completion — after the agent had already decided to wrap up
- Agents informally recognized cross-compound patterns in their text output but never formalized them as `record_insight(grade='pattern')`

**Collateral bug**: The contradiction mechanism marked 80%+ of findings as `under_review`. All findings shared identical scope fields (`scope_engine=qe, scope_workflow=relax, scope_system_type=semiconductor, scope_method=dft`). With `_CONTRADICTION_THRESHOLD=3`, only the 3 most recent findings stayed `active`. A meta-session calling `list_insights(grade='finding')` would see only 3 of 20+ findings.

---

## 4. Workflow Gaps

### 4.1 Record After Failure

**Current state**: Nothing prompts recording after failure. The error enrichment hint says "fix and retry" only.

**What would prompt a Claude agent to record the failure?**
Currently: Nothing. The agent would see the error, apply the suggested fix, retry, and move on. If it eventually succeeds, it records the numerical result but not the journey.

**What's missing**: A single line in the error enrichment context_hint:
```
"Before retrying, record this error and its resolution with
record_insight(grade='finding') so future sessions can avoid this issue."
```

**Concrete fix**: In `error_enrichment.py:52-54`, modify the hint:
```python
hint = (
    f"Before retrying: consider recording this error pattern with "
    f"record_insight(grade='finding', content='<error description and fix>', "
    f"scope_engine='{engine}', tags='error_recovery') "
    f"so future sessions can avoid it. "
    f"Then use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, "
    f"and run_calculation(calc_ulid='{calc_ulid}') to retry."
)
```

### 4.2 Search Before Calculate

**Current state**: The preamble's last 2 lines mention searching. But:
- `create_calculation` context_hint does NOT mention `search_knowledge`
- `quick_run` bypasses the opportunity entirely
- No tool in the calculate chain prompts the agent to check knowledge first

**What would ensure an agent searches at session start?**

Option A (preamble): Move the "search before calculating" instruction to the TOP of the CALCULATION MODE section, not the bottom. Make it step 1 of the Normal track:
```
Normal track:
  search_knowledge → create_calculation → ...
```
This is already present! But agents skip it because:
1. It's mixed into a dense chain
2. No tool response reinforces it
3. The task prompt ("calculate X for Y") creates urgency that overrides advisory text

Option B (tool-level): Add `search_knowledge` to `create_calculation`'s context_hint:
```
"Before configuring: use search_knowledge(engine='...', workflow='...')
to check for relevant best practices and known issues."
```

Option C (automatic): Have `create_calculation` itself call `search_knowledge` internally and include relevant knowledge in its response. This is more invasive but would guarantee knowledge is surfaced.

**Recommendation**: Implement Option B (low-risk text change) and consider Option C for complex workflows (AHC, phonons, GW).

### 4.3 Multiple Insights Per Session

**What encourages only 1 insight?**

1. **Preamble chain**: `→ record_insight(grade='finding')` — singular, at end of chain. Reads as "record THE insight."
2. **context_hint after recording**: `"Insight recorded in knowledge base. Use search_knowledge() to verify."` — termination signal. Should instead say "Record additional insights if this session produced other findings."
3. **get_results_summary hint**: `"Record key numerical findings..."` — says "findings" (plural content) but implies a single `record_insight` call.
4. **Task focus**: Agent's task is "calculate X" → producing insights is incidental to the primary deliverable.

**What would encourage multiple?**

1. Change the record_insight context_hint from:
   ```
   "Insight recorded in knowledge base. Use search_knowledge() to verify."
   ```
   to:
   ```
   "Insight recorded. If this session produced additional findings (methodology lessons,
   error workarounds, parameter guidance), record each as a separate insight."
   ```

2. Change `get_results_summary` hint to explicitly request multiple:
   ```
   "Record numerical results, methodology lessons, and any error recovery procedures
   as separate insights with record_insight(grade='finding')."
   ```

3. Add to the preamble: "Record multiple insights per session when warranted — numerical results, methodology lessons, and error recovery procedures should each be separate findings."

### 4.4 Engineering vs Scientific Insights

**Current state**: The system does not distinguish between scientific findings ("GaAs lattice constant = 5.743 A") and engineering findings ("Wannier90 requires explicit K_POINTS crystal from NSCF; automatic grids cause pw2wannier90 failure").

The `tags` field could be used to mark engineering insights (e.g., `tags='error_recovery,k_points,wannier90'`), but no guidance exists on how to tag them.

**Chain A evidence**: All 25 findings were scientific (lattice constants). The one engineering insight (Pulay stress) came from a meta-session, not from the session where the failure occurred.

**Should the system distinguish them?** Yes, but minimally. The `grade` system is already complex (5 levels). Adding a `category` dimension (scientific vs engineering) would add confusion.

**Better approach**: Use examples in the preamble and tool descriptions:
```
Record both:
- Scientific findings: "GaAs PBE lattice constant = 5.743 A (+1.59% vs experiment)"
- Engineering lessons: "Wannier90 workflows require explicit K_POINTS crystal list from NSCF;
  automatic grids cause pw2wannier90 k-point mismatch failure"
```

Tag-based differentiation (`tags='error_recovery'` vs `tags='lattice_constant'`) is sufficient for search without adding schema complexity.

---

## 5. Prioritized Recommendations

### Must-Fix Before Experiments

| # | What | Where | Why | Size |
|---|------|-------|-----|------|
| M1 | **Add "record failure" prompt to error enrichment hint** | `error_enrichment.py:52-54` | Without this, the AHC experiment (Group 2) will repeat the GPT trace failure: 3x k-point mismatch, 0 insights recorded. The entire A/B comparison depends on knowledge accumulation from errors. | S |
| M2 | **Change record_insight context_hint to encourage additional insights** | `record_insight.py:244` | Without this, Group 3 (38-session chain) will reproduce Chain A's 1-finding-per-session pattern. Meta-sessions will have only numerical findings to synthesize — no methodology patterns. | S |
| M3 | **Add "record both scientific and engineering insights" guidance to preamble** | `app.py:_MCP_INSTRUCTIONS` | Without this, Group 2 agents won't record k-point lessons, Fermi level lessons, or pipeline configuration. The "with knowledge" arm will have only numerical findings, not methodological knowledge. | S |
| M4 | **Fix contradiction scope granularity** | `knowledge/store.py` (contradiction detection) | Currently all semiconductor/QE/relax findings share identical scope, triggering false contradictions. With `_CONTRADICTION_THRESHOLD=3`, a meta-session sees only 3 of N findings. Group 3 will have 19+ relax findings — 16+ will be invisible. | M |
| M5 | **Add "multiple insights expected" to preamble** | `app.py:_MCP_INSTRUCTIONS` | Chain A evidence: agents self-limit to 1 finding without explicit encouragement. A complex AHC session warrants 3-5 insights. | S |

### Should-Fix

| # | What | Where | Why | Size |
|---|------|-------|-----|------|
| S1 | **Add search_knowledge to create_calculation context_hint** | `create_calculation.py:113-127` | Reinforces the "search before calculate" workflow at tool level, not just preamble. | S |
| S2 | **Add record_insight mention to run_calculation success hint** | `run_calculation.py:123-131` | Currently only `get_results_summary` mentions recording. Agents who skip that tool never see the prompt. | S |
| S3 | **Add quick_run success hint for record_insight** | `quick_run.py:216-225` | Same gap as S2 but for the combined quick_run path. | S |
| S4 | **Add lattice constants to get_results_summary for relax workflows** | `get_results_summary.py:_build_summary` | Group 3 meta-sessions calling `get_results_summary` for relax findings won't see lattice parameters — the primary measurement they need to synthesize. | M |
| S5 | **Surface `status` field in list_insights response** | `list_insights.py` | If contradiction bug (M4) isn't fully fixed, agents need to see which findings are `under_review` vs `active`. | S |
| S6 | **Mention record_intent in preamble** | `app.py:_MCP_INSTRUCTIONS` | Tool exists but is invisible. For Group 2 (AHC), intent recording before complex multi-step workflows would improve provenance. | S |

### Nice-to-Have

| # | What | Where | Why | Size |
|---|------|-------|-----|------|
| N1 | **Add examples to record_insight description** | `record_insight.py` docstring | Show scientific vs engineering insight examples with good tags. Helps agents understand expected content quality. | S |
| N2 | **Add compound-level scope to contradiction detection** | `knowledge/store.py` | Prevents cross-compound false contradictions. Long-term fix for M4. | M |
| N3 | **Structured error classes for common workflow failures** | `error_enrichment.py` | AHC-specific error classification (k-point mismatch, Fermi level stale, etc.) with targeted record_insight prompts. | L |
| N4 | **Auto-insert search_knowledge into create_calculation** | `create_calculation.py` | Guarantee knowledge is surfaced at calculation creation time. More invasive than S1 but more reliable. | M |

---

## 6. Overall Readiness Assessment

### Group 1: Broad Matrix (simple DFT across compounds)

**Verdict: CONDITIONAL GO**

The basic workflow (create → set_parameters → run → get_results_summary → record_insight) works. `get_results_summary` already prompts for `record_insight`. The main risk is the contradiction bug (M4) — if running 20+ compounds with similar scope, most findings will be marked `under_review` and invisible to later analysis.

**Minimum required**: Fix M4 (contradiction scope) or M5+M2 (encourage recording despite the bug).

### Group 2: A/B Controlled (AHC with/without knowledge)

**Verdict: NO-GO without M1, M2, M3, M5**

This experiment's entire hypothesis is that prior knowledge improves outcomes. But:
- **M1**: Without failure recording prompts, the "with knowledge" arm won't accumulate the engineering knowledge that would actually help (k-point mismatch lessons, Fermi level handling). It'll only have numerical results.
- **M3**: Without engineering insight guidance, agents will record "AHC = 701 S/cm" but not "use explicit K_POINTS crystal for Wannier workflows."
- **M2 + M5**: Without multi-insight encouragement, the "with knowledge" arm's knowledge base will be thin — 1 finding per session instead of 3-5.

The A/B comparison would be testing: "Does knowing that AHC = X S/cm help you calculate AHC?" Answer: obviously not. The valuable knowledge is methodological, and the current system doesn't capture it.

### Group 3: Long Chain + Meta-Session (38 sessions)

**Verdict: CONDITIONAL GO (with M2, M4, M5)**

The chain will run and produce findings. But:
- M4: Meta-sessions will see only 3 of 38 findings due to contradiction scope bug
- M2 + M5: Without these fixes, each session produces exactly 1 numerical finding, giving the meta-session a thin dataset for pattern synthesis
- Without M3, all findings will be scientific — the meta-session won't find methodology patterns because none were recorded

### Group 4: Active Proposal (agent proposes experiments)

**Verdict: CONDITIONAL GO (depends on Group 3 quality)**

This experiment reads accumulated knowledge and proposes next steps. Its quality depends entirely on the richness of the Group 3 knowledge base. If Group 3 produces only numerical findings with thin scope, the proposals will be simplistic ("calculate more compounds" rather than "investigate convergence with k-grid density" or "test SOC effects on AHC accuracy").

---

## Appendix A: Verbatim Key Texts

### Preamble (complete)

```
You are a computational materials science research assistant
that operates in two modes:

CALCULATION MODE — when asked to compute properties:
  init_project (if needed) → choose track
  Fast track (if a relevant demo exists for the target system/property/workflow):
    search_demos → (optional get_demo_results) → load_demo → run_calculation → get_results_summary → record_insight(grade='finding')
  Normal track:
    search_knowledge → create_calculation → (optional auto_resolve_species_map or set_species_map) → (optional apply_preset) → (optional set_parameters) → run_calculation → get_results_summary → record_insight(grade='finding')

KNOWLEDGE SYNTHESIS MODE — when asked to review or summarize:
  list_insights(grade='finding') → identify trends →
    record_insight(grade='pattern', references=[...finding IDs])
  list_insights(grade='pattern') → identify unifying mechanisms →
    record_insight(grade='principle', references=[...pattern IDs])
  Use get_results_summary(calc_ulid=...) to drill into raw data
  when needed (source_calculation field links findings to calculations).

KNOWLEDGE GRADES:
  finding   → verified result from one calculation
  pattern   → recurring trend across multiple findings
              (requires references to supporting finding IDs)
  principle → general rule distilled from multiple patterns
              (requires references to supporting pattern IDs)

WHEN TO RECORD vs REPORT:
  Always give the user an honest summary of what you observe,
  including tentative signals and caveats.
  Record a pattern or principle to the knowledge base when the
  evidence is broad enough that it would be useful to a future
  session working on a related compound. A pattern based on
  3 data points is likely premature; a pattern consistent across
  a chemical family or structural class is worth recording.
  Recording is not a permanent commitment — future sessions can
  vote entries up or down as new evidence emerges.

Before starting new calculations:
- Search the knowledge base for relevant prior findings
- Check if similar compounds or workflows have been studied before
```

### run_calculation failure context_hint

```python
hint = (
    f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, "
    f"then run_calculation(calc_ulid='{calc_ulid}') to retry."
)
```

### record_insight post-recording context_hint

```python
# For promoted (finding/pattern/principle):
hint = "Insight recorded in knowledge base. Use search_knowledge() to verify it's findable."

# For observations:
hint = (
    "Observation recorded in journal. "
    "Record more observations, then consolidate into a finding with "
    "record_insight(grade='finding'). After several findings, synthesize "
    "a pattern with record_insight(grade='pattern', references=[...])."
)
```

### get_results_summary context_hint (non-relax)

```python
hint = (
    "Results ready. Record key numerical findings (band gaps, k-point locations, "
    "direct/indirect) with record_insight(grade='finding') "
    "for cross-compound comparison in future sessions."
)
```

### error_enrichment context_hint (on failure)

```python
hint = (
    f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, "
    f"then run_calculation(calc_ulid='{calc_ulid}') to retry."
)
```

## Appendix B: Evidence Cross-Reference

| Claim | Source | Location |
|-------|--------|----------|
| GPT agent: 403 tool calls, 0 record_insight | GPT trace JSONL | `/Users/hh7465/gpt_agent_test/task_4_final_conversation_trace_detailed.jsonl` |
| GPT agent: 11 run_calculation, 3 k-point failures | GPT postmortem | `/Users/hh7465/gpt_agent_test/task_4_trace_postmortem_report.md` |
| GPT agent saw context_hint mentioning record_insight, ignored it | GPT trace line 652 | Trace JSONL |
| Chain A: 1 finding per session, 0 list_insights calls | Chain A audit | `.tmp/task3_chain_a/AUDIT_NUDGE_RESPONSE.md` |
| Chain A: nudge 100% ignored, fired at 93-96% session completion | Nudge audit | `.tmp/task3_chain_a/AUDIT_NUDGE_RESPONSE.md` |
| Chain A: 80%+ findings under_review due to contradiction scope | Traceability audit | `.tmp/task3_chain_a/AUDIT_TRACEABILITY_CHAIN.md` |
| Chain A: agents recognized patterns informally but never recorded them | Nudge audit, sessions 09/11/16/18 | `.tmp/task3_chain_a/AUDIT_NUDGE_RESPONSE.md` |

---

**Summary**: The MCP system's core mechanics are sound — the tools work, the knowledge store functions, the preamble is well-structured. The gaps are all in **behavioral nudging**: the system doesn't push agents hard enough to (a) record failures, (b) record multiple insights, (c) record engineering/methodology insights, or (d) search knowledge proactively. These are all text changes (S-sized), not architectural changes. Five must-fix items (M1-M5) would cost approximately 30 minutes of implementation time and would make the difference between experiments that produce thin, purely numerical knowledge and experiments that capture the rich methodological insights needed for a compelling paper.
