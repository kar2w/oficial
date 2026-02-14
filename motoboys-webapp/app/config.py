"""Backward-compatible config module.

Prefer importing `settings` from `app.settings`.
"""

from app.settings import settings

__all__ = ["settings"]
