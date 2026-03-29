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

# Patterns for when the REPL is READY to accept commands
DEFAULT_PROMPT_PATTERNS: dict[str, str] = {
    "python": r"^>>> ",
    "ipython": r"^In \\d+\: ",
    "bash": r"^[^$#]+[$#] *",
    "sh": r"^[^$#]+[$#] *",
    "zsh": r"^[^$+][$#] *",
    # Lisp ready prompts: top-level REPL only, INCLUDING debugger prompts
    # "*" - bare idle prompt (nothing after it)
    # "* " - top-level prompt with or without command
    # "Name> " - custom package / slynk prompt, e.g. "slynk> " or "CL-USER> "
    # "?" - CCL
    # TO BE PERFECTLY CLEAR, THE DEBUGGER STATE PROMPT IS *DEFINITELY* A READY
    # PROMPT. The user can be in the debugger and still type commands, so the
    # debugger prompt is a valid command boundary and must be treated as such.
    "lisp": r"^\? |^\* |^\*$|[A-Za-z0-9.-]+> |^ *[0-9]+\] ?",
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
        encoding="ISO-8859-1", # This is just "normal" bash encoding
        errors="replace", # Replace invalid bytes with � to avoid decode errors
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


def is_empty_prompt(line: str, kind: str, kinds: dict[str, list[str]]) -> bool:
    """Return True if *line* matches the prompt regex for *kind*."""
    pattern = kinds.get(kind)
    if pattern is None:
        return False
    return bool(re.fullmatch(pattern, line))

def is_prompt_line(line: str, kind: str, kinds: dict[str, list[str]]) -> bool:
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
    lines: list[str],
    kind: str,
    kinds: dict[str, str],
) -> Optional[int]:
    """Return the index of the *last* prompt line (including debugger prompts),
    or None."""
    result: Optional[int] = None
    for i, line in enumerate(lines):
        if is_prompt_line(line, kind, kinds):
            result = i
    return result


def second_to_last_prompt_index(
    lines: list[str],
    kind: str,
    kinds: dict[str, str],
) -> Optional[int]:
    """Return the index of the second-to-last prompt line (ready only), or None.

    The "start" boundary of a command block is always a prompt (remember,
    debugger prompts are normal prompts).
    """
    end_idx = last_prompt_index(lines, kind, kinds)
    if end_idx is None:
        return None
    result: Optional[int] = None
    for i, line in enumerate(lines):
        if i >= end_idx:
            break
        # Only ready prompts can be the start of a command block
        # Debugger prompts are valid ready prompts and thus valid boundaries.
        if is_prompt_line(line, kind, kinds):
            result = i
    return result


def prompt_block_p(
    lines: list[str],
    kind: str,
    kinds: dict[str, str]
) -> bool:
    """
    Return True if *lines* ends with a prompt line (standard or debugger)
    **and** contains at least one prior *ready* prompt line (i.e. a complete
    command→output→prompt block exists).
    """
    last = last_meaningful_line(lines)
    if last is None:
        return False
    is_end = is_prompt_line(last, kind, kinds)
    if not is_end:
        return False
    return second_to_last_prompt_index(lines, kind, kinds) is not None


# ---------------------------------------------------------------------------
# Higher-level helpers used by MCP tools
# ---------------------------------------------------------------------------


def detect_kind(
    lines: list[str], kinds: dict[str, str]
) -> Optional[str]:
    """
    Return the *kind* whose prompt regex (ready or debugger) matches the last
    meaningful line of *lines*, or None if no known prompt is found.

    The debugger is a valid REPL state — if a debugger prompt is detected for
    a kind, that kind is returned just like a normal ready prompt.
    """
    last = last_meaningful_line(lines)
    if last is None:
        return None

    # Check ready patterns first
    for kind, pattern in kinds.items():
        if re.search(pattern, last):
            return kind

    return None


def extract_last_command_and_output(
    lines: list[str],
    kind: str,
    kinds: dict[str, str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Return ``(last_command, output)`` parsed from *lines*.

    *last_command* is the text of the second-to-last prompt line **without**
    the prompt prefix.  *output* is everything between that prompt line and
    the final prompt line (which may be a debugger prompt).

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
    Wait until the REPL is idle again.

    After send_keys has been called, this function polls the pane until the
    very last line matches the REPL prompt pattern for *kind*. This indicates
    the REPL has finished processing the command and is ready for input.

    If a debugger prompt is detected, returns the current lines immediately
    (caller can then decide how to handle the error state).

    Returns the final list of lines.
    """
    while True:
        current = split_lines(capture_pane(pane, max_lines))

        if len(current) == 0:
            time.sleep(check)
            continue

        last_line = last_meaningful_line(current)

        if last_line is None:
            time.sleep(check)
            continue

        # Check if we're back at a ready prompt
        if is_empty_prompt(last_line, kind, kinds):
            return current

        # Only sleep if we haven't found the prompt yet
        time.sleep(check)
