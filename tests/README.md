# QuantumVITAS Tests

This directory contains tests for QuantumVITAS, including unit tests and integration tests for QE input parsing and generation.

## Structure

- `unit/` - Unit tests for individual components
- `integration/` - Integration tests for workflows
- `examples/` - Example QE input/output files from the [Quantum ESPRESSO Tutorial 2019](https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects)

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r requirements.txt
```

Or install pytest separately:

```bash
pip install pytest pytest-cov
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_qe_input.py -v

# Specific test
pytest tests/unit/test_qe_input.py::TestQEInputParser::test_parse_simple_scf -v
```

### Run with Coverage

```bash
pytest tests/ --cov=src/quantumvitas --cov-report=html
```

## Test Examples

The tests use real QE input files from the tutorial repository. These are automatically downloaded when you clone the repository.

### Example: Testing Bidirectional Conversion

```python
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator

# Parse a QE input file
qe_input = QEInputParser.parse_file("tests/examples/qe_tutorial_examples/0_Si_scf/si.scf.in")

# Modify parameters
control = qe_input.get_namelist('control')
control.set('prefix', 'modified_si')

# Generate new input file
QEInputGenerator.write_file(qe_input, "modified.in")
```

## Test Coverage

Current test coverage includes:

- ✅ QE input file parsing (namelists, cards, comments)
- ✅ QE input file generation
- ✅ Bidirectional conversion (parse -> generate -> parse)
- ✅ Real-world examples from QE tutorial
- ✅ QE engine integration
- ✅ Workflow scenarios (SCF -> NSCF conversion)

## Adding New Tests

When adding new features, please add corresponding tests:

1. Unit tests for individual functions/classes
2. Integration tests for workflows
3. Tests using real example files when possible

Follow the existing test structure and naming conventions.

