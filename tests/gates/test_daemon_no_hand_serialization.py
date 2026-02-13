"""
PR6 Gate Test: Daemon Endpoints Must Use DTOs (No Hand Serialization)

This test enforces that daemon endpoint handlers do not use hand-serialization patterns:
- json.dumps() (except in RPCResponse.to_json() for final wire serialization)
- .__dict__ or vars() for object serialization
- Manual dict construction when DTOs exist

All endpoint responses should use DTO.to_dict() or dataclasses.asdict() for serialization.

Reference:
- docs/history/plans/API_FACADE_IMPLEMENTATION_PLAN.md §Priority 3
"""

import ast
import re
from pathlib import Path

import pytest


def _find_handlers_in_file(file_path: Path) -> list[tuple[int, str]]:
    """
    Find all _handle_* methods in daemon server file.
    
    Returns:
        List of (line_number, method_name) tuples
    """
    handlers = []
    content = file_path.read_text()
    lines = content.splitlines()
    
    for i, line in enumerate(lines, start=1):
        if re.match(r'\s+def _handle_\w+\(', line):
            # Extract method name
            match = re.search(r'def (_handle_\w+)\(', line)
            if match:
                handlers.append((i, match.group(1)))
    
    return handlers


def _is_inside_docstring(lines: list[str], line_idx: int) -> bool:
    """
    Check if line_idx is inside a docstring by looking for unclosed triple quotes.
    
    Args:
        lines: All lines in the file
        line_idx: Index of line to check (0-indexed)
    
    Returns:
        True if inside a docstring, False otherwise
    """
    # Look backwards from line_idx to find the last opening triple quote
    text_before = '\n'.join(lines[:line_idx + 1])
    last_open = max(
        text_before.rfind('"""'),
        text_before.rfind("'''")
    )
    if last_open == -1:
        return False
    
    # Check if there's a closing triple quote after the opening one
    text_after_open = text_before[last_open + 3:]
    closing = text_after_open.find('"""')
    if closing == -1:
        closing = text_after_open.find("'''")
    # If no closing found, we're inside a docstring
    return closing == -1


def _check_for_allowlist_annotation(lines: list[str], line_idx: int) -> bool:
    """
    Check if line_idx or the immediately preceding line contains ALLOW_MANUAL_DICT annotation.
    
    Args:
        lines: List of all lines in the file
        line_idx: Index of line to check (0-indexed)
    
    Returns:
        True if allowlist annotation found, False otherwise
    """
    # Check current line
    if line_idx < len(lines):
        if '# ALLOW_MANUAL_DICT:' in lines[line_idx]:
            return True
    # Check immediately preceding line
    if line_idx > 0:
        if '# ALLOW_MANUAL_DICT:' in lines[line_idx - 1]:
            return True
    return False


