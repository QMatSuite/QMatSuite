"""
Test to enforce the single-point canonicalization contract and pure bond detection.

This test prevents accidental reintroduction of canonicalization in internal helpers
by checking that:
1. canonicalize_frac_coords() and canonicalize_structure_in_place() are only called
   from allowed entry points.
2. Bond detection functions (detect_bonds, build_bonds, build_bonds_bruteforce,
   build_bonds_cell_list) do NOT call any canonicalization functions.
"""

import pathlib
import re


def test_canonicalize_frac_coords_usage_is_restricted():
    """
    Enforce that canonicalize_frac_coords() is only called from allowed locations.
    
    Allowed call sites:
    - Inside canonicalize_structure_in_place() (the only production caller)
    - Inside wrap_fractional_coords() (thin wrapper for backward compatibility)
    
    Forbidden: Any direct calls in helpers like detect_bonds, make_supercell, etc.
    """
    # Find structure_viz.py
    test_file = pathlib.Path(__file__)
    repo_root = test_file.parents[2]
    structure_viz_path = repo_root / "src" / "quantumvitas" / "analysis" / "structure_viz.py"
    
    assert structure_viz_path.exists(), f"File not found: {structure_viz_path}"
    
    text = structure_viz_path.read_text()
    
    # Find all occurrences of "canonicalize_frac_coords("
    # We'll use a simple pattern: look for the function call
    pattern = r'canonicalize_frac_coords\s*\('
    matches = list(re.finditer(pattern, text))
    
    # Classify each occurrence
    allowed_contexts = []
    forbidden_contexts = []
    
    for match in matches:
        start_pos = match.start()
        # Get surrounding context (100 chars before and after)
        context_start = max(0, start_pos - 100)
        context_end = min(len(text), start_pos + 100)
        context = text[context_start:context_end]
        
        # Check if it's in the definition
        if 'def canonicalize_frac_coords(' in text[:start_pos + 200]:
            # This is the function definition, skip it
            continue
        
        # Find the function that contains this call
        func_start = text.rfind('def ', 0, start_pos)
        if func_start != -1:
            func_end = text.find(':', func_start)
            func_name = text[func_start:func_end].strip()
            
            if 'canonicalize_structure_in_place' in func_name:
                allowed_contexts.append((start_pos, "inside canonicalize_structure_in_place"))
                continue
            
            if 'wrap_fractional_coords' in func_name:
                allowed_contexts.append((start_pos, "inside wrap_fractional_coords (wrapper)"))
                continue
            
            # Check function name to see if it's a forbidden helper
            # Bond detection functions MUST NOT canonicalize - they are pure geometric functions
            forbidden_helpers = [
                'detect_bonds',
                'make_supercell',
                'generate_boundary_atoms',
                'build_bonds',
                'build_bonds_bruteforce',
                'build_bonds_cell_list',
            ]
            
            is_forbidden = any(helper in func_name for helper in forbidden_helpers)
            if is_forbidden:
                forbidden_contexts.append((start_pos, f"inside {func_name} (FORBIDDEN)"))
            else:
                # Unknown context - might be allowed, but log it
                allowed_contexts.append((start_pos, f"inside {func_name} (unknown, but not explicitly forbidden)"))
    
    # Report findings
    if forbidden_contexts:
        error_msg = "FORBIDDEN: canonicalize_frac_coords() called from internal helpers:\n"
        for pos, desc in forbidden_contexts:
            # Get line number
            line_num = text[:pos].count('\n') + 1
            error_msg += f"  Line {line_num}: {desc}\n"
        error_msg += "\nCanonicalization must only happen at entry points (build_display_atoms, visualize_structure, plot_structure_3d)."
        assert False, error_msg
    
    # If we get here, all calls are in allowed contexts
    assert len(allowed_contexts) > 0 or len(matches) == 1, (
        f"Found {len(matches)} occurrences of canonicalize_frac_coords(), "
        f"but none in allowed contexts. This might indicate a parsing issue."
    )


