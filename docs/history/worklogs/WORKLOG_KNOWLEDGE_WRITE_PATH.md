# Knowledge Write Path Implementation Worklog

## Overview
Implement the agent-authored knowledge write path: `record_insight`, `record_intent`, trust-weighted search, and contradiction detection.

## Baseline
- Test count: 6625 passed, 5 skipped
- Branch: v2-python

## Steps

### Step 0: Worklog + baseline
- [x] Created worklog
- [x] Baseline test count recorded: 6625 passed, 5 skipped

### Step 1: KnowledgeStore.add() + multi-DB + trust weights
- [x] Trust weight mapping (TRUST_WEIGHTS dict)
- [x] _local_db_path() helper
- [x] Multi-DB constructor (local_db_path param, lazy local_conn)
- [x] add() method with grade gating (finding/principle promoted, others journal-only)
- [x] Contradiction detection (scope-based, bilateral non-wildcard rule)
- [x] Multi-DB search (builtin + local merge, results from both DBs)
- [x] Trust-weighted ranking formula: confidence_weight * bm25_rank * trust_weight
- [x] Under-review annotation ([UNDER REVIEW] prefix) for high contradiction_count

### Step 2: record_insight MCP tool
- [x] Input validation (grade, content)
- [x] Journal write for ALL grades (doc_type="unknown")
- [x] Knowledge DB write for grade >= finding
- [x] Contradiction warnings in response
- [x] Context hints (promoted vs observation vs failure)

### Step 3: record_intent MCP tool
- [x] Input validation
- [x] Journal-only write
- [x] Return envelope with intent_id

### Step 4: Wiring + shared store
- [x] get_knowledge_store() singleton in knowledge/__init__.py
- [x] reset_knowledge_store() for testing
- [x] Update search_knowledge to use shared store
- [x] Register record_insight + record_intent in server.py
- [x] Update error_enrichment to use shared store
- [x] Fix test_stage4.py, test_stage5.py fixtures (patch knowledge_mod._store)
- [x] Update tool count assertions: 38 → 40 in test_stage11, test_stage_p1, test_stage_p2
- [x] Add record_insight, record_intent to expected_names in test_stage11

### Step 5: Comprehensive tests
- [x] TestKnowledgeStoreAdd (8 tests)
- [x] TestMultiDBSearch (4 tests)
- [x] TestTrustWeights (3 tests)
- [x] TestContradictionDetection (5 tests)
- [x] TestRecordInsightTool (6 tests)
- [x] TestRecordIntentTool (4 tests)
- [x] Total: 30 new tests, all passing

### Step 6: Final verification
- [x] Full test suite: 6655 passed, 5 skipped, 0 failures
- [x] Delta: +30 tests from baseline (6625 → 6655)
- [x] Worklog finalized

## Files Created
| File | Description |
|------|-------------|
| `src/qmatsuite/mcp/tools/record_insight.py` | MCP tool: record agent insights (journal + knowledge DB) |
| `src/qmatsuite/mcp/tools/record_intent.py` | MCP tool: record agent intent (journal only) |
| `tests/mcp/test_knowledge_write.py` | 30 comprehensive tests for write path |
| `docs/history/worklogs/WORKLOG_KNOWLEDGE_WRITE_PATH.md` | This worklog |

## Files Modified
| File | Change |
|------|--------|
| `src/qmatsuite/mcp/knowledge/store.py` | add(), multi-DB, trust weights, contradiction detection |
| `src/qmatsuite/mcp/knowledge/__init__.py` | get_knowledge_store() shared singleton |
| `src/qmatsuite/mcp/tools/search_knowledge.py` | Use shared store, add contradiction_count to results |
| `src/qmatsuite/mcp/server.py` | Register record_insight + record_intent |
| `src/qmatsuite/mcp/error_enrichment.py` | Use shared store via get_knowledge_store() |
| `tests/mcp/test_stage4.py` | Fix fixture to patch knowledge_mod._store |
| `tests/mcp/test_stage5.py` | Fix fixture to patch knowledge_mod._store |
| `tests/mcp/test_stage11.py` | Tool count 38→40, add new tools to expected set |
| `tests/mcp/test_stage_p1.py` | Tool count 38→40 |
| `tests/mcp/test_stage_p2.py` | Tool count 38→40 |

## Key Design Decisions
1. **Multi-DB via two connections**: builtin.db (read-only) + local.db (writes). No ATTACH DATABASE.
2. **local.db created lazily on first write**: No empty file creation for read-only users.
3. **Bilateral non-wildcard contradiction rule**: Both sides must be non-wildcard to match.
4. **Journal entries for ALL grades**: Even bookkeeping/observation get provenance.
5. **doc_type="unknown"**: Verified acceptable at journal.py:34.
6. **Trust weights as simple multipliers**: score = confidence_weight * bm25_relevance * trust_weight.
7. **Shared store via knowledge/__init__.py**: Single source for search_knowledge + error_enrichment.
