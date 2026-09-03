"""Persistent state for exclusions.

User overrides to the default exclusion set are stored in a small JSON file.
  - "added":   names the user explicitly added to the exclusion set.
  - "removed": names the user explicitly removed from the default set.
"""

import json
import os

STATE_FILENAME = ".moveany/state.json"


def _default_state_path():
    home = os.path.expanduser("~")
    return os.path.join(home, ".moveany", "exclusions.json")


def load_state(path=None):
    """Return dict with keys 'added' and 'removed' (each a set)."""
    path = path or _default_state_path()
    if not os.path.isfile(path):
        return {"added": set(), "removed": set()}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {
            "added": set(data.get("added", [])),
            "removed": set(data.get("removed", [])),
        }
    except (OSError, ValueError):
        return {"added": set(), "removed": set()}


def save_state(state, path=None):
    """Persist {added, removed} sets to the state file."""
    path = path or _default_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "added": sorted(state["added"]),
        "removed": sorted(state["removed"]),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