def test_canonicalize_structure_in_place_usage_is_restricted():
    """
    Enforce that canonicalize_structure_in_place() is only called from allowed entry points.
    
    Allowed call sites (whitelist):
    - build_display_atoms() - main entry for GUI visualization
    - visualize_structure() - high-level API entry point
    - plot_structure_3d() - matplotlib visualization entry point
    
    Forbidden: Any calls in helpers like detect_bonds, make_supercell, etc.
    """
    # Find structure_viz.py
    test_file = pathlib.Path(__file__)
    repo_root = test_file.parents[2]
    structure_viz_path = repo_root / "src" / "quantumvitas" / "analysis" / "structure_viz.py"
    
    assert structure_viz_path.exists(), f"File not found: {structure_viz_path}"
    
    text = structure_viz_path.read_text()
    
    # Find all occurrences of "canonicalize_structure_in_place("
    pattern = r'canonicalize_structure_in_place\s*\('
    matches = list(re.finditer(pattern, text))
    
    # Whitelist of allowed entry points
    allowed_entry_points = [
        'build_display_atoms',
        'visualize_structure',
        'plot_structure_3d',
    ]
    
    # Classify each occurrence
    allowed_contexts = []
    forbidden_contexts = []
    
    for match in matches:
        start_pos = match.start()
        
        # Check if it's in the definition
        if 'def canonicalize_structure_in_place(' in text[:start_pos + 200]:
            # This is the function definition, skip it
            continue
        
        # Check if it's in a comment or docstring (not actual code)
        # Look backwards for the nearest newline
        line_start = text.rfind('\n', 0, start_pos) + 1
        line_text = text[line_start:start_pos].strip()
        
        # Skip if it's in a comment (line starts with #)
        if line_text.startswith('#'):
            continue
        
        # Skip if it's in a docstring (look for triple quotes before this position)
        # Find the last """ or ''' before this position
        last_triple_quote = max(
            text.rfind('"""', 0, start_pos),
            text.rfind("'''", 0, start_pos)
        )
        if last_triple_quote != -1:
            # Check if there's a closing triple quote after the opening but before our match
            closing_quote = text.find('"""', last_triple_quote + 3, start_pos)
            if closing_quote == -1:
                closing_quote = text.find("'''", last_triple_quote + 3, start_pos)
            if closing_quote == -1:
                # We're inside an unclosed docstring, skip
                continue
        
        # Find the function that contains this call
        func_start = text.rfind('def ', 0, start_pos)
        if func_start != -1:
            func_end = text.find(':', func_start)
            func_name_line = text[func_start:func_end]
            # Extract just the function name
            func_match = re.search(r'def\s+(\w+)', func_name_line)
            if func_match:
                func_name = func_match.group(1)
                
                # Check if it's in an allowed entry point
                is_allowed = any(entry in func_name for entry in allowed_entry_points)
                
                if is_allowed:
                    allowed_contexts.append((start_pos, f"inside {func_name} (ALLOWED entry point)"))
                else:
                    forbidden_contexts.append((start_pos, f"inside {func_name} (FORBIDDEN)"))
    
    # Report findings
    if forbidden_contexts:
        error_msg = "FORBIDDEN: canonicalize_structure_in_place() called from non-entry-point functions:\n"
        for pos, desc in forbidden_contexts:
            # Get line number
            line_num = text[:pos].count('\n') + 1
            error_msg += f"  Line {line_num}: {desc}\n"
        error_msg += "\nCanonicalization must only happen at entry points: "
        error_msg += ", ".join(allowed_entry_points)
        assert False, error_msg
    
    # Verify we found calls in allowed entry points
    # We expect at least calls in build_display_atoms, visualize_structure, and plot_structure_3d
    # (Note: visualize_structure may not call it directly if it delegates to plot_structure_3d)
    if len(allowed_contexts) == 0 and len(matches) > 1:
        # If we found matches but no allowed contexts, the parsing might be wrong
        # But if we have no forbidden contexts either, that's OK (maybe all are in comments)
        if len(forbidden_contexts) == 0:
            # All matches were filtered out (probably in comments/docstrings), which is fine
            pass
        else:
            # We have forbidden contexts, which is a real problem
            error_msg = "FORBIDDEN: canonicalize_structure_in_place() called from non-entry-point functions:\n"
            for pos, desc in forbidden_contexts:
                line_num = text[:pos].count('\n') + 1
                error_msg += f"  Line {line_num}: {desc}\n"
            error_msg += "\nCanonicalization must only happen at entry points: "
            error_msg += ", ".join(allowed_entry_points)
            assert False, error_msg
    
    # If we have allowed contexts, verify they're in entry points
    if allowed_contexts:
        allowed_funcs = [desc for _, desc in allowed_contexts]
        for func_desc in allowed_funcs:
            is_entry = any(entry in func_desc for entry in allowed_entry_points)
            assert is_entry, (
                f"Found canonicalize_structure_in_place() call in {func_desc}, "
                f"but this is not an allowed entry point. Allowed: {allowed_entry_points}"
            )


