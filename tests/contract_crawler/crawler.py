"""Contract crawler for daemon RPC methods."""

import json
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest

from .introspection import get_all_rpc_methods
from .payloads import get_minimal_payload, get_methods_needing_recipes


@dataclass
class CrawlResult:
    """Result of crawling a single RPC method."""
    method_name: str
    success: bool
    response_data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    json_serializable: bool = True
    serialization_error: str | None = None
    needs_recipe: bool = False
    skipped_reason: str | None = None


@dataclass
class CrawlReport:
    """Aggregated crawl results."""
    results: list[CrawlResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def covered(self) -> list[CrawlResult]:
        return [r for r in self.results if r.success and not r.needs_recipe]

    @property
    def needs_recipe(self) -> list[CrawlResult]:
        return [r for r in self.results if r.needs_recipe]

    @property
    def failed(self) -> list[CrawlResult]:
        return [r for r in self.results if not r.success and not r.needs_recipe]

    @property
    def not_json_serializable(self) -> list[CrawlResult]:
        return [r for r in self.results if not r.json_serializable]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "covered": len(self.covered),
            "needs_recipe": len(self.needs_recipe),
            "failed": len(self.failed),
            "not_json_serializable": len(self.not_json_serializable),
            "coverage_pct": round(len(self.covered) / self.total * 100, 1) if self.total else 0,
            "results": [
                {
                    "method": r.method_name,
                    "status": "covered" if r.success else ("needs_recipe" if r.needs_recipe else "failed"),
                    "json_ok": r.json_serializable,
                    "error": r.error or r.serialization_error,
                }
                for r in self.results
            ],
        }


def crawl_method(
    daemon: QVDaemon,
    method_name: str,
    payload: dict[str, Any],
) -> CrawlResult:
    """
    Crawl a single RPC method.

    Args:
        daemon: QVDaemon instance
        method_name: RPC method name
        payload: Request payload

    Returns:
        CrawlResult with response data and validation status.
    """
    try:
        response = daemon.handle_request(RPCRequest(
            id=f"crawl-{method_name}",
            type=method_name,
            payload=payload,
        ))

        if not response.ok:
            return CrawlResult(
                method_name=method_name,
                success=False,
                error=response.error,
            )

        # Validate JSON serialization
        try:
            json_str = json.dumps(response.data)
            # Also verify roundtrip
            parsed = json.loads(json_str)

            return CrawlResult(
                method_name=method_name,
                success=True,
                response_data=parsed,
                json_serializable=True,
            )
        except (TypeError, ValueError) as e:
            return CrawlResult(
                method_name=method_name,
                success=True,
                response_data=response.data,
                json_serializable=False,
                serialization_error=str(e),
            )

    except Exception as e:
        return CrawlResult(
            method_name=method_name,
            success=False,
            error={"code": "exception", "message": str(e)},
        )


def crawl_all_methods(
    project_root: Path | None = None,
    include_recipes: bool = False,
) -> CrawlReport:
    """
    Crawl all RPC methods with minimal payloads.

    Args:
        project_root: Optional project path for project-scoped methods
        include_recipes: If True, skip recipe-required methods; else mark them

    Returns:
        CrawlReport with all results.
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    methods = get_all_rpc_methods()
    needs_recipes = get_methods_needing_recipes()

    report = CrawlReport()

    for method in methods:
        name = method.name

        if name in needs_recipes:
            if include_recipes:
                continue  # Skip - will be covered by recipe tests
            report.results.append(CrawlResult(
                method_name=name,
                success=False,
                needs_recipe=True,
                skipped_reason="Requires recipe (complex prerequisites)",
            ))
            continue

        payload = get_minimal_payload(name, project_root)

        if payload is None:
            report.results.append(CrawlResult(
                method_name=name,
                success=False,
                needs_recipe=True,
                skipped_reason="No minimal payload defined",
            ))
            continue

        result = crawl_method(daemon, name, payload)
        report.results.append(result)

    return report

