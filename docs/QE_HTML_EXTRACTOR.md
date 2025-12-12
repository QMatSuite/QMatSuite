# QE HTML Parameter Extractor

## Overview

The QE HTML extractor (`tools/extract_qe_parameters_v*.py`) scrapes Quantum ESPRESSO HTML documentation files (`INPUT_*.html`) to extract structured parameter metadata for use in the QuantumVITAS GUI.

**Purpose**: Generate machine-readable JSON metadata from QE's human-readable HTML documentation.

**Inputs**: 
- QE HTML documentation files (e.g., `INPUT_PW.html`, `INPUT_PH.html`) stored locally in `temp/qe_docs/`
- One HTML file per QE module (pw, ph, cp, neb, etc.)

**Outputs**:
- `src/quantumvitas/data/qe_module_parameters.json` - Schema v3 JSON with parameter metadata and section hierarchy
- Legacy versions preserved as `qe_module_parameters.legacy.v*.json`

**Why ToC-driven ordering?**
- The Table of Contents (ToC) in QE HTML docs reflects the canonical order intended by QE developers
- Preserving this order ensures the GUI displays parameters in the same sequence users see in the official documentation
- No sorting is applied anywhere in the extraction pipeline

---

## V1 vs V2 Improvements

### V1 Limitations
- Assumed second row of parameter table was always "Default:" (incorrect for parameters like `celldm` where "See:" appears first)
- Enum extraction relied on regex heuristics that missed structured HTML (`<span class="flag">`)
- Description rendering used `get_text()` which produced excessive blank lines and lost structure
- Limited indexing support (only simple bounded patterns)

### V3 Improvements

**A) Better Default/Status/See Parsing**
- Reads left cell text (case-insensitive) to identify label rows: "Default:", "Status:", "See:"
- No longer assumes row position
- Fixes cases where "See:" appears before "Default:" (e.g., `celldm` parameter)

**B) Better Enum Extraction**
- **Priority 1**: Extract from `<span class="flag">` elements inside `<dl>/<dt>` blocks
- **Priority 2**: Fallback to `<dl><dt><tt>` structures
- **Priority 3**: Regex heuristics (quoted tokens for CHARACTER, integer lines for INTEGER)
- Preserves quotes in enum values (e.g., `'debug'`, `'high'`)

**C) Improved Indexing Support**
- Bounded with numeric bounds: `celldm(i), i=1,6`
- Bounded with symbolic end: `Hubbard_U(i), i=1,ntyp` (stores `end_symbol`)
- Grouped indexed bases: `e1(i), e2(i), e3(i), i=1,3` → expands to 3 separate parameters
- Fixed-index expansions: `if_pos(1), if_pos(2), if_pos(3)` → compresses to single base
- Multi-dimensional: `Hubbard_occ(ityp,i), (ityp,i) = (1,1) . . . (ntyp,3)` (stores `dims` array)
- Fallback: Any parameter with parentheses is preserved with `raw_spec` if parsing fails

**D) Better Description Rendering**
- Custom HTML-to-text renderer (`render_description()`)
- Handles `<pre>`: dedents, normalizes newlines, compresses blank lines (max 2 consecutive)
- Handles `<dl>`: renders as bullet lists with indented multi-line descriptions
- Handles `<br>`, inline tags (`<a>`, `<i>`, `<b>`, `<span>`)
- Preserves structure while removing excessive whitespace

**E) Schema Version 2**
- Adds optional `status` field (e.g., "REQUIRED", "OPTIONAL")
- Adds optional `see_also` field (list of related parameter names or string)
- Maintains backward compatibility with v1 structure

---

## V2 Pipeline (Step-by-Step)

### Stage 1: ToC-Driven Initialization

```python
# Pseudo-code
toc_params = extract_toc_parameters(html_content)
# Returns: {"&CONTROL": ["calculation", "title", ...], "K_POINTS": ["nks", ...], ...}

parameters = {}
for section_name, param_names in toc_params.items():
    for param_name in param_names:
        base_name = normalize_param_name(param_name)
        key = f"{section_name}.{base_name}"
        parameters[key] = {
            "namelist": section_name,
            "name": base_name,
            "type": None,  # Will be filled in Stage 2
            # ... other fields initialized to None
        }
```

**Key points**:
- ToC extraction preserves document order (left-to-right, top-to-bottom traversal)
- Section names include `&` prefix for namelists (e.g., `&CONTROL`), no prefix for cards (e.g., `K_POINTS`)
- Parameters are initialized with minimal metadata; full metadata extracted in Stage 2

