"""
Configuration loading for tmux-repl-mcp.

REPL kinds and their prompt regexes can be extended through the environment
variable ``TMUX_REPL_KINDS``.  The value should be a JSON object mapping
kind names to prompt regular-expression strings, e.g.::

    TMUX_REPL_KINDS='{"myrepl": "^myrepl> "}'

Entries here are *merged* on top of the built-in defaults, so existing kinds
can also be overridden.
"""

from __future__ import annotations

import json
import os

from tmux_repl_mcp.core import DEFAULT_KINDS


def load_kinds() -> dict[str, str]:
    """Return the effective mapping of kind → prompt-regex."""
    kinds = dict(DEFAULT_KINDS)
    extra = os.environ.get("TMUX_REPL_KINDS", "").strip()
    if extra:
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                kinds.update(parsed)
            else:
                import sys
                print(
                    "WARNING: TMUX_REPL_KINDS must be a JSON object; ignoring.",
                    file=sys.stderr,
                )
        except json.JSONDecodeError as exc:
            import sys
            print(
                f"WARNING: Could not parse TMUX_REPL_KINDS ({exc}); ignoring.",
                file=sys.stderr,
            )
    return kinds
