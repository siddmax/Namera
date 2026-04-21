"""Namera - Check name availability across domains, trademarks, and more."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

try:
    __version__ = _dist_version("namera")
except PackageNotFoundError:
    try:
        from ._version import version as __version__
    except ImportError:
        __version__ = "0.0.0"