### Stage 2: Parameter Metadata Extraction

```python
# Pseudo-code
all_elements = soup.find_all(["h2", "h3", "table"])

for i, element in enumerate(all_elements):
    if element.name == "table":
        # Find nearest previous h2/h3 matching "Namelist:" or "Card:"
        section_for_table = find_section_for_table(all_elements, i)
        if not section_for_table:
            continue  # Skip tables under "Description of items:" etc.
        
        # Extract metadata from parameter table
        meta_list = extract_parameter_metadata_from_table(element)
        # Returns: [{"name": "celldm", "type": "REAL", "indexing": {...}, ...}, ...]
        
        for meta in meta_list:
            key = f"{section_for_table}.{meta['name']}"
            if key in parameters:
                parameters[key].update(meta)  # Fill in metadata
            else:
                parameters[key] = meta  # New parameter not in ToC
```

**Key extraction functions**:

1. **`extract_parameter_metadata_from_table(table)`**:
   - Parses `<th>` for raw parameter name
   - Parses first `<td>` for type (INTEGER, REAL, CHARACTER, LOGICAL)
   - Scans rows for "Default:", "Status:", "See:" by reading left cell text
   - Extracts description from `<blockquote>` using `render_description()`
   - Extracts enums (prioritize `<span class="flag">`, fallback to heuristics)
   - Calls `parse_indexing_and_expand()` for indexing metadata

2. **`parse_indexing_and_expand(raw_name, description)`**:
   - Handles all indexing patterns (bounded, symbolic, grouped, multi-dimensional)
   - Returns list of `{"base_name": str, "indexing": dict|None}`
   - May return multiple entries for grouped patterns (e.g., `e1(i), e2(i), e3(i)`)

3. **`render_description(blockquote)`**:
   - Traverses direct children of blockquote
   - Renders `<pre>` with dedenting and blank line compression
   - Renders `<dl>` as bullet lists
   - Normalizes whitespace (max 2 consecutive blank lines)

### Stage 3: Order Preservation

```python
# Pseudo-code
ordered_parameters = {}

# First: all ToC params in order
for section_name, param_list in toc_params.items():
    for param_name in param_list:
        key = f"{section_name}.{normalize(param_name)}"
        if key in parameters:
            ordered_parameters[key] = parameters[key]

# Then: extras discovered in Stage 2 (append at end)
for key, param in parameters.items():
    if key not in ordered_parameters:
        ordered_parameters[key] = param
```

**Output**:
```python
json.dump({
    "schema_version": 3,
    "modules": {
        "pw": {
            "doc_url": "...",
            "parameters": ordered_parameters  # Preserves insertion order
        }
    }
}, file, sort_keys=False)  # CRITICAL: no sorting
```

---

## Known V2 Limitations (Before V3)

1. **Section-level descriptions not stored**
   - V2 only extracts parameter-level descriptions
   - Section-level context (e.g., "Input this namelist only if lfcp = .TRUE.") is lost

2. **Card options/syntax/items not captured as structured data**
   - Card options (e.g., `{ tpiba | automatic | gamma | ... }`) are not parsed
   - Card syntax tables are not extracted
   - Card item descriptions are not captured separately

3. **NEB supercards not represented as hierarchy**
   - NEB modules use `BEGIN_*` / `END_*` supercard containers
   - V2 treats these as flat sections, losing the hierarchical structure

4. **No optionality classification**
   - Cannot determine if a section is "optional", "required", or "conditional"
   - This information exists in section descriptions but is not extracted

---

## V3 Additions

V3 extends v2 with section-level metadata and hierarchical structure:

### New Features

1. **Section Tree (`module.sections`)**
   - Hierarchical representation of sections (supercard → children → ...)
   - Supports NEB supercard nesting (`BEGIN_*` / `END_*`)
   - Each section node includes: `kind`, `name`, `description`, `optionality`, `children`

2. **Section-Level Description**
   - Extracts description text immediately after section header
   - Rendered using same `render_description()` logic
   - Stored in `section.description`

3. **Optionality Classification**
   - Analyzes section description for keywords
   - Classifies as: `"optional"`, `"required"`, `"conditional"`, or `"none"`
   - Rules based on presence of "if", "optional", "required" keywords

4. **Card Structured Fields**
   - `card.options`: List of option strings from `{ ... }` braces
   - `card.default_option`: Default option value
   - `card.options_description`: Mapping of option → description text
   - `card.syntax`: Rendered syntax table
   - `card.items`: List of item parameter tables (from "Description of items:")

