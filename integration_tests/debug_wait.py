#!/usr/bin/env python3
"""Debug wait_and_capture to see what's happening."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

import time
from tmux_repl_mcp.config import load_kinds
from tmux_repl_mcp.core import (
    capture_pane,
    split_lines,
    last_meaningful_line,
    is_prompt_line,
    detect_kind,
)

def debug_wait_and_capture(pane: str, kind: str, max_lines: int = 200, check: float = 0.5, max_iterations: int = 20):
    """Debug version of wait_and_capture with iteration limit."""
    kinds = load_kinds()

    print(f"Starting wait_and_capture debug for pane={pane}, kind={kind}")
    print(f"Pattern for {kind}: {kinds[kind]!r}")
    print()

    # Capture initial sentinel
    sentinel = split_lines(capture_pane(pane, max_lines))
    print(f"Phase 0 - Initial sentinel captured: {len(sentinel)} lines")
    print(f"  Last meaningful line: {last_meaningful_line(sentinel)!r}")
    print(f"  Is it a prompt? {is_prompt_line(last_meaningful_line(sentinel), kind, kinds)}")
    print()

    # Phase 1: wait for pane to change
    print("Phase 1 - Waiting for pane to change...")
    iteration = 0
    while iteration < max_iterations:
        time.sleep(check)
        current = split_lines(capture_pane(pane, max_lines))
        last = last_meaningful_line(current)
        print(f"  Iter {iteration}: Last line = {last!r}, Changed = {current != sentinel}")
        if current != sentinel:
            print("  Pane changed, moving to Phase 2")
            break
        iteration += 1
    else:
        print("  TIMEOUT: Pane never changed")
        return

    print()

    # Phase 2: wait for REPL prompt to reappear
    print("Phase 2 - Waiting for REPL prompt...")
    iteration = 0
    while iteration < max_iterations:
        current = split_lines(capture_pane(pane, max_lines))
        last = last_meaningful_line(current)
        is_prompt = last is not None and is_prompt_line(last, kind, kinds)
        detected = detect_kind(current, kinds)

        print(f"  Iter {iteration}: Last line = {last!r}")
        print(f"    is_prompt_line({kind}) = {is_prompt}")
        print(f"    detect_kind = {detected!r}")

        if is_prompt:
            print("  Prompt detected!")
            break
        time.sleep(check)
        iteration += 1
    else:
        print("  TIMEOUT: Prompt never appeared")
        return

    print()

    # Phase 3: stability check
    print("Phase 3 - Stability check...")
    time.sleep(check)
    stable = split_lines(capture_pane(pane, max_lines))
    last = last_meaningful_line(stable)
    print(f"  Final last line: {last!r}")
    print(f"  Is prompt: {is_prompt_line(last, kind, kinds)}")

    return stable

if __name__ == "__main__":
    debug_wait_and_capture("0", "lisp", 200, 0.5, 10)
