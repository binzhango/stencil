"""Package version."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("office-stencil")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