### Schema Changes

- `schema_version`: 3
- New top-level: `module.sections` (hierarchical tree)
- Section nodes include: `kind`, `name`, `description`, `optionality`, `optionality_source`, `children`
- Card sections may include: `options`, `default_option`, `options_description`, `syntax`, `items`
- `module.parameters` unchanged (still uses v2 logic)

### V3 Algorithm Overview

1. **Build section hierarchy**:
   - Traverse `<h2>` elements in document order
   - Classify section kind (namelist/card/supercard/line_of_input/other)
   - Use stack to track open supercards (`BEGIN_*` pushes, `END_*` pops)
   - Attach sections to current supercard parent (if any) or module root

2. **Extract section descriptions**:
   - Collect content after `<h2>` until first `<h3>` or parameter table
   - Render using `render_description()` (same as v2)
   - **Robustness**: Falls back to `content_td` if nested table is missing
   - **Improved stop detection**: Only stops at parameter tables with type tokens (INTEGER, REAL, CHARACTER, LOGICAL)

3. **Classify optionality**:
   - Analyze section description text using word-boundary regex to avoid false positives
   - Rules: `\bif\b` → conditional, `\boptional\b` (not required) → optional, etc.
   - **Robustness**: Uses word boundaries to avoid matching "diff", "interface", etc.
   - Snippet extraction: First tries line-by-line scan, then falls back to sentence split

4. **Extract card structured fields**:
   - Parse options from header braces or "Card's options:" row (case-insensitive, apostrophe-tolerant)
   - Extract default from "Default:" row
   - Parse `<dl>` blocks for options_description
   - Extract syntax from `<h3>Syntax:</h3>` block (with `<pre>` fallback)
   - Extract items from `<h3>Description of items:</h3>` block (searches forward until next h3)
   - **Robustness**: Uses same nested content root as section description extraction for consistency

5. **Preserve v2 parameter extraction**:
   - `module.parameters` still uses v2's ToC-driven + metadata fill logic
   - No changes to parameter extraction behavior

---

## V3 Pipeline (Detailed)

### Stage 1: Section Hierarchy Building

```python
# Pseudo-code
sections_tree = []
supercard_stack = []  # Stack of open supercards

for h2 in soup.find_all("h2"):
    kind, name = classify_section_kind_and_name(h2)
    
    # Handle END_* (pop matching BEGIN_*)
    if kind == "supercard" and name.startswith("END_"):
        # Pop from stack (match by suffix)
        end_suffix = name[4:]  # "END_X" -> "X"
        for i in range(len(supercard_stack) - 1, -1, -1):
            if supercard_stack[i]["name"][6:] == end_suffix:  # "BEGIN_X" -> "X"
                supercard_stack = supercard_stack[:i]
                break
        continue
    
    # Extract description and optionality
    description = extract_section_description(h2, soup)
    optionality_info = classify_optionality(description)
    
    # Build section node
    section_node = {
        "kind": kind,
        "name": name,
        "description": description,
        "optionality": optionality_info["optionality"],
        "optionality_source": optionality_info["optionality_source"],
        "children": [],
    }
    
    # Extract card fields if card
    if kind == "card":
        card_fields = extract_card_structured_fields(h2, soup)
        section_node.update(card_fields)
    
    # Attach to parent
    if supercard_stack:
        supercard_stack[-1]["children"].append(section_node)
    else:
        sections_tree.append(section_node)
    
    # Push BEGIN_* onto stack
    if kind == "supercard" and name.startswith("BEGIN_"):
        supercard_stack.append(section_node)
```

**Key points**:
- Sections are attached to current top supercard (if any) or module root
- Supercard stack maintains nesting depth
- END_* elements are not added as nodes (they just close supercards)
- All sections processed in document order (no sorting)

### Stage 2: Section Description Extraction

The `extract_section_description()` function:
1. Finds the `<td>` in the row after the h2's `<tr>`
2. Locates nested table inside that `<td>` (falls back to `content_td` if missing)
3. Collects content elements (`<p>`, `<blockquote>`, `<pre>`, `<dl>`, `<div>`) from nested `<td>`
4. Stops at first `<h3>` or parameter-definition table
5. Renders collected elements using same logic as v2's `render_description()`

**Robustness improvements**:
- **Missing nested table**: Falls back to `content_td` or first `<td>` within it if nested table is missing
- **Improved stop detection**: Only stops at parameter tables where `<td>` contains "type" or type tokens (INTEGER, REAL, CHARACTER, LOGICAL)
- **Metadata table whitelist**: Expanded to include "see also:" and handles missing apostrophes

