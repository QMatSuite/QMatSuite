# Vault: Legacy Code Reference

This directory contains legacy QVService implementations preserved for reference only.

## Purpose

- **Historical reference** during migration
- **Documentation** of legacy patterns
- **Emergency debugging** if needed

## Rules

1. **DO NOT IMPORT** from `quantumvitas._vault` in production code
2. **DO NOT USE** vault code in new features
3. **DO NOT MODIFY** vault code (it's frozen reference)

## Contents

- `_legacy_service.py`: Full legacy QVService (215 methods) - renamed from `_api_legacy.py`
- `_legacy_facade.py`: Partial legacy facade (101 methods) - renamed from `api_legacy.py`

## Migration Path

All code should migrate to use `quantumvitas.api.QVService` (canonical API).

See `docs/API_SINGLE_SOURCE_MIGRATION_PLAN.md` for migration strategy.

