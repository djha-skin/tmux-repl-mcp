#!/usr/bin/env python3
"""Debug send_keys - check if command actually appears in pane."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

import time
from tmux_repl_mcp.core import (
    capture_pane,
    split_lines,
    send_keys,
)

def debug_send_keys(pane: str, command: str, max_lines: int = 500):
    """Check if send_keys actually puts the command in the pane."""

    print("=" * 70)
    print(f"DEBUG send_keys: pane={pane}, command={command!r}")
    print("=" * 70)
    print()

    # Capture before
    print("BEFORE send_keys (last 10 lines):")
    before = split_lines(capture_pane(pane, max_lines))
    for i, line in enumerate(before[-10:], start=len(before)-10):
        print(f"  {i}: {line!r}")
    print()

    # Send the command
    print(f"Sending: {command!r}")
    send_keys(pane, command)
    print("send_keys returned")
    print()

    # Wait a tiny bit
    time.sleep(0.2)

    # Capture after
    print("AFTER send_keys (last 15 lines):")
    after = split_lines(capture_pane(pane, max_lines))
    for i, line in enumerate(after[-15:], start=len(after)-15):
        print(f"  {i}: {line!r}")
    print()

    # Check if command appears anywhere
    print(f"Searching for {command!r} in pane content:")
    for i, line in enumerate(after):
        if command in line:
            print(f"  Found at line {i}: {line!r}")

    print()
    print(f"Before had {len(before)} lines, after has {len(after)} lines")
    print(f"Lines are identical: {before == after}")

if __name__ == "__main__":
    debug_send_keys("0", "(+ 1 2)", 500)