def test_bond_detection_functions_do_not_canonicalize():
    """
    Enforce that bond detection functions are pure geometric functions.
    
    Bond detection functions (detect_bonds, build_bonds, build_bonds_bruteforce,
    build_bonds_cell_list) MUST NOT call any canonicalization functions.
    They must be pure: given fixed geometry, return deterministic bonds.
    """
    # Find structure_viz.py
    test_file = pathlib.Path(__file__)
    repo_root = test_file.parents[2]
    structure_viz_path = repo_root / "src" / "quantumvitas" / "analysis" / "structure_viz.py"
    
    assert structure_viz_path.exists(), f"File not found: {structure_viz_path}"
    
    text = structure_viz_path.read_text()
    
    # Bond detection functions that must NOT canonicalize
    bond_functions = [
        'detect_bonds',
        'build_bonds',
        'build_bonds_bruteforce',
        'build_bonds_cell_list',
    ]
    
    # Canonicalization functions that must NOT be called
    canonicalization_patterns = [
        r'canonicalize_structure_in_place\s*\(',
        r'canonicalize_frac_coords\s*\(',
        r'wrap_fractional_coords\s*\(',
    ]
    
    violations = []
    
    for func_name in bond_functions:
        # Find the function definition
        func_pattern = rf'def\s+{func_name}\s*\('
        func_match = re.search(func_pattern, text)
        
        if not func_match:
            continue  # Function not found, skip
        
        func_start = func_match.start()
        
        # Find the end of the function (next def or end of file)
        next_def = text.find('\ndef ', func_start + 1)
        if next_def == -1:
            func_end = len(text)
        else:
            func_end = next_def
        
        func_body = text[func_start:func_end]
        
        # Check for canonicalization calls in the function body
        for pattern in canonicalization_patterns:
            matches = list(re.finditer(pattern, func_body))
            for match in matches:
                # Check if it's in a comment or docstring
                match_pos_in_body = match.start()
                line_start_in_body = func_body.rfind('\n', 0, match_pos_in_body) + 1
                line_text = func_body[line_start_in_body:match_pos_in_body].strip()
                
                # Skip if it's in a comment
                if line_text.startswith('#'):
                    continue
                
                # Skip if it's in a docstring
                # Find the last """ or ''' before this position in the function body
                last_triple_quote = max(
                    func_body.rfind('"""', 0, match_pos_in_body),
                    func_body.rfind("'''", 0, match_pos_in_body)
                )
                if last_triple_quote != -1:
                    closing_quote = func_body.find('"""', last_triple_quote + 3, match_pos_in_body)
                    if closing_quote == -1:
                        closing_quote = func_body.find("'''", last_triple_quote + 3, match_pos_in_body)
                    if closing_quote == -1:
                        # Inside unclosed docstring, skip
                        continue
                
                # This is a violation - canonicalization in a bond function
                actual_pos = func_start + match.start()
                line_num = text[:actual_pos].count('\n') + 1
                violations.append((func_name, pattern, line_num))
    
    if violations:
        error_msg = "VIOLATION: Bond detection functions must NOT canonicalize:\n"
        for func_name, pattern, line_num in violations:
            error_msg += f"  {func_name}() calls {pattern} at line {line_num}\n"
        error_msg += "\nBond detection functions must be pure geometric functions."
        error_msg += " All canonicalization must happen at entry points before calling bond functions."
        assert False, error_msg
