"""Base class for RPC method recipes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest


@dataclass
class RecipeResult:
    """Result of executing a recipe."""
    recipe_name: str
    method_name: str
    success: bool
    response_data: dict[str, Any] | None = None
    error: str | None = None
    setup_ok: bool = True
    teardown_ok: bool = True


class Recipe(ABC):
    """Base class for RPC method test recipes."""

    method_name: str  # RPC method being tested
    description: str  # Human-readable description

    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.project_root: Path | None = None
        self.daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

    @abstractmethod
    def setup(self) -> bool:
        """
        Set up prerequisites for the method call.

        Returns:
            True if setup succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def build_payload(self) -> dict[str, Any]:
        """
        Build the request payload.

        Returns:
            Payload dict for RPC call.
        """
        pass

    @abstractmethod
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate the response data.

        Args:
            response_data: Response from RPC call

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    def teardown(self) -> bool:
        """
        Clean up after test.

        Returns:
            True if teardown succeeded.
        """
        return True

    def execute(self) -> RecipeResult:
        """
        Execute the full recipe.

        Returns:
            RecipeResult with all execution details.
        """
        # Setup
        try:
            if not self.setup():
                return RecipeResult(
                    recipe_name=self.__class__.__name__,
                    method_name=self.method_name,
                    success=False,
                    error="Setup failed",
                    setup_ok=False,
                )
        except Exception as e:
            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=False,
                error=f"Setup exception: {e}",
                setup_ok=False,
            )

        # Execute
        try:
            payload = self.build_payload()
            response = self.daemon.handle_request(RPCRequest(
                id=f"recipe-{self.method_name}",
                type=self.method_name,
                payload=payload,
            ))

            if not response.ok:
                return RecipeResult(
                    recipe_name=self.__class__.__name__,
                    method_name=self.method_name,
                    success=False,
                    error=str(response.error),
                )

            # Validate
            is_valid, error = self.validate_response(response.data)

            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=is_valid,
                response_data=response.data if is_valid else None,
                error=error,
            )

        except Exception as e:
            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=False,
                error=f"Execution exception: {e}",
            )
        finally:
            # Teardown
            try:
                self.teardown()
            except Exception:
                pass  # Log but don't fail on teardown

