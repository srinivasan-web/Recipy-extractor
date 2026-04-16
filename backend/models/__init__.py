try:
    from .recipe import Recipe
except ImportError:  # pragma: no cover - supports running from backend/ as top-level package
    from recipe import Recipe

__all__ = ["Recipe"]