def _check_manual_dict_literal(file_path: Path, line_num: int, line: str, method_name: str, 
                                context_lines: list[str], all_lines: list[str], line_idx: int) -> list[str]:
    """
    Check for manual dict literal construction in handler methods.
    
    Flags dict literals like {"key": obj.attr, ...} or items.append({"ulid": t.id, ...})
    unless they have an allowlist annotation or are in allowed contexts.
    
    Args:
        file_path: Path to file being checked
        line_num: Line number (1-indexed)
        line: Line content to check
        method_name: Name of the method containing this line
        context_lines: List of lines around this line for context checking
        all_lines: All lines in the file (for allowlist checking)
        line_idx: Index of current line (0-indexed)
    
    Returns:
        List of violation messages (empty if none)
    """
    violations = []
    
    # Skip comments and strings
    stripped = line.strip()
    if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
        return violations
    
    # Skip if line is inside a docstring
    if _is_inside_docstring(all_lines, line_idx):
        return violations
    
    # Skip if line contains triple quotes (likely docstring delimiter)
    if '"""' in line or "'''" in line:
        return violations
    
    # Check for allowlist annotation
    if _check_for_allowlist_annotation(all_lines, line_idx):
        return violations
    
    # Check if we're in RPCResponse.to_json() - already allowed
    context_lower = ' '.join([line] + context_lines[:5]).lower()
    if 'def to_json' in context_lower or 'rpcresponse' in context_lower:
        return violations
    
    # Check for file I/O / cache usage - allow these
    if any(keyword in context_lower for keyword in ['write_text', '.write(', 'sqlite', 'db_path', 
                                                     'conn.execute', 'cursor.execute', 'cache']):
        return violations
    
    # Skip set literals (e.g., `if k not in {"code", "message"}:`)
    # Set literals don't have colons, so if we see { ... } without :, it's likely a set
    # But we also need to check for dict access patterns like .get("key", {})
    if '.get(' in line or '.setdefault(' in line:
        return violations
    
    # Pattern: Dict literal with object attribute access
    # Examples: 
    #   items.append({"ulid": t.id, "name": t.name})  - FLAG THIS
    #   return {"ok": True, "enabled": bool_value}  - DON'T FLAG (no obj.attr)
    #   if k not in {"code", "message"}:  - DON'T FLAG (set literal, no :)
    
    # Pattern to match: "key": obj.attr (object attribute access, not method calls)
    dict_literal_pattern = r'["\']\w+["\']\s*:\s*\w+\.\w+(?!\s*\()'
    
    # Check for dict literal pattern: { "key": obj.attr, ... } 
    # Must have: { ... "key": var.attr ... } where var.attr is object attribute access
    # We want to flag: {"ulid": t.id, "name": t.name} but NOT {"ok": True, "enabled": settings.get(...)}
    if '{' in line and ':' in line:
        # Look for pattern: {"key": obj.attr where obj.attr is NOT a method call
        if re.search(dict_literal_pattern, line):
            # Make sure it's not from to_dict()/asdict() and then filtered
            if 'to_dict()' not in line and 'asdict(' not in line:
                violations.append(f"Manual dict literal construction found (use DTO.to_dict() or dataclasses.asdict() instead)")
    
    # Also check for multi-line dict literals
    # Only flag if current line starts a dict (like "return {", "param_dict = {", "append({") 
    # AND we see the pattern in the immediate next 2-3 lines
    if '{' in line and (line.strip().endswith('{') or '= {' in line or 'return {' in line or '.append({' in line or '.extend({' in line):
        # Only look at immediate next 2-3 lines for the pattern
        # Check each line individually for the pattern
        pattern_found = False
        for check_line in context_lines[:3]:
            if ':' in check_line and re.search(dict_literal_pattern, check_line):
                pattern_found = True
                break
        if pattern_found:
            # Make sure it's not from to_dict()/asdict()
            combined = ' '.join([line] + context_lines[:3])
            if 'to_dict()' not in combined and 'asdict(' not in combined:
                violations.append(f"Manual dict literal construction found (use DTO.to_dict() or dataclasses.asdict() instead)")
    
    return violations


