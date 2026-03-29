#!/usr/bin/env python3
"""Test the actual is_repl_ready tool behavior."""

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
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", pane, "-p", "-S", f"-{max_lines}"],
        capture_output=True,
        text=True,
        encoding="ISO-8859-1",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"tmux capture-pane failed: {result.stderr.strip()}")
    return result.stdout

def split_lines_local(text: str) -> list[str]:
    return text.split("\n")

def last_meaningful_line(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        if line.strip():
            return line
    return None

def detect_kind_local(lines: list[str], kinds: dict[str, str]) -> Optional[str]:
    last = last_meaningful_line(lines)
    if last is None:
        return None
    for kind, pattern in kinds.items():
        if re.search(pattern, last):
            return kind
    return None

def simulate_is_repl_ready_with_params(kind: str, pane: str, max_lines: int) -> dict:
    """
    This simulates the ACTUAL is_repl_ready tool from server.py:
    
    def is_repl_ready(
        kind: str,  # <-- This is REQUIRED!
        pane: str = "0",
        max_lines: int = 200,
    ) -> dict[str, Any]:
        kinds = load_kinds()
        lines = split_lines(capture_pane(pane, max_lines))
        detected_kind = detect_kind(lines, kinds)
        return {
            "kind": detected_kind,
            "is_ready": detected_kind == kind,
        }
    """
    lines = split_lines_local(capture_pane_local(pane, max_lines))
    detected_kind = detect_kind_local(lines, DEFAULT_KINDS)
    
    # The key insight: is_ready is True ONLY if detected_kind == the requested kind
    return {
        "kind": detected_kind,
        "is_ready": detected_kind == kind,
    }

def main():
    pane = "0"
    
    print("=" * 70)
    print("Simulating is_repl_ready with different 'kind' parameters")
    print("=" * 70)
    
    # What if the tool was called WITHOUT specifying kind='lisp'?
    # Or with a different kind?
    
    test_kinds = [None, "lisp", "python", "bash", ""]
    
    for test_kind in test_kinds:
        print(f"\n--- is_repl_ready(kind={test_kind!r}, pane='0', max_lines=200) ---")
        if test_kind is None:
            print("  ERROR: 'kind' is a required parameter - tool would fail!")
        else:
            result = simulate_is_repl_ready_with_params(test_kind, pane, 200)
            print(f"  Result: {result}")
    
    print("\n" + "=" * 70)
    print("Key Finding:")
    print("=" * 70)
    print("The is_repl_ready tool returns {'kind': null, 'is_ready': false} when:")
    print("  1. No prompt is detected (detected_kind is None), OR")
    print("  2. The detected kind does NOT match the requested 'kind' parameter")
    print()
    print("If you called is_repl_ready without specifying kind='lisp',")
    print("or with a different kind, it would return is_ready: false even though")
    print("a Lisp REPL is present!")

if __name__ == "__main__":
    main()
