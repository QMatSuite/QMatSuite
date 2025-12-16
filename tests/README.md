# Tests Overview (local)

This directory contains the quick tests (unit and integration tests).

For full documentation of the test layout and markers, see:

- `docs/testing_guide.md` – quick start guide
- `docs/tests_overview.md` – detailed test map
- `extended-tests/README.md` – documentation for the extended QE test suite

## Running Integration Tests

### OPTIMADE Live Tests

Real network integration tests for the OPTIMADE pipeline. These tests perform actual HTTP requests against Materials Cloud OPTIMADE endpoints and will fail in CI if the endpoint/format changes.

```bash
# Run all OPTIMADE live tests
pytest -m integration -k optimade_live -s

# Run specific test
pytest tests/integration/test_optimade_live.py::test_optimade_live_search_si -s
pytest tests/integration/test_optimade_live.py::test_optimade_live_fetch_si_structure_and_parse_pymatgen -s
pytest tests/integration/test_optimade_live.py::test_optimade_live_viewer_payload_builder -s
```

**Note:** These tests require network access and will fail if:
- Materials Cloud OPTIMADE endpoints are down
- Endpoint URLs or response formats change
- Network connectivity is unavailable

The tests are marked with `@pytest.mark.integration` and are intended to run in CI to provide early warning if the OPTIMADE route breaks.
