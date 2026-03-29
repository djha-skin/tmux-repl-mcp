#!/usr/bin/env python3
"""Debug execute_command flow - send a command and wait."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

import time
from tmux_repl_mcp.config import load_kinds, load_debugger_patterns
from tmux_repl_mcp.core import (
    capture_pane,
    split_lines,
    last_meaningful_line,
    is_prompt_line,
    is_debugger_prompt,
    detect_kind,
    send_keys,
)

def debug_execute_flow(pane: str, kind: str, command: str, max_lines: int = 200, check: float = 0.5, max_iterations: int = 30):
    """Debug the full execute_command flow."""
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    
    print("=" * 70)
    print(f"DEBUG execute_command: pane={pane}, kind={kind}, command={command!r}")
    print("=" * 70)
    print()
    
    # Pre-flight: check if REPL is ready
    print("Pre-flight check...")
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)
    last = last_meaningful_line(lines)
    
    print(f"  Detected kind: {current_kind!r}")
    print(f"  Last line: {last!r}")
    print(f"  Is prompt: {is_prompt_line(last, kind, kinds) if last else False}")
    
    if current_kind is None:
        print("  ERROR: No prompt detected!")
        return
    
    if current_kind != kind:
        print(f"  ERROR: Expected {kind!r} but got {current_kind!r}")
        return
    
    print("  REPL is ready!")
    print()
    
    # Send the command
    print(f"Sending command: {command!r}")
    send_keys(pane, command)
    print("Command sent!")
    print()
    
    # Capture initial state after send-keys
    print("Phase 0 - Initial state after send-keys:")
    sentinel = split_lines(capture_pane(pane, max_lines))
    last = last_meaningful_line(sentinel)
    print(f"  Last line: {last!r}")
    print(f"  Is prompt: {is_prompt_line(last, kind, kinds)}")
    print()
    
    # Phase 1: wait for pane to change
    print("Phase 1 - Waiting for pane to change...")
    iteration = 0
    while iteration < max_iterations:
        time.sleep(check)
        current = split_lines(capture_pane(pane, max_lines))
        last = last_meaningful_line(current)
        changed = current != sentinel
        
        print(f"  Iter {iteration:2d}: Last line = {last!r:30s} Changed = {changed}")
        
        if changed:
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
        is_debug = last is not None and is_debugger_prompt(last, kind, debugger_patterns)
        detected = detect_kind(current, kinds, debugger_patterns)
        
        print(f"  Iter {iteration:2d}: Last line = {last!r:30s} is_prompt={is_prompt} is_debug={is_debug} detected={detected!r}")
        
        if is_prompt:
            print("  Prompt detected!")
            break
        if is_debug:
            print("  DEBUGGER detected!")
            break
        time.sleep(check)
        iteration += 1
    else:
        print("  TIMEOUT: Prompt never appeared")
        # Show final state
        final = split_lines(capture_pane(pane, max_lines))
        print("\n  Final pane content (last 10 lines):")
        for i, line in enumerate(final[-10:], start=len(final)-10):
            print(f"    {i}: {line!r}")
        return
    
    print()
    
    # Phase 3: stability check
    print("Phase 3 - Stability check...")
    time.sleep(check)
    stable = split_lines(capture_pane(pane, max_lines))
    last = last_meaningful_line(stable)
    print(f"  Final last line: {last!r}")
    print(f"  Is prompt: {is_prompt_line(last, kind, kinds)}")
    
    print()
    print("SUCCESS!")
    return stable

if __name__ == "__main__":
    debug_execute_flow("0", "lisp", "(+ 1 2)", 200, 0.5, 20)
