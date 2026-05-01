"""Filesystem helpers used across pipelines."""

from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
