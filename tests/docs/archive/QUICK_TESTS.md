# Quick Tests

Quick tests are fast, focused tests that run automatically in CI.

## Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests
└── core/              # Test framework core
```

## Running

```bash
# Run all quick tests
pytest tests/ -m quick

# Run with coverage
pytest tests/ --cov=src/qmatsuite --cov-report=html

# Run specific category
pytest tests/unit/
pytest tests/integration/
```

## CI Integration

Quick tests run automatically in GitHub Actions:
- ✅ On push to main/develop
- ✅ On pull requests
- ✅ Daily schedule

See `.github/calculations/tests.yml`.

## Requirements

- Fast execution (< 5 minutes total)
- No external dependencies (or marked with `@pytest.mark.requires_qe`)
- Focused on core functionality