**HTML structure**:
```
<table>
  <tr><th><h2>Namelist: &NAME</h2></th></tr>
  <tr><td>
    <table>
      <tr><td>
        <p><b>Description text</b></p>  <!-- Collected -->
        <a name="param">...</a><table>...</table>  <!-- Stop here -->
      </td></tr>
    </table>
  </td></tr>
</table>
```

### Stage 3: Optionality Classification

The `classify_optionality()` function applies strict rules (case-insensitive, word-boundary matching):

1. If description contains word "if" (`\bif\b`) → `"conditional"`
2. Else if contains word "optional" (`\boptional\b`) and NOT "required" → `"optional"`
3. Else if contains word "required" (`\brequired\b`) and NOT "optional" → `"required"`
4. Else if contains BOTH "required" and "optional" → `"conditional"`
5. Else → `"none"`

**Robustness improvements**:
- **Word-boundary regex**: Uses `\bif\b`, `\boptional\b`, `\brequired\b` to avoid false positives (e.g., "diff", "interface")
- **Snippet extraction**: First tries line-by-line scan, then falls back to sentence split
- **Whitespace normalization**: Collapses excessive whitespace in snippets

Also extracts `optionality_raw_snippet` (line or sentence containing the keyword) for reference.

### Stage 4: Card Structured Fields Extraction

The `extract_card_structured_fields()` function:

1. **Options**: Parses from header `{ opt1 | opt2 | ... }` or "Card's options:" table row (case-insensitive, apostrophe-tolerant)
2. **Default option**: Extracts from "Default:" row in card section
3. **Options description**: Parses `<dl>` blocks, maps option key (from `<dt>`, often `<span class="flag">`) to description (from `<dd>`)
4. **Syntax**: Finds `<h3>Syntax:</h3>`, extracts `<div class="syntax"><table>`, renders as tab-separated lines. **Fallback**: If table not found, extracts `<pre>` text
5. **Items**: Finds `<h3>Description of items:</h3>`, searches forward until next `<h3>`, extracts parameter-definition tables (with type token detection), stores as `card.items[]` (NOT merged into `module.parameters`)

**Robustness improvements**:
- **Consistent traversal**: Uses same nested content root logic as `extract_section_description()` for consistency
- **Case-insensitive matching**: "Card's options:" matching is case-insensitive and apostrophe-tolerant
- **Syntax fallback**: Extracts `<pre>` if syntax table is missing
- **Items extraction**: Searches forward until next `<h3>` instead of only checking immediate blockquote sibling

### Stage 5: V3 Parameter Extraction (Preserved)

- All v3 logic intact: ToC-driven init, metadata fill, extras appended
- `module.parameters` structure unchanged
- No sorting applied

---

## V3 Robustness Improvements (Final Pass)

After the initial v3 implementation, a final robustness pass addressed several edge cases and false positives. These improvements maintain schema version 3 and do not change the JSON structure.

### 1) Optionality False-Positive Reduction

**Problem**: Substring matching (`"if" in desc`) incorrectly matched words like "diff", "interface", causing false conditional classifications.

**Solution**: 
- Keyword detection uses word-boundary regex: `\bif\b`, `\boptional\b`, `\brequired\b`
- This prevents matches inside words (e.g., "diff" no longer triggers conditional)

**Snippet extraction for `optionality_raw_snippet`**:
- **First pass**: Scan line-by-line and pick the first line containing the relevant keyword
- **Fallback pass**: Sentence splitting if no line match
- **Normalization**: Whitespace inside snippet normalized (`\s+` → single space)

**Example**:
- Old: `"This is a diff calculation"` → `optionality="conditional"` (false positive)
- New: `"This is a diff calculation"` → `optionality="none"` (correct)

### 2) `extract_section_description()` Robustness

**Problem**: Function returned `None` if expected nested table structure was missing, causing sections to lose descriptions.

**Solution**:
- **Missing nested table fallback**: If nested table is missing, fallback to `content_td` or the first `<td>` within it
- This allows extraction even when HTML structure varies

**Improved "stop" detection**:
- Only stop when a `<table>` looks like a parameter-definition table:
  - The type cell (`<td>`) contains "type" OR one of: INTEGER, REAL, CHARACTER, LOGICAL
  - AND it's NOT a metadata table (whitelist check)
