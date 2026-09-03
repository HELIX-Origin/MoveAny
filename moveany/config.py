"""CLI-level configuration for MoveAny.

Everything here can be overridden at runtime via the CLI. Any config that
benefits from dedicated logic lives in the `config` package's submodules and
is imported here.
"""

from moveany.cfg.exclusions import DEFAULT_EXCLUDE_DIRS

# Number of bytes to compare at a time when verifying with a content hash.
HASH_CHUNK = 1 << 20  # 1 MiB

# Default log directory name (relative to the current working directory or an
# absolute path passed with --log-dir).
from moveany.cfg.defaults import DEFAULT_LOG_DIR

# Per-file progress logging intervals for long scans.
SCAN_PROGRESS_EVERY = 1000
COMPARE_PROGRESS_EVERY = 500
COPY_PROGRESS_EVERY = 250

__all__ = ["DEFAULT_EXCLUDE_DIRS", "HASH_CHUNK", "DEFAULT_LOG_DIR"]
