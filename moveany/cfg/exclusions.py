"""Exclusion sets used by MoveAny.

MoveAny hides copies of an existing exclusion catalog so the CLI (`config.py`)
and any future GUI can share one definition of what a "build artifact /
ignorable directory" means.
"""

# Default names excluded from copy/move. These are reproducible or
# build-on-demand artifacts and should not be transferred. Users can add or
# remove via the exclude CLI options.
# NOTE: ".git" is intentionally NOT included - repository history is valuable
# data and must be copied.
DEFAULT_EXCLUDE_DIRS = (
    "node_modules",
    "_build",
    "releases",
)

# Candidate directory names that look like build artifacts but are kept by
# default. Shown as suggestions in `exclude list --available`.
KNOWN_BUILD_ARTIFACTS = (
    "node_modules",
    "_build",
    "build",
    "dist",
    "out",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "releases",
    "bin",
    "obj",
    ".vs",
    "site-packages",
)


def effective_exclusions(state=None):
    """Combine default exclusions with user add/remove overrides.

    `state` is a dict with sets 'added' and 'removed' (or None for empty).
    Returns a sorted tuple of the effective exclusion directory names.
    """
    added = set()
    removed = set()
    if state:
        added = set(state.get("added", ()))
        removed = set(state.get("removed", ()))
    return tuple(sorted((set(DEFAULT_EXCLUDE_DIRS) | added) - removed))
