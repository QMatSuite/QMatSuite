# Legacy Pattern Audit & Gate

## Rules (Non-Negotiable)

1. **Class/Dataclass Fields (FORBIDDEN)**:
   - `step_id:` → must be `step_ulid:`
   - `calc_id:` → must be `calc_ulid:`
   - `run_id:` → must be `run_ulid:`
   - `calculation_id:` → must be `calculation_ulid:`
   - `structure_id:` → must be `structure_ulid:` (EXCEPT in CalculationModel which uses structure_id as a foreign key)
   - `step_type:` (bare) → must be `step_type_spec:` or `step_type_gen:`
   - `id:` → must be `ulid:`

2. **Attribute Access (FORBIDDEN)**:
   - `.step_id` on objects → must be `.step_ulid`
   - `.run_id` on result objects → must be `.run_ulid`
   - `.calculation_id` on objects → must be `.calculation_ulid`

3. **Function Parameters (ALLOWED)**:
   - `step_id: str` as function parameter is OK (local variable scope)
   - `step_type: str` as function parameter is OK
   - `calc_id: str` as function parameter is OK
   - `run_id: str` as function parameter is OK

4. **Dict Keys (NO BACKWARD COMPAT)**:
   - All dict keys should use canonical names
   - Remove `"step_id": step.step_ulid` backward compat mappings

5. **Ignored**:
   - `_vault/` directory (legacy code)
   - Documentation/comments
   - DTO compat properties (like `calc_id` returning `calc_ulid`)

---

## Discovered Issues

### Class/Dataclass Fields to Fix:

1. **`calculation/results.py` - CalculationResult**
   - Line 31: `calculation_id: str` → `calculation_ulid: str`
   - Line 38: `run_id: Optional[str]` → `run_ulid: Optional[str]`

2. **`calculation/results.py` - to_dict() backward compat**
   - Line 50: `"step_id": step.step_ulid` → REMOVE (backward compat)
   - Lines 51-52: Duplicate `step_type_spec` keys → FIX

3. **`history/pins.py` - PinResult** ✅ PARTIALLY FIXED
   - Already fixed field names
   - Need to update usages

4. **`history/events.py` - Event Classes**
   - Various `run_id:` fields need to become `run_ulid:`

### Attribute Accesses to Fix:

1. **`analysis/dos.py:114`**: `step.step_id` → `step.step_ulid`
2. **`analysis/bands.py:172`**: `step.step_id` → `step.step_ulid`
3. **`analysis/energy.py:93`**: `step.step_id` → `step.step_ulid`
4. **`calculation/runner.py:803,818`**: `summary.step_id` → `summary.step_ulid`
5. **`calculation/results.py:69-70`**: `self.run_id` → `self.run_ulid`
6. **`history/storage.py:434,461`**: `event.step_id` → `event.step_ulid`

---

## Fix Order

1. Fix dataclass field definitions first
2. Then fix attribute accesses (will automatically need updating after #1)
3. Then fix constructor calls
4. Run full pytest
