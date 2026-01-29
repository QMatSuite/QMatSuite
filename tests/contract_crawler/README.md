# Contract Crawler

Tools for enumerating, testing, and tracking coverage of daemon RPC methods.

## Components

### Introspection
- `introspection.py`: Enumerates all RPC methods from daemon handler registry
- `test_introspection.py`: Tests for method enumeration

### Auto-Crawler
- `payloads.py`: Minimal payload generators for stateless methods
- `crawler.py`: Core crawler logic for calling methods and validating JSON serialization
- `test_auto_crawl.py`: Tests for auto-crawling

### Recipes
- `recipes/`: Recipe-based tests for complex methods requiring setup
- `test_recipes.py`: Tests for recipe execution

### Golden Comparison
- `golden_comparison.py`: Utilities for comparing current responses to golden fixtures
- `test_golden_contracts.py`: Tests comparing current responses to baseline (0873ebf)

### Coverage Tools

#### Coverage Report
- `report_coverage.py`: Generates machine-readable coverage matrix report
- `test_coverage_report.py`: Validates report structure

**Usage:**
```bash
python tests/contract_crawler/report_coverage.py
# Output: tests/contract_crawler/coverage_report.json
```

#### Discovery Runner
- `discover_methods.py`: Best-effort attempt to call all RPC methods and bucket failures
- `test_coverage.py`: Coverage enforcement tests

**Usage:**
```bash
python tests/contract_crawler/discover_methods.py
# Output: tests/contract_crawler/discovery_report.json
```

**Failure Buckets:**
- `no_payload`: Payload generator returned None (method needs recipe or payload definition)
- `missing_fields`: Validation error about required fields (payload incomplete)
- `needs_resources`: Needs project/calc/step resources (should use recipe)
- `error`: Generic error (needs investigation)

#### GUI Scanner
- `gui/tests/e2e/tools/scan_gui_rpc_methods.py`: Static scanner for GUI-used RPC methods
- `test_gui_scanner.py`: Validates scanner output

**Usage:**
```bash
python gui/tests/e2e/tools/scan_gui_rpc_methods.py
# Output: gui/tests/e2e/tools/gui_rpc_methods.txt
#         gui/tests/e2e/tools/gui_rpc_methods.json
```

### GUI Coverage Gate
- `test_gui_methods_covered.py`: Soft gate ensuring GUI-used methods are covered

**Usage:**
```bash
# Soft mode (xfail, shows missing methods)
pytest tests/contract_crawler/test_gui_methods_covered.py::test_gui_methods_covered_soft

# Enforced mode (fails if missing)
QV_ENFORCE_GUI_RPC_COVERAGE=1 pytest tests/contract_crawler/test_gui_methods_covered.py::test_gui_methods_covered
```

## Workflow

1. **Generate coverage report** to see current state:
   ```bash
   python tests/contract_crawler/report_coverage.py
   ```

2. **Run discovery** to find methods that can be auto-crawled:
   ```bash
   python tests/contract_crawler/discover_methods.py
   ```

3. **Scan GUI** to identify GUI-used methods:
   ```bash
   python gui/tests/e2e/tools/scan_gui_rpc_methods.py
   ```

4. **Check GUI coverage** (soft gate):
   ```bash
   pytest tests/contract_crawler/test_gui_methods_covered.py::test_gui_methods_covered_soft
   ```

5. **Expand coverage** by:
   - Adding minimal payloads to `payloads.py` (for auto-crawler)
   - Creating recipes in `recipes/` (for complex methods)
   - Adding exemptions to `EXEMPT_METHODS` in `test_coverage.py` (with reasons)

