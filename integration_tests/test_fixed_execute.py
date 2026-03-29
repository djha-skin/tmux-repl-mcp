#!/usr/bin/env python3
"""Test the FIXED wait_and_capture and execute_command flow."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

from tmux_repl_mcp.config import load_kinds, load_debugger_patterns
from tmux_repl_mcp.core import (
    capture_pane,
    split_lines,
    last_meaningful_line,
    is_prompt_line,
    is_debugger_prompt,
    detect_kind,
    send_keys,
    wait_and_capture,
    extract_last_command_and_output,
)

def simulate_execute_command(command: str, kind: str, pane: str = "0", max_lines: int = 200, check: float = 0.5):
    """Simulate the execute_command MCP tool with the FIXED code."""
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    
    print("=" * 70)
    print(f"execute_command(command={command!r}, kind={kind!r}, pane={pane!r})")
    print("=" * 70)
    
    # Pre-flight check
    print("\nPre-flight check...")
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)
    last = last_meaningful_line(lines)
    
    print(f"  Detected kind: {current_kind!r}")
    print(f"  Last meaningful line: {last!r}")
    
    if current_kind is None:
        return {"status": "error", "reason": "No prompt detected"}
    
    if current_kind != kind:
        return {"status": "error", "reason": f"Expected {kind!r} but got {current_kind!r}"}
    
    print("  REPL is ready!")
    
    # Send the command
    print(f"\nSending command: {command!r}")
    send_keys(pane, command)
    
    # Wait for completion
    print("Waiting for REPL to be idle...")
    final_lines = wait_and_capture(pane, kind, kinds, max_lines, check, debugger_patterns)
    
    print(f"Captured {len(final_lines)} lines")
    print(f"Last line: {final_lines[-1]!r}")
    
    # Check if we're in debugger
    last_line = last_meaningful_line(final_lines)
    if last_line is not None and is_debugger_prompt(last_line, kind, debugger_patterns):
        print("\nDEBUGGER DETECTED!")
        last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
        print(f"Extracted command: {last_command!r}")
        print(f"Extracted output: {output!r}")
        return {
            "status": "debugger",
            "reason": "REPL entered debugger (error occurred).",
            "last_command": last_command,
            "output": output,
        }
    
    # Extract result
    last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
    
    print(f"\nExtracted command: {last_command!r}")
    print(f"Extracted output: {output!r}")
    
    return {
        "status": "ok",
        "last_command": last_command,
        "output": output,
    }

if __name__ == "__main__":
    result = simulate_execute_command("(+ 1 2)", "lisp", "0", 200, 0.5)
    print("\n" + "=" * 70)
    print(f"FINAL RESULT: {result}")
    print("=" * 70)