- **Expanded metadata-table whitelist**:
  - Include "see also:" (case-insensitive)
  - Handle missing apostrophes (apostrophe-tolerant matching: "cards options" matches "Card's options:")

**Result**: More sections have descriptions extracted, fewer false stops at metadata tables.

### 3) `extract_card_structured_fields()` Traversal and Extraction Improvements

**Problem**: Inconsistent traversal starting point and fragile extraction logic.

**Solution**:
- **Traversal root consistency**: Uses same nested content root logic as `extract_section_description()` for consistency
  - Locates `tr_with_h2`, `next_tr`, `content_td`, `nested_table`, `nested_td` using identical logic
  - Iterates through `nested_td.children` in document order

**"Card's options" matching**:
- Case-insensitive and apostrophe-tolerant
- Matches "Card's options:", "card options", "CARDS OPTIONS", etc.

**Syntax extraction fallback**:
- If syntax table (`<div class="syntax"><table>`) is missing, extract `<pre>` text
- Light whitespace normalization (line trimming, preserve structure)

**Items extraction robustness**:
- Search forward until the next `<h3>` boundary (not just immediate siblings)
- Handle cases where blockquote nesting differs
- Only extract parameter-definition tables (with type token detection: INTEGER, REAL, CHARACTER, LOGICAL)

**Result**: More reliable card field extraction, especially for cards with non-standard HTML structure.

### 4) Regeneration and Invariants

After the robustness pass:
- **JSON regenerated**: `src/quantumvitas/data/qe_module_parameters.json` updated
- **Schema version**: Remains 3 (no schema changes)
- **Parameter count**: Unchanged (no accidental drops)
- **Order preservation**: Still guaranteed:
  - No `sorted()` calls
  - `json.dump(..., sort_keys=False)`

---

### Output

```python
json.dump({
    "schema_version": 3,
    "modules": {
        "pw": {
            "doc_url": "...",
            "sections": sections_tree,  # NEW: hierarchical
            "parameters": ordered_parameters,  # V3 logic
        }
    }
}, file, sort_keys=False)  # CRITICAL: preserve order
```

---

## Implementation Notes

### Order Preservation

**Critical**: The extractor must NEVER sort anything:
- No `sorted()` calls on parameter lists
- No `sort_keys=True` in `json.dump()`
- Use `dict` (Python 3.7+ preserves insertion order) and `list` (preserves order)
- Only use `set` for deduplication in diff computations (not for storage)

### Section Attribution

V2 and v3 use the same strategy:
- For each parameter table, find the nearest previous `<h2>` or `<h3>` that matches:
  - `"Namelist: &NAME"` → section = `"&NAME"`
  - `"Card: NAME"` → section = `"NAME"`
- Ignore other headings (e.g., "Description of items:", "Syntax:")
- This prevents incorrect attribution of card item tables to previous namelists

### Error Handling

- Parameters with parentheses that cannot be fully parsed are still extracted with `raw_spec` fallback
- Missing metadata fields default to `None` (not omitted from JSON)
- Invalid HTML structures are skipped with warnings (verbose mode)

### Known Limitations

1. **Card item parameters**: Parameters extracted into `card.items[]` are NOT merged into `module.parameters`. This is intentional to preserve the distinction between card-specific items and module-level parameters.

2. **Section descriptions**: Descriptions are extracted from content immediately after the `<h2>` header. If the HTML structure deviates significantly from the expected nested table pattern, some descriptions may be missed even with fallbacks.

3. **Optionality classification**: Classification is based solely on keyword presence in the description text. It does not parse complex conditional logic or cross-reference other parameters.

4. **Supercard nesting**: Only `BEGIN_*` supercards are stored as nodes. `END_*` elements are used only to close supercards and are not stored.

5. **Parameter table detection**: The extractor relies on specific HTML patterns (parameter tables with type cells). Non-standard table structures may not be recognized.

---

## Validation Checklist

To validate the v3 extractor locally:

### 1. Run Extractor

```bash
cd /Users/up/quantumVITAS
python3 tools/extract_qe_parameters_v3.py --use-cache --pretty
```

**Check**:
- Only one canonical output JSON path: `src/quantumvitas/data/qe_module_parameters.json`
- No errors or warnings (check stderr)

### 2. Verify Schema and Structure

```python
import json
from pathlib import Path

v4_path = Path('src/quantumvitas/data/qe_module_parameters.json')
v4_data = json.loads(v4_path.read_text())

# Check schema version
assert v3_data.get('schema_version') == 3

# Check module count (should be 22)
assert len(v3_data.get('modules', {})) == 22

# Check parameter count (should be ~1081)
total_params = sum(len(mod.get('parameters', {})) for mod in v3_data['modules'].values())
assert total_params >= 1000  # Approximate check
```