def _check_line_for_violations(file_path: Path, line_num: int, line: str, method_name: str, context_lines: list[str], 
                                all_lines: list[str] = None, line_idx: int = None) -> list[str]:
    """
    Check a single line for hand-serialization violations.
    
    Args:
        file_path: Path to file being checked
        line_num: Line number (1-indexed)
        line: Line content to check
        method_name: Name of the method containing this line
        context_lines: List of lines around this line for context checking
        all_lines: All lines in the file (for allowlist checking)
        line_idx: Index of current line (0-indexed)
    
    Returns:
        List of violation messages (empty if none)
    """
    violations = []
    
    # Check for json.dumps (except in to_json methods and file I/O operations)
    if 'json.dumps(' in line and 'def to_json' not in line and 'to_json()' not in line:
        # Get context (current line + next 5 lines)
        context = ' '.join([line] + context_lines[:5]).lower()
        
        # Allow json.dumps in RPCResponse.to_json() method
        if line.strip().startswith('return json.dumps'):
            # Check if we're in a to_json method
            method_start = max(0, line_num - 20)
            method_context = '\n'.join(context_lines[-20:]) if len(context_lines) > 20 else '\n'.join(context_lines)
            if 'def to_json' in method_context or 'RPCResponse' in method_context:
                pass  # Allowed in to_json()
            else:
                violations.append(f"json.dumps() in return statement (use DTO.to_dict() instead)")
        # Allow json.dumps for file I/O operations (write_text, file operations)
        elif 'write_text' in context or '.write(' in context or 'file' in context:
            pass  # Allowed for file I/O
        # Allow json.dumps for cache/database storage (SQLite, cache operations)
        elif 'sqlite' in context or 'db_path' in context or 'conn.execute' in context or 'cursor.execute' in context:
            pass  # Allowed for cache/database storage
        else:
            violations.append(f"json.dumps() found (use DTO.to_dict() instead)")
    
    # Check for __dict__ access
    if '__dict__' in line and not line.strip().startswith('#'):
        violations.append(f"__dict__ access found (use DTO.to_dict() or dataclasses.asdict() instead)")
    
    # Check for vars() usage
    if re.search(r'\bvars\s*\(', line) and not line.strip().startswith('#'):
        violations.append(f"vars() found (use DTO.to_dict() or dataclasses.asdict() instead)")
    
    # Check for manual dict construction in comprehensions (narrow pattern)
    # Pattern: list comprehension that builds dict literals with object attribute access
    # e.g., [{"a": x.a, "b": x.b} for x in items]
    # This is a conservative check - only flags list comprehensions with dict literals containing obj.attr
    if not line.strip().startswith('#'):
        # Check for list comprehension with dict literal containing object attribute access
        # Pattern: [{"key": var.attr, ...} for var in ...]
        # Must have: [ ... { ... var.attr ... } ... for var in ...]
        # Handle both single-line and multi-line (where { might be on previous line)
        if '[' in line and 'for' in line and 'in' in line:
            # Get context lines to check for multi-line dict literals
            full_context = ' '.join([line] + context_lines[:3])
            # Check if there's a dict literal with object attribute access
            # Look for pattern: [{...var.attr...} for var in ...] or [\n{...var.attr...}\n for var in ...]
            if '{' in full_context:
                # Extract the part before 'for'
                for_match = re.search(r'for\s+\w+\s+in', full_context)
                if for_match:
                    before_for = full_context[:for_match.start()]
                    # Check if before 'for' there's a dict literal with obj.attr
                    # Pattern: [{...} ...] where {...} contains var.attr
                    if re.search(r'\{[^}]*\w+\.\w+[^}]*\}', before_for):
                        # Make sure it's inside a list comprehension (starts with [)
                        if '[' in before_for:
                            # Make sure it's not using to_dict() or asdict()
                            if 'to_dict()' not in full_context and 'asdict(' not in full_context:
                                violations.append(f"Manual dict construction in list comprehension (use DTO.to_dict() or dataclasses.asdict() instead)")
    
    # Check for manual dict literal construction (PR6.5 enhancement)
    if all_lines is not None and line_idx is not None:
        dict_violations = _check_manual_dict_literal(file_path, line_num, line, method_name, context_lines, all_lines, line_idx)
        violations.extend(dict_violations)
    
    return violations


