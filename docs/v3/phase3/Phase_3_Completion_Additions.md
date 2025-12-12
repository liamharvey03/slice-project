# Phase 3 Completion Guide - Additional Sections

This document contains the missing sections identified in Claude's review. These should be integrated into the main Phase 3 Completion Guide.

---

## Dependency Injection Wiring

All Phase 3 components are wired through `src/voyager/api/deps.py`:

**LLM Client**:
```python
def get_llm_client_instance() -> LLMClientProtocol:
    # Uses OpenAILLMClient wrapper around AsyncOpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4")
    return OpenAILLMClient(api_key=api_key, model=model)
```

**QueryTranslator**:
```python
def get_query_translator_instance() -> QueryTranslator:
    llm_client = get_llm_client_instance()  # Shared LLM client
    registry = get_series_registry_instance()
    return QueryTranslator(llm_client, registry)
```

**CritiqueEngine**:
```python
def get_critique_engine_instance() -> CritiqueEngine:
    llm_client = get_llm_client_instance()  # Same shared client
    return CritiqueEngine(llm_client)
```

**ValidationService**:
```python
def get_validation_service_instance() -> ValidationService:
    return ValidationService(
        query_translator=get_query_translator_instance(),
        quant_service=get_quant_service_instance(),
        validation_repo=LogicValidationRepository(engine),
        thesis_repo=get_data_access_instance().thesis_repo
    )
```

**CritiqueService**:
```python
def get_critique_service_instance() -> CritiqueService:
    engine = get_engine()
    return CritiqueService(
        critique_engine=get_critique_engine_instance(),
        thesis_repo=get_data_access_instance().thesis_repo,
        snapshot_repo=ThesisSnapshotRepository(engine),
        validation_repo=LogicValidationRepository(engine),
        backtest_repo=BacktestResultRepository(engine),
        engine=engine
    )
```

**Key Points**:
- No protected member access (`._llm_client`) - uses public `get_llm_client_instance()`
- Singleton pattern via module-level cache variables
- All dependencies injected through factory functions

---

## Async/Sync Coordination

**Pattern**: Synchronous `QuantService` methods called directly from async contexts.

```python
# In ValidationService._run_quant_query() (async method):
result = self._quant.relationship_strength(  # Sync call
    resolved.series_a,
    resolved.series_b,
    expected_direction=expected_direction
)
```

**Rationale**:
- `QuantService` queries are fast (<100ms) database operations
- No blocking I/O that would benefit from threading
- Simplifies error handling and code flow
- Alternative (`asyncio.to_thread()`) adds overhead without benefit

**LLM Calls**: Properly async with `await` and timeout handling:
```python
response = await asyncio.wait_for(
    self._llm.chat(messages),
    timeout=30.0
)
```

---

## Error Handling Strategy

**LLM Timeout** (30 second timeout on all calls):
- `ValidationService.validate()`: Returns `ValidationResult(status="parse_failed", error_message="...")`
- `CritiqueEngine.critique()`: Returns `CritiqueSummary(concerns=[], opening_message="I encountered a timeout...")`
- `CritiqueEngine.drill_down()`: Returns `CritiqueResponse(message="I encountered a timeout...", thesis_edit_suggestion=None)`

**JSON Parsing Failure**:
- All LLM responses wrapped in `extract_json()` + `json.loads()` with try-except
- Fallback to empty/error responses rather than crashes
- Logged as warnings for debugging

**Quant Query Failure**:
- Individual link failures don't abort validation
- Failed links returned with `interpretation="error: <message>"`
- Allows partial validation results

**Database Errors**:
- Propagated to caller (not caught)
- Assumption: database should be reliable, failures are exceptional

**Broad Exception Handling**:
- Used only for LLM layer (unpredictable network/API errors)
- Marked with `# pylint: disable=broad-exception-caught`
- All exceptions logged with `exc_info=True` for debugging

---

## Test Mocking Approach

**LLM Client Mocking**:
```python
@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns JSON responses"""
    client = AsyncMock()
    # Set return value per test:
    client.chat.return_value = {
        "content": '{"links": [...]}',
        "usage": {...}
    }
    return client
```

**Registry Mocking**:
```python
@pytest.fixture
def mock_registry():
    """Mock SeriesRegistry"""
    registry = MagicMock(spec=SeriesRegistry)
    # Configure search_by_concept() return value per test
    registry.search_by_concept.return_value = [
        SeriesEntry(id="DFII10", name="10Y Real Yield", source="FRED")
    ]
    return registry
```

**QuantService Mocking**:
```python
@pytest.fixture
def mock_quant():
    """Mock QuantService"""
    quant = MagicMock(spec=QuantService)
    # Configure correlation() and relationship_strength() per test
    return quant
```

