"""
MCP server for tmux-repl-mcp.

Exposes three tools:
  - is_repl_ready
  - get_last_command
  - execute_command
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from tmux_repl_mcp.config import load_kinds, load_debugger_patterns
from tmux_repl_mcp.core import (
    capture_pane,
    detect_kind,
    extract_last_command_and_output,
    is_debugger_prompt,
    last_meaningful_line,
    send_keys,
    split_lines,
    wait_and_capture,
)

mcp = FastMCP(
    "tmux-repl-mcp",
    instructions=(
        "Interact with a REPL running inside a tmux pane. "
        "Use is_repl_ready to check the REPL state, "
        "get_last_command to read the last command and its output, and "
        "execute_command to send a command and wait for the result."
    ),
)


# ---------------------------------------------------------------------------
# Tool: is_repl_ready
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Check whether the specified tmux pane is currently showing a REPL "
        "prompt. Returns {\"kind\": \"<kind>\", \"is_ready\": true} if a known prompt is detected, "
        "or {\"kind\": null, \"is_ready\": false} if the pane is busy or shows an unrecognised prompt."
    )
)
def is_repl_ready(
    kind: str,
    pane: str = "0",
    max_lines: int = 200,
) -> dict[str, Any]:
    """
    Parameters
    ----------
    kind:
        The expected REPL kind (e.g. ``"python"``, ``"sbcl"``).
    pane:
        tmux pane identifier (default ``"0"``).
    max_lines:
        How many lines to capture from the pane (default 50).
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    lines = split_lines(capture_pane(pane, max_lines))
    detected_kind = detect_kind(lines, kinds, debugger_patterns)
    return {
        "kind": detected_kind,
        "is_ready": detected_kind == kind,
    }


# ---------------------------------------------------------------------------
# Tool: get_last_command
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Return the last command executed in the REPL and its output. "
        "Looks backwards through up to *max_lines* lines of the pane. "
        "Returns {\"last_command\": ..., \"output\": ...}; both are null "
        "when no complete command block is found or the REPL is busy."
    )
)
def get_last_command(
    kind: str,
    pane: str = "0",
    max_lines: int = 200,
) -> dict[str, Any]:
    """
    Parameters
    ----------
    kind:
        The REPL kind to look for (e.g. ``"python"``, ``"sbcl"``).
    pane:
        tmux pane identifier (default ``"0"``).
    max_lines:
        Maximum lines to capture from the pane (default 200).
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()

    # Check that the REPL is currently idle.
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)
    if current_kind is None:
        return {"last_command": None, "output": None}

    last_command, output = extract_last_command_and_output(lines, kind, kinds, debugger_patterns)
    return {"last_command": last_command, "output": output}


# ---------------------------------------------------------------------------
# Tool: execute_command
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Send a command to a REPL running in a tmux pane and wait until the "
        "REPL is idle again, then return the command and its output. "
        "Returns {\"last_command\": ..., \"output\": ..., \"status\": ...}."
    )
)
def execute_command(
    command: str,
    kind: str,
    pane: str = "0",
    max_lines: int = 200,
    check: float = 2.0,
) -> dict[str, Any]:
    """
    Parameters
    ----------
    command:
        The command text to send to the REPL.
    kind:
        The expected REPL kind (e.g. ``"python"``, ``"sbcl"``).
    pane:
        tmux pane identifier (default ``"0"``).
    max_lines:
        Maximum lines to capture / look back (default 200).
    check:
        Seconds to wait between pane-state polls (default 2.0).
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()

    # --- pre-flight: is the REPL ready? ------------------------------------
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)

    if current_kind is None:
        return {
            "status": "error",
            "reason": "REPL is not ready (no prompt detected).",
            "last_command": None,
            "output": None,
        }

    if current_kind != kind:
        return {
            "status": "error",
            "reason": (
                f"Expected REPL kind {kind!r} but detected {current_kind!r}."
            ),
            "last_command": None,
            "output": None,
        }

    # --- send the command --------------------------------------------------
    send_keys(pane, command)

    # --- wait for command to finish ----------------------------------------
    final_lines = wait_and_capture(pane, kind, kinds, max_lines, check, debugger_patterns)

    # --- check if we ended up in a debugger --------------------------------
    last_line = last_meaningful_line(final_lines)
    if last_line is not None and is_debugger_prompt(last_line, kind, debugger_patterns):
        # Extract the command and error output even though we're in a debugger
        last_command, output = extract_last_command_and_output(final_lines, kind, kinds, debugger_patterns)
        # Return status "ok" - the tool worked correctly, the REPL just entered debugger
        return {
            "status": "ok",
            "last_command": last_command,
            "output": output,
        }

    # --- extract result ----------------------------------------------------
    last_command, output = extract_last_command_and_output(
        final_lines, kind, kinds, debugger_patterns
    )
    return {
        "status": "ok",
        "last_command": last_command,
        "output": output,
    }