def test_daemon_no_hand_serialization():
    """
    Scan daemon server for hand-serialization violations in endpoint handlers.
    
    Checks all _handle_* methods for:
    - json.dumps() (except in to_json methods)
    - .__dict__ access
    - vars() usage
    
    Manual dict construction is harder to detect automatically, but the above patterns
    are strong indicators of hand-serialization.
    """
    repo_root = Path(__file__).parent.parent.parent
    daemon_file = repo_root / "src" / "quantumvitas" / "daemon" / "server.py"
    
    if not daemon_file.exists():
        pytest.skip(f"Daemon server file not found: {daemon_file}")
    
    # Find all handler methods
    handlers = _find_handlers_in_file(daemon_file)
    
    if not handlers:
        pytest.skip("No _handle_* methods found in daemon server")
    
    # Read file content
    content = daemon_file.read_text()
    lines = content.splitlines()
    
    # Track violations
    all_violations = []
    
    # For each handler, check its body for violations
    for handler_line, handler_name in handlers:
        # Find the method body (next non-empty line to next def/class or end of file)
        start_line = handler_line
        end_line = len(lines)
        
        # Find the end of this method
        indent_level = len(lines[handler_line - 1]) - len(lines[handler_line - 1].lstrip())
        for i in range(handler_line, len(lines)):
            line = lines[i]
            if line.strip() and not line.strip().startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and (line.strip().startswith('def ') or line.strip().startswith('class ')):
                    end_line = i
                    break
        
        # Check each line in the method body
        for i in range(start_line, end_line):
            if i >= len(lines):
                break
            line = lines[i]
            # Get context (next 5 lines for checking)
            context_lines = lines[i+1:min(i+6, end_line)]
            violations = _check_line_for_violations(daemon_file, i + 1, line, handler_name, context_lines, lines, i)
            if violations:
                for violation in violations:
                    all_violations.append(
                        f"{daemon_file}:{i+1} in {handler_name}(): {violation}\n"
                        f"  Line: {line.strip()}"
                    )
        
        # Also check for multi-line list comprehensions that might span across lines
        # Look for patterns where [ starts on one line and { with obj.attr is on a later line
        for i in range(start_line, min(start_line + 100, end_line)):  # Check first 100 lines
            if i >= len(lines):
                break
            line = lines[i]
            # If line starts a list comprehension with [
            if '[' in line and 'for' not in line:
                # Look ahead up to 10 lines for the completion
                for j in range(i+1, min(i+11, end_line)):
                    if j >= len(lines):
                        break
                    next_line = lines[j]
                    # Check if we find 'for' and the pattern matches
                    if 'for' in next_line and 'in' in next_line:
                        # Combine lines from i to j
                        combined = ' '.join(lines[i:j+1])
                        # Check if there's a dict literal with obj.attr
                        if '{' in combined and re.search(r'\w+\.\w+', combined):
                            # Check if it's a list comprehension pattern
                            if re.search(r'\[.*?\{[^}]*\w+\.\w+[^}]*\}.*?for\s+\w+\s+in', combined):
                                # Make sure it's not using to_dict() or asdict()
                                if 'to_dict()' not in combined and 'asdict(' not in combined:
                                    all_violations.append(
                                        f"{daemon_file}:{i+1} in {handler_name}(): Manual dict construction in list comprehension (use DTO.to_dict() or dataclasses.asdict() instead)\n"
                                        f"  Lines {i+1}-{j+1}: {line.strip()[:80]} ... {next_line.strip()[:80]}"
                                    )
                        break  # Found the 'for', stop looking ahead
    
    # Also check for manual dict construction patterns in handlers
    # Look for dict comprehensions or dict literals that might be manual serialization
    # This is a heuristic - we look for patterns like {key: obj.attr for ...} or {key: obj.attr}
    for handler_line, handler_name in handlers:
        # Get method body
        start_line = handler_line
        indent_level = len(lines[handler_line - 1]) - len(lines[handler_line - 1].lstrip())
        end_line = len(lines)
        for i in range(handler_line, len(lines)):
            line = lines[i]
            if line.strip() and not line.strip().startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and (line.strip().startswith('def ') or line.strip().startswith('class ')):
                    end_line = i
                    break
        
        # Check for manual dict construction (heuristic: dict with object attribute access)
        for i in range(start_line, min(start_line + 50, end_line)):  # Check first 50 lines of method
            if i >= len(lines):
                break
            line = lines[i]
            # Look for patterns like {"key": obj.attr, ...} that might be manual serialization
            # This is a conservative check - we only flag obvious cases
            if re.search(r'\{[^}]*\w+\.\w+[^}]*\}', line) and 'to_dict()' not in line and 'asdict(' not in line:
                # Check if it's a return statement with a dict literal
                if 'return' in line and '{' in line:
                    # This might be manual serialization, but it's hard to be sure
                    # We'll be conservative and only flag if it's clearly a violation
                    pass
    
    if all_violations:
        error_msg = (
            "Hand-serialization violations found in daemon endpoints:\n\n"
            + "\n\n".join(all_violations)
            + "\n\n"
            "All endpoint handlers must use DTO.to_dict() or dataclasses.asdict() "
            "for serialization, not json.dumps(), __dict__, or vars()."
        )
        pytest.fail(error_msg)


def test_all_handler_responses_json_serializable():
    """
    Every handler response must be JSON-serializable.

    This is a runtime guard complementing the static AST checks.
    """
    import json
    from io import StringIO
    from tests.contract_crawler.crawler import crawl_all_methods

    report = crawl_all_methods()

    failures = report.not_json_serializable
    if failures:
        failure_details = "\n".join([
            f"  - {r.method_name}: {r.serialization_error}"
            for r in failures
        ])
        pytest.fail(f"Handlers returning non-JSON-serializable data:\n{failure_details}")


def test_no_dto_leakage_in_responses():
    """
    Handler responses must not contain DTO instances (must use to_dict()).
    """
    from io import StringIO
    from tests.contract_crawler.crawler import crawl_all_methods
    from quantumvitas.api.types.base import BaseDTO

    def check_for_dto_leakage(obj, path=""):
        """Recursively check for DTO instances."""
        if isinstance(obj, BaseDTO):
            return [f"{path}: Found raw DTO {type(obj).__name__}"]

        leaks = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                leaks.extend(check_for_dto_leakage(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                leaks.extend(check_for_dto_leakage(v, f"{path}[{i}]"))

        return leaks

    report = crawl_all_methods()

    all_leaks = []
    for result in report.covered:
        if result.response_data:
            leaks = check_for_dto_leakage(result.response_data, result.method_name)
            all_leaks.extend(leaks)

    assert not all_leaks, f"DTO leakage detected:\n" + "\n".join(all_leaks)

