"""Command-line interface for QMatSuite."""


def __getattr__(name: str):
    """Lazy import to avoid circular import issues with -m execution."""
    if name == "app":
        from .main import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
