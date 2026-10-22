try:
    from .tool import register
except ImportError:  # pytest collecting from the repo root imports this file outside its package
    from tool import register  # noqa: F401

__all__ = ["register"]
