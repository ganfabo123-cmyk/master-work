"""Canonical strategy-based clustering entry point.

The implementation is shared with ``error_clustering_experiment`` for
backward compatibility. New callers should use this module: error codes are
one strategy, alongside stack sites, test cases, configuration changes, and
dependency changes.
"""

from error_clustering_experiment import *  # noqa: F401,F403
from error_clustering_experiment import main as _implementation_main


def main() -> None:
    """Run the canonical strategy-clustering CLI."""
    _implementation_main()


if __name__ == "__main__":
    main()
