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
    # Goose TUI prompt – the ready-state footer line
    "goose": r"🪿 Enter to send.*",
}

# ---------------------------------------------------------------------------
# Low-level tmux helpers
# ---------------------------------------------------------------------------


def _window_fallback(pane: str) -> Optional[str]:
    """Alternate pane target for servers with base-index 1.

    Window/pane index 0 does not exist when tmux is configured with
    ``base-index 1`` / ``pane-base-index 1``, so retry with index 1.
    """
    if pane == "0":
        return "1"
    if ":0" in pane:
        return pane.replace(":0", ":1", 1)
    if pane.endswith(".0"):
        return pane[:-2] + ".1"
    return None


def _run_tmux(pane: str, args, what: str, **run_kwargs) -> subprocess.CompletedProcess:
    """Run a tmux command targeting *pane*, retrying with the base-index-1
    fallback target if the original target's window/pane cannot be found."""
    result = subprocess.run(
        args(pane),
        capture_output=True,
        text=True,
        **run_kwargs,
    )
    if result.returncode != 0 and "can't find" in result.stderr:
        fallback = _window_fallback(pane)
        if fallback is not None:
            retry = subprocess.run(
                args(fallback),
                capture_output=True,
                text=True,
                **run_kwargs,
            )
            if retry.returncode == 0:
                return retry
    if result.returncode != 0:
        raise RuntimeError(
            f"tmux {what} failed for pane {pane!r}: {result.stderr.strip()}"
        )
    return result


def capture_pane(pane: str, max_lines: int) -> str:
    """Return the last *max_lines* lines of a tmux pane as a raw string."""
    result = _run_tmux(
        pane,
        lambda p: ["tmux", "capture-pane", "-t", p, "-p", "-S", f"-{max_lines}"],
        "capture-pane",
        encoding="utf-8",  # Modern terminals use UTF-8
        errors="replace",  # Replace invalid bytes with � to avoid decode errors
    )
    return result.stdout


def send_keys(pane: str, command: str) -> None:
    """Send *command* followed by Enter to the tmux pane."""
    _run_tmux(
        pane,
        lambda p: ["tmux", "send-keys", "-t", p, command, "Enter"],
        "send-keys",
    )


def send_literal(pane: str, text: str) -> None:
    """Send *text* literally (no Enter, no key-name interpretation)."""
    _run_tmux(
        pane,
        lambda p: ["tmux", "send-keys", "-t", p, "-l", text],
        "send-keys",
    )


def send_backspaces(pane: str, count: int) -> None:
    """Send *count* backspaces to erase previously typed characters."""
    _run_tmux(
        pane,
        lambda p: ["tmux", "send-keys", "-t", p] + ["BSpace"] * count,
        "send-keys",
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


def extract_output_after_command(
    lines: list[str],
    command: str,
    kind: str,
    kinds: dict[str, str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract output using the sent *command* text as the start boundary.

    Used in probed-prompt mode, where prompt themes (e.g. powerlevel10k
    transient prompts) rewrite finished prompt lines so the probed prompt
    character cannot reliably delimit blocks. The command line is instead
    located by its own text; output is everything after it, with trailing
    prompt/empty lines stripped.
    """
    # Long commands wrap across pane lines — match on a prefix.
    needle = command[:60].strip()
    start_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if needle and needle in line:
            start_idx = i
    if start_idx is None:
        return None, None

    tail = lines[start_idx + 1 :]
    # Strip trailing empty lines and the fresh prompt line(s).
    while tail and (
        not tail[-1].strip() or is_prompt_line(tail[-1], kind, kinds)
    ):
        tail.pop()
    return command, "\n".join(tail)


# ---------------------------------------------------------------------------
# Probe-based prompt discovery
# ---------------------------------------------------------------------------

PROBE_SENTINEL = "TMUXREPLPROBE"


def probe_prompt_pattern(
    pane: str,
    max_lines: int = 200,
    settle: float = 0.3,
) -> Optional[str]:
    """
    Discover a prompt pattern by typing a sentinel string into the pane.

    If the pane is showing a prompt, the sentinel lands right after it. We
    capture the pane, locate the sentinel, take up to the 10 characters
    preceding it, strip trailing whitespace, and use the last remaining
    non-whitespace character as the prompt marker. The sentinel is erased
    with backspaces before returning.

    Returns a prompt regex string, or None if the sentinel never appeared or
    nothing precedes it (a bare/empty prompt column).
    """
    send_literal(pane, PROBE_SENTINEL)
    try:
        # Poll: over SSH the remote echo can take a while to reach the pane.
        deadline = time.monotonic() + max(settle, 2.0)
        while True:
            lines = split_lines(capture_pane(pane, max_lines))
            for line in reversed(lines):
                idx = line.rfind(PROBE_SENTINEL)
                if idx == -1:
                    continue
                before = line[max(0, idx - 10):idx].rstrip()
                if not before:
                    return None
                return re.escape(before[-1]) + " *"
            if time.monotonic() >= deadline:
                return None
            time.sleep(settle)
    finally:
        send_backspaces(pane, len(PROBE_SENTINEL))


# ---------------------------------------------------------------------------
# execute_command wait loop
# ---------------------------------------------------------------------------


def wait_and_capture(
    pane: str,
    kind: str,
    kinds: dict[str, str],
    max_lines: int,
    check: float,
    command: Optional[str] = None,
    probed: bool = False,
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

        # Probed patterns come from themed prompts (e.g. powerlevel10k) whose
        # idle line carries decorations and never fullmatches. There, treat a
        # prompt line as "idle again" once the sent command has been echoed
        # somewhere above it (guards against capturing before the terminal
        # has even echoed the command) and is gone from the prompt line.
        if probed and is_prompt_line(last_line, kind, kinds):
            needle = (command or "")[:60].strip()
            if not needle or (
                needle not in last_line
                and any(needle in line for line in current)
            ):
                return current

        # Only sleep if we haven't found the prompt yet
        time.sleep(check)