**Repository Mocking**:
- Use `MagicMock(spec=<RepoClass>)` to ensure method signatures match
- Configure `insert()`, `get_by_id()`, etc. per test
- Verify calls with `.assert_called_once_with()`

**Integration Tests**:
- Use real repositories with test database
- Use real QuantService with test data
- Mock only LLM client (expensive, non-deterministic)

---

## Performance & Latency

**Expected Latency** (with OpenAI GPT-4):

| Operation | LLM Calls | Quant Queries | Expected Time |
|-----------|-----------|---------------|---------------|
| Validation (3 links) | 1 | 3 | ~2-4 seconds |
| Critique (initial) | 1 | 0 | ~2-3 seconds |
| Drill-down (1 message) | 1 | 0 | ~2-3 seconds |

**Bottlenecks**:
1. **LLM API calls**: 1-5 seconds per call (network + generation)
2. **Database queries**: <50ms (negligible)
3. **Quant calculations**: <100ms per query (negligible)

**Optimization Opportunities** (future):
- Cache LLM responses for identical thesis texts
- Batch multiple drill-down dimensions in single LLM call
- Use streaming for real-time critique updates
- Switch to faster models (GPT-3.5-turbo) for extraction

**Timeout Configuration**:
- All LLM calls: 30 second timeout
- Reasonable for GPT-4 with complex prompts
- Prevents indefinite hangs on API issues

---

## CLI Tool

**File**: `scripts/cli/llm_cli.py`

### Commands

**Extract Links**:
```bash
python scripts/cli/llm_cli.py extract <thesis_id>
# Outputs: Extracted causal links and ambiguities
```

**Validate Thesis**:
```bash
python scripts/cli/llm_cli.py validate <thesis_id>
# Outputs: Complete validation result with quant interpretations
```

**Generate Critique**:
```bash
python scripts/cli/llm_cli.py critique <thesis_id>
# Outputs: Critique summary with concerns across 6 dimensions
```

**Drill-Down**:
```bash
python scripts/cli/llm_cli.py drill-down <thesis_id> logical_coherence "Can you elaborate?"
# Outputs: LLM response to your message
```

### Usage

Requires:
- Thesis exists in database
- `OPENAI_API_KEY` environment variable set
- Database configured in `.env`

Example workflow:
```bash
# 1. Validate thesis logic
python scripts/cli/llm_cli.py validate thesis_123

# 2. Generate critique
python scripts/cli/llm_cli.py critique thesis_123

# 3. Explore specific concern
python scripts/cli/llm_cli.py drill-down thesis_123 empirical_grounding \
  "What would strengthen the empirical support?"
```

---

## Integration Tests

**File**: `tests/v3/test_integration.py`

Tests complete workflows with real components (except LLM):

**test_full_validation_flow**:
- Creates test thesis in database
- Runs validation with real QuantService
- Verifies LogicValidation record persisted
- Confirms thesis status updated to "VALIDATED"

**test_full_critique_flow**:
- Starts critique session
- Tests multi-turn drill-down
- Applies edit suggestions
- Completes session
- Verifies snapshots and conversation history in database

**Purpose**:
- Unit tests prove components work in isolation
- Integration tests prove they work together
- Catches wiring issues, database schema mismatches, etc.

---

## Updated Known Limitations

4. **Direct SQL in CritiqueService** (FIXED):
   - Previously: Raw SQL UPDATE statements in `apply_edit_suggestion()`
   - Now: Uses `ThesisRepository.update_hypothesis()`, `.update_list_field()`, `.update_expression()`
   - All thesis updates now go through repository layer

5. **Protected Access** (FIXED):
   - Previously: `CritiqueService` called `_row_to_thesis()` protected method
   - Now: Uses public `get_by_id()` method
   - All repository access uses public API

---

## Summary of Fixes Applied

| Issue | Status | Solution |
|-------|--------|----------|
| CLI Tool Missing | ✅ Fixed | Created `scripts/cli/llm_cli.py` |
| deps.py Wiring Undocumented | ✅ Fixed | Added wiring details section |
| Async/Sync Handling Undocumented | ✅ Fixed | Added coordination section |
| Integration Test Missing | ✅ Fixed | Created `tests/v3/test_integration.py` |
| Error Fallbacks Undocumented | ✅ Fixed | Added error handling strategy section |
| Direct SQL in CritiqueService | ✅ Fixed | Refactored to use repository methods |
| Protected Access | ✅ Verified | Confirmed all instances fixed |
| Performance Notes Missing | ✅ Fixed | Added performance characteristics section |
| Test Mocking Strategy Undocumented | ✅ Fixed | Added mocking approach section |
