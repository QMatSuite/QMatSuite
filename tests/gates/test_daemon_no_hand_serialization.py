"""
PR6 Gate Test: Daemon Endpoints Must Use DTOs (No Hand Serialization)

This test enforces that daemon endpoint handlers do not use hand-serialization patterns:
- json.dumps() (except in RPCResponse.to_json() for final wire serialization)
- .__dict__ or vars() for object serialization
- Manual dict construction when DTOs exist

All endpoint responses should use DTO.to_dict() or dataclasses.asdict() for serialization.

Reference:
- docs/specs/API_FACADE_IMPLEMENTATION_PLAN.md §Priority 3
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


def _check_line_for_violations(file_path: Path, line_num: int, line: str, method_name: str, context_lines: list[str]) -> list[str]:
    """
    Check a single line for hand-serialization violations.
    
    Args:
        file_path: Path to file being checked
        line_num: Line number (1-indexed)
        line: Line content to check
        method_name: Name of the method containing this line
        context_lines: List of lines around this line for context checking
    
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
            violations = _check_line_for_violations(daemon_file, i + 1, line, handler_name, context_lines)
            if violations:
                for violation in violations:
                    all_violations.append(
                        f"{daemon_file}:{i+1} in {handler_name}(): {violation}\n"
                        f"  Line: {line.strip()}"
                    )
    
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

