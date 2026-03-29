#!/usr/bin/env python3
"""Debug script to capture pane content and test detect_kind with different parameters."""

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

def capture_pane_local(pane: str, max_lines: int) -> str:
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

def split_lines_local(text: str) -> list[str]:
    """Split *text* on newlines."""
    return text.split("\n")

def last_meaningful_line(lines: list[str]) -> Optional[str]:
    """Return the last non-empty line, or None."""
    for line in reversed(lines):
        if line.strip():
            return line
    return None

def detect_kind_local(lines: list[str], kinds: dict[str, str]) -> Optional[str]:
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

def is_repl_ready_simulation(kind: str, pane: str, max_lines: int) -> dict:
    """Simulate what is_repl_ready does."""
    lines = split_lines_local(capture_pane_local(pane, max_lines))
    detected_kind = detect_kind_local(lines, DEFAULT_KINDS)
    return {
        "kind": detected_kind,
        "is_ready": detected_kind == kind,
    }

def main():
    pane = "0"
    
    print("=" * 70)
    print("DEBUG: Testing is_repl_ready simulation")
    print("=" * 70)
    
    # Test with different max_lines values
    for max_lines in [50, 100, 200, 500]:
        print(f"\n--- Testing with max_lines={max_lines} ---")
        raw_content = capture_pane_local(pane, max_lines)
        lines = split_lines_local(raw_content)
        
        last = last_meaningful_line(lines)
        print(f"Total lines captured: {len(lines)}")
        print(f"Last meaningful line: {repr(last)}")
        
        detected = detect_kind_local(lines, DEFAULT_KINDS)
        print(f"Detected kind: {detected!r}")
        
        # Test for lisp specifically
        result = is_repl_ready_simulation("lisp", pane, max_lines)
        print(f"is_repl_ready(kind='lisp'): {result}")
        
        # Show last 5 lines for context
        print("\nLast 5 lines of pane content:")
        for i, line in enumerate(lines[-5:], start=len(lines)-5):
            print(f"  {i}: {repr(line)}")
    
    # Also check what the actual tool might be seeing
    print("\n" + "=" * 70)
    print("Checking if there's a mismatch in the tool definition")
    print("=" * 70)
    
    # Look at the actual function signature
    import sys
    sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')
    
    from tmux_repl_mcp.config import load_kinds
    from tmux_repl_mcp.core import detect_kind, split_lines, capture_pane
    
    kinds = load_kinds()
    print(f"\nLoaded kinds from config: {list(kinds.keys())}")
    
    # Test with the actual loaded kinds
    for max_lines in [50, 200]:
        lines = split_lines(capture_pane(pane, max_lines))
        last = last_meaningful_line(lines)
        detected = detect_kind(lines, kinds)
        print(f"\nWith actual loaded kinds (max_lines={max_lines}):")
        print(f"  Last line: {repr(last)}")
        print(f"  Detected: {detected!r}")

if __name__ == "__main__":
    main()
