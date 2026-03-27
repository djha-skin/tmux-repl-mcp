"""
Core logic for tmux-repl-mcp: pane capture, prompt detection,
command-output extraction, and the execute_command wait loop.
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Built-in REPL kinds with their prompt regexes.
# Additional kinds can be injected via TMUX_REPL_KINDS environment variable
# (see config.py).
# ---------------------------------------------------------------------------

DEFAULT_KINDS: dict[str, str] = {
    "python": r"^>>> ",
    "ipython": r"^In \[\d+\]: ",
    "bash": r"[\$\#]\s*$",
    "zsh": r"[\$\#%]\s*$",
    "sh": r"[\$\#]\s*$",
    # "lisp" is the generic catch-all for Common Lisp REPLs (SBCL, CCL, etc.).
    # Prompt lines always start with one of:
    #   "* "   – top-level SBCL/generic CL prompt (followed by command or empty)
    #   "N] "  – SBCL/CCL debugger prompt, e.g. "1] "
    #   "Name> " – custom package / slynk prompt, e.g. "slynk> "
    "lisp": r"^\* |^\d+\] |^[A-Za-z0-9.]+> ",
    "node": r"^> ",
    "irb": r"^irb\(.*\):\d+:\d+> $",
    "iex": r"^iex\(\d+\)> $",
}


# ---------------------------------------------------------------------------
# Low-level tmux helpers
# ---------------------------------------------------------------------------


def capture_pane(pane: str, max_lines: int) -> str:
    """Return the last *max_lines* lines of a tmux pane as a raw string."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", pane, "-p", "-S", f"-{max_lines}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tmux capture-pane failed for pane {pane!r}: {result.stderr.strip()}"
        )
    return result.stdout


def send_keys(pane: str, command: str) -> None:
    """Send *command* followed by Enter to the tmux pane."""
    result = subprocess.run(
        ["tmux", "send-keys", "-t", pane, command, "Enter"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tmux send-keys failed for pane {pane!r}: {result.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Line / prompt helpers
# ---------------------------------------------------------------------------


def split_lines(text: str) -> list[str]:
    """Split *text* on newlines."""
    return text.split("\n")


def is_prompt_line(line: str, kind: str, kinds: dict[str, str]) -> bool:
    """Return True if *line* matches the prompt regex for *kind*."""
    pattern = kinds.get(kind)
    if pattern is None:
        return False
    return bool(re.search(pattern, line))


def last_meaningful_line(lines: list[str]) -> Optional[str]:
    """Return the last non-empty line, or None."""
    for line in reversed(lines):
        if line.strip():
            return line
    return None


def last_prompt_index(
    lines: list[str], kind: str, kinds: dict[str, str]
) -> Optional[int]:
    """Return the index of the *last* prompt line, or None."""
    result: Optional[int] = None
    for i, line in enumerate(lines):
        if is_prompt_line(line, kind, kinds):
            result = i
    return result


def second_to_last_prompt_index(
    lines: list[str], kind: str, kinds: dict[str, str]
) -> Optional[int]:
    """Return the index of the second-to-last prompt line, or None."""
    end_idx = last_prompt_index(lines, kind, kinds)
    if end_idx is None:
        return None
    result: Optional[int] = None
    for i, line in enumerate(lines):
        if i >= end_idx:
            break
        if is_prompt_line(line, kind, kinds):
            result = i
    return result


def prompt_block_p(lines: list[str], kind: str, kinds: dict[str, str]) -> bool:
    """
    Return True if *lines* ends with a prompt line **and** contains at least
    one prior prompt line (i.e. a complete command→output→prompt block exists).
    """
    last = last_meaningful_line(lines)
    if last is None:
        return False
    if not is_prompt_line(last, kind, kinds):
        return False
    return second_to_last_prompt_index(lines, kind, kinds) is not None


# ---------------------------------------------------------------------------
# Higher-level helpers used by MCP tools
# ---------------------------------------------------------------------------


def detect_kind(
    lines: list[str], kinds: dict[str, str]
) -> Optional[str]:
    """
    Return the first *kind* whose prompt regex matches the last meaningful
    line of *lines*, or None.
    """
    last = last_meaningful_line(lines)
    if last is None:
        return None
    for kind, pattern in kinds.items():
        if re.search(pattern, last):
            return kind
    return None


def extract_last_command_and_output(
    lines: list[str], kind: str, kinds: dict[str, str]
) -> tuple[Optional[str], Optional[str]]:
    """
    Return ``(last_command, output)`` parsed from *lines*.

    *last_command* is the text of the second-to-last prompt line **without**
    the prompt prefix.  *output* is everything between that prompt line and
    the final prompt line.

    Returns ``(None, None)`` if a complete block cannot be found.
    """
    end_idx = last_prompt_index(lines, kind, kinds)
    start_idx = second_to_last_prompt_index(lines, kind, kinds)
    if start_idx is None or end_idx is None:
        return None, None

    pattern = kinds[kind]
    prompt_line = lines[start_idx]
    # Strip the prompt prefix to get just the command text.
    last_command = re.sub(pattern, "", prompt_line, count=1).strip()

    output_lines = lines[start_idx + 1 : end_idx]
    output = "\n".join(output_lines)

    return last_command, output


# ---------------------------------------------------------------------------
# execute_command wait loop
# ---------------------------------------------------------------------------


def wait_and_capture(
    pane: str,
    kind: str,
    kinds: dict[str, str],
    max_lines: int,
    check: float,
) -> list[str]:
    """
    Wait until a complete, *stable* prompt block appears in *pane*.

    Phase 1 – start-state loop:
        Wait until the pane content changes from the sentinel captured just
        after send-keys (meaning the REPL has started processing the command).

    Phase 2 – end-state loop:
        Wait until the last non-empty line is a prompt for *kind* (the REPL
        is idle again).

    Phase 3 – stability check:
        Wait one more *check* cycle and confirm the pane hasn't changed.

    Returns the final list of lines.
    """
    # Capture initial sentinel *after* send-keys so the new command line is
    # already visible.
    sentinel = split_lines(capture_pane(pane, max_lines))

    # Phase 1: wait for pane to change.
    while True:
        time.sleep(check)
        current = split_lines(capture_pane(pane, max_lines))
        if current != sentinel:
            break

    # Phase 2: wait for REPL prompt to reappear.
    while True:
        current = split_lines(capture_pane(pane, max_lines))
        last = last_meaningful_line(current)
        if last is not None and is_prompt_line(last, kind, kinds):
            break
        time.sleep(check)

    # Phase 3: stability – wait one more interval and confirm no change.
    time.sleep(check)
    stable = split_lines(capture_pane(pane, max_lines))
    # If it changed again (e.g. another prompt appeared), that's still fine;
    # just use whatever we have now.
    return stable