### 3. Verify Order Preservation

```python
# Check that JSON was written with sort_keys=False
# (Order is preserved in Python 3.7+ dicts)
# Verify by checking that parameter keys appear in document order
# (first parameters from first sections, etc.)
```

### 4. Verify Optionality Improvements

```python
# Check that optionality no longer misfires on "diff/interface"
# Look for sections with descriptions containing "diff" or "interface"
# They should have optionality="none", not "conditional"

for mod_name, mod_data in v4_data['modules'].items():
    sections = mod_data.get('sections', [])
    def check_sections(sections_list):
        for sec in sections_list:
            desc = sec.get('description', '').lower()
            opt = sec.get('optionality')
            if 'diff' in desc or 'interface' in desc:
                # Should NOT be conditional due to these words
                if opt == 'conditional':
                    # Check if it's actually conditional for other reasons
                    if 'if' not in desc.replace('diff', '').replace('interface', ''):
                        print(f"Warning: {mod_name}.{sec.get('name')} may have false positive")
            if sec.get('children'):
                check_sections(sec['children'])
    check_sections(sections)
```

### 5. Verify Section Descriptions

```python
# Check that more sections have descriptions (due to fallbacks)
sections_with_desc = 0
total_sections = 0

def count_sections(sections_list):
    global sections_with_desc, total_sections
    for sec in sections_list:
        total_sections += 1
        if sec.get('description'):
            sections_with_desc += 1
        if sec.get('children'):
            count_sections(sec['children'])

for mod_name, mod_data in v4_data['modules'].items():
    count_sections(mod_data.get('sections', []))

print(f"Sections with descriptions: {sections_with_desc}/{total_sections}")
# Should be a reasonable percentage (e.g., >30%)
```

### 6. Verify Card Fields

```python
# Check that known cards have structured fields
# Example: CELL_PARAMETERS in PW module should have options

pw_data = v3_data['modules'].get('pw', {})
pw_sections = pw_data.get('sections', [])

def find_card(sections_list, card_name):
    for sec in sections_list:
        if sec.get('name') == card_name and sec.get('kind') == 'card':
            return sec
        if sec.get('children'):
            found = find_card(sec['children'], card_name)
            if found:
                return found
    return None

cell_params = find_card(pw_sections, 'CELL_PARAMETERS')
if cell_params:
    assert cell_params.get('options') is not None, "CELL_PARAMETERS should have options"
    print(f"✓ CELL_PARAMETERS has options: {cell_params.get('options')}")
```

### 7. Debugging Tips

**If optionality seems wrong**:
- Check the `optionality_raw_snippet` field to see which text triggered the classification
- Verify the description text doesn't contain false-positive keywords (use word-boundary regex test)

**If section descriptions are missing**:
- Check the HTML structure in `temp/qe_docs/INPUT_*.html`
- Verify the nested table structure exists (or fallback should handle it)
- Use `--verbose` flag to see extraction diagnostics

**If card fields are missing**:
- Check that the card section has the expected HTML structure
- Verify "Card's options:" row exists (case-insensitive matching should handle variations)
- Check syntax extraction: look for `<div class="syntax">` or `<pre>` in the HTML

**If parameter count changed unexpectedly**:
- Compare with legacy v3 JSON: `qe_module_parameters.legacy.v3.json`
- Check for any new parameters discovered in tables (should be appended, not replacing)

---

## File Structure

```
tools/
  extract_qe_parameters_v1.py  # Legacy (not used)
  extract_qe_parameters_v2.py  # Legacy (not used)
  extract_qe_parameters_v2.py  # Current (documented, preserved)
  extract_qe_parameters_v3.py  # Current (active)

src/quantumvitas/data/
  qe_module_parameters.json              # Schema v3 (current)
  qe_module_parameters.legacy.v0.json    # Schema v0
  qe_module_parameters.legacy.v1.json    # Schema v1
  qe_module_parameters.legacy.v2.json    # Schema v2

docs/
  QE_HTML_EXTRACTOR.md  # This file
```

---

## References

- QE Documentation: https://www.quantum-espresso.org/Doc/
- HTML files: `temp/qe_docs/INPUT_*.html`
- JSON schema: See `src/quantumvitas/data/qe_module_parameters.json` (schema_version field)
