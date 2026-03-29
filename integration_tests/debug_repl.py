#!/usr/bin/env python3
"""Debug script to capture pane content and test detect_kind."""

import subprocess
import re
from typing import Optional

# Copy of DEFAULT_KINDS from core.py
DEFAULT_KINDS: dict[str, str] = {
    "python": r"^>>> ",
    "ipython": r"^In \[\d+\]: ",
    "bash": r"[\$\#]\s*$",
    "zsh": r"[\$\#%]\s*$",
    "sh": r"[\$\#]\s*$",
    "lisp": r"^\*(?:\s.*)?$|^\d+\] |^[A-Za-z0-9.]+> ",
    "node": r"^> ",
    "irb": r"^irb\(.*\):\d+:\d+> $",
    "iex": r"^iex\(\d+\)> $",
}

def capture_pane(pane: str, max_lines: int) -> str:
    """Return the last *max_lines* lines of a tmux pane as a raw string."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", pane, "-p", "-S", f"-{max_lines}"],
        capture_output=True,
        text=True,
        encoding="ISO-8859-1",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tmux capture-pane failed for pane {pane!r}: {result.stderr.strip()}"
        )
    return result.stdout

def split_lines(text: str) -> list[str]:
    """Split *text* on newlines."""
    return text.split("\n")

def last_meaningful_line(lines: list[str]) -> Optional[str]:
    """Return the last non-empty line, or None."""
    for line in reversed(lines):
        if line.strip():
            return line
    return None

def detect_kind(lines: list[str], kinds: dict[str, str]) -> Optional[str]:
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

def main():
    pane = "0"
    max_lines = 50
    
    print(f"=== Capturing pane {pane} (last {max_lines} lines) ===\n")
    
    raw_content = capture_pane(pane, max_lines)
    lines = split_lines(raw_content)
    
    print(f"Raw pane content ({len(lines)} lines):")
    print("=" * 60)
    for i, line in enumerate(lines):
        # Show line with visible special chars
        display_line = repr(line)
        print(f"{i:3d}: {display_line}")
    print("=" * 60)
    
    last = last_meaningful_line(lines)
    print(f"\nLast meaningful line: {repr(last)}")
    
    print("\n=== Testing each regex pattern against last line ===")
    for kind, pattern in DEFAULT_KINDS.items():
        match = re.search(pattern, last) if last else None
        print(f"  {kind:12s}: pattern={pattern!r:40s} -> {'MATCH' if match else 'no match'}")
    
    detected = detect_kind(lines, DEFAULT_KINDS)
    print(f"\n=== detect_kind result: {detected!r} ===")
    
    # Also show what tmux sees as the pane info
    print("\n=== tmux list-panes info ===")
    result = subprocess.run(
        ["tmux", "list-panes", "-t", pane, "-a"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)

if __name__ == "__main__":
    main()
