"""
Discovery runner: best-effort attempt to call all RPC methods.

This is a developer tool to "bucket failures" and rapidly expand coverage.
It attempts all methods and categorizes failures for easier triage.
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from quantumvitas.daemon.server import QVDaemon, RPCRequest

from tests.contract_crawler.introspection import get_all_rpc_methods
from tests.contract_crawler.payloads import get_minimal_payload, get_methods_needing_recipes


@dataclass
class DiscoveryResult:
    """Result of attempting a single method."""
    method_name: str
    attempt_status: str  # "success" | "failed"
    failure_bucket: str | None  # "no_payload" | "missing_fields" | "needs_resources" | "error" | None
    error_type: str | None
    error_message: str | None


OUTPUT_FILE = Path(__file__).parent / "discovery_report.json"


def normalize_error(error: Any) -> tuple[str, str]:
    """
    Normalize error to type and message.
    
    Returns:
        Tuple of (error_type, error_message) with message truncated to 200 chars.
    """
    if isinstance(error, dict):
        error_type = error.get("code", "unknown")
        error_message = str(error.get("message", "Unknown error"))
    elif isinstance(error, Exception):
        error_type = type(error).__name__
        error_message = str(error)
    else:
        error_type = "unknown"
        error_message = str(error)
    
    # Truncate message
    if len(error_message) > 200:
        error_message = error_message[:200] + "..."
    
    return error_type, error_message


def categorize_failure(error: Any, method_name: str) -> str:
    """
    Categorize failure into bucket.
    
    Buckets:
    - "no_payload": Payload generator returned None
    - "missing_fields": Validation error about required fields
    - "needs_resources": Needs project/calc/step resources
    - "error": Generic error
    """
    error_str = str(error).lower()
    error_msg = str(error) if isinstance(error, (str, dict)) else str(error)
    
    # Check for missing fields / validation errors
    if any(keyword in error_str for keyword in ["required", "missing", "invalid", "validation"]):
        return "missing_fields"
    
    # Check for resource needs
    if any(keyword in error_str for keyword in ["project", "calculation", "step", "structure", "not found", "not_found"]):
        return "needs_resources"
    
    # Check for unsafe operations (shutdown, etc.)
    if any(keyword in error_str for keyword in ["shutdown", "unsafe", "dangerous"]):
        return "error"  # Mark as error but don't attempt
    
    return "error"


def discover_method(method_name: str, daemon: QVDaemon) -> DiscoveryResult:
    """
    Attempt to call a single RPC method with best-effort payload.
    
    Returns:
        DiscoveryResult with attempt status and failure bucket.
    """
    # Check if method needs recipe
    needs_recipes = get_methods_needing_recipes()
    if method_name in needs_recipes:
        return DiscoveryResult(
            method_name=method_name,
            attempt_status="failed",
            failure_bucket="needs_resources",
            error_type="recipe_required",
            error_message="Method requires recipe (complex prerequisites)",
        )
    
    # Try to get payload
    try:
        payload = get_minimal_payload(method_name)
    except Exception as e:
        error_type, error_message = normalize_error(e)
        return DiscoveryResult(
            method_name=method_name,
            attempt_status="failed",
            failure_bucket="no_payload",
            error_type=error_type,
            error_message=error_message,
        )
    
    if payload is None:
        return DiscoveryResult(
            method_name=method_name,
            attempt_status="failed",
            failure_bucket="no_payload",
            error_type="no_payload_generator",
            error_message="No minimal payload defined for this method",
        )
    
    # Attempt the call
    try:
        response = daemon.handle_request(RPCRequest(
            id=f"discover-{method_name}",
            type=method_name,
            payload=payload,
        ))
        
        if response.ok:
            return DiscoveryResult(
                method_name=method_name,
                attempt_status="success",
                failure_bucket=None,
                error_type=None,
                error_message=None,
            )
        else:
            # Categorize the failure
            failure_bucket = categorize_failure(response.error, method_name)
            error_type, error_message = normalize_error(response.error)
            
            return DiscoveryResult(
                method_name=method_name,
                attempt_status="failed",
                failure_bucket=failure_bucket,
                error_type=error_type,
                error_message=error_message,
            )
    
    except Exception as e:
        failure_bucket = categorize_failure(e, method_name)
        error_type, error_message = normalize_error(e)
        
        return DiscoveryResult(
            method_name=method_name,
            attempt_status="failed",
            failure_bucket=failure_bucket,
            error_type=error_type,
            error_message=error_message,
        )


def discover_all_methods() -> list[DiscoveryResult]:
    """
    Attempt all RPC methods and return discovery results.
    
    Returns:
        List of DiscoveryResult objects.
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    all_methods = get_all_rpc_methods()
    
    results = []
    for method_info in all_methods:
        result = discover_method(method_info.name, daemon)
        results.append(result)
    
    return results


def main():
    """Run discovery and write report."""
    print("Running discovery on all RPC methods...")
    print("This may take a moment...\n")
    
    results = discover_all_methods()
    
    # Convert to dict for JSON serialization
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "total_methods": len(results),
        "success_count": sum(1 for r in results if r.attempt_status == "success"),
        "failure_count": sum(1 for r in results if r.attempt_status == "failed"),
        "failure_buckets": {
            bucket: sum(1 for r in results if r.failure_bucket == bucket)
            for bucket in ["no_payload", "missing_fields", "needs_resources", "error"]
        },
        "results": [asdict(r) for r in results],
    }
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"Discovery report written to: {OUTPUT_FILE}")
    print(f"\nSummary:")
    print(f"  Total methods: {report_data['total_methods']}")
    print(f"  Success: {report_data['success_count']}")
    print(f"  Failed: {report_data['failure_count']}")
    print(f"\nFailure buckets:")
    for bucket, count in report_data['failure_buckets'].items():
        print(f"  {bucket}: {count}")


if __name__ == "__main__":
    main()

