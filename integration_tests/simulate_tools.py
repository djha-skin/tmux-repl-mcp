#!/usr/bin/env python3
"""
Simulate the MCP tool calls by directly importing and calling the module functions.
This bypasses the need to build the wheel.
"""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

from tmux_repl_mcp.config import load_kinds, load_debugger_patterns
from tmux_repl_mcp.core import (
    capture_pane,
    detect_kind,
    split_lines,
    last_meaningful_line,
    extract_last_command_and_output,
    send_keys,
    wait_and_capture,
)

def simulate_is_repl_ready(kind: str, pane: str = "0", max_lines: int = 200) -> dict:
    """
    Simulates the is_repl_ready MCP tool.
    
    From server.py:
    def is_repl_ready(kind: str, pane: str = "0", max_lines: int = 200):
        kinds = load_kinds()
        debugger_patterns = load_debugger_patterns()
        lines = split_lines(capture_pane(pane, max_lines))
        detected_kind = detect_kind(lines, kinds, debugger_patterns)
        return {"kind": detected_kind, "is_ready": detected_kind == kind}
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    lines = split_lines(capture_pane(pane, max_lines))
    detected_kind = detect_kind(lines, kinds, debugger_patterns)
    
    print(f"[is_repl_ready] Captured {len(lines)} lines from pane {pane}")
    print(f"[is_repl_ready] Last meaningful line: {last_meaningful_line(lines)!r}")
    print(f"[is_repl_ready] Detected kind: {detected_kind!r}")
    print(f"[is_repl_ready] Requested kind: {kind!r}")
    
    return {
        "kind": detected_kind,
        "is_ready": detected_kind == kind,
    }

def simulate_get_last_command(kind: str, pane: str = "0", max_lines: int = 200) -> dict:
    """
    Simulates the get_last_command MCP tool.
    
    From server.py:
    def get_last_command(kind: str, pane: str = "0", max_lines: int = 200):
        kinds = load_kinds()
        debugger_patterns = load_debugger_patterns()
        lines = split_lines(capture_pane(pane, max_lines))
        current_kind = detect_kind(lines, kinds, debugger_patterns)
        if current_kind is None:
            return {"last_command": None, "output": None}
        last_command, output = extract_last_command_and_output(lines, kind, kinds)
        return {"last_command": last_command, "output": output}
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)
    
    print(f"[get_last_command] Captured {len(lines)} lines from pane {pane}")
    print(f"[get_last_command] Current detected kind: {current_kind!r}")
    
    if current_kind is None:
        print("[get_last_command] No prompt detected, returning None")
        return {"last_command": None, "output": None}
    
    last_command, output = extract_last_command_and_output(lines, kind, kinds)
    print(f"[get_last_command] Extracted command: {last_command!r}")
    print(f"[get_last_command] Extracted output: {output!r}")
    
    return {"last_command": last_command, "output": output}

def simulate_execute_command(command: str, kind: str, pane: str = "0", max_lines: int = 200, check: float = 0.5) -> dict:
    """
    Simulates the execute_command MCP tool.
    
    From server.py:
    def execute_command(command: str, kind: str, pane: str = "0", max_lines: int = 200, check: float = 2.0):
        kinds = load_kinds()
        debugger_patterns = load_debugger_patterns()
        lines = split_lines(capture_pane(pane, max_lines))
        current_kind = detect_kind(lines, kinds, debugger_patterns)
        
        if current_kind is None:
            return {"status": "error", "reason": "REPL is not ready (no prompt detected)."}
        
        if current_kind != kind:
            return {"status": "error", "reason": f"Expected REPL kind {kind!r} but detected {current_kind!r}."}
        
        send_keys(pane, command)
        final_lines = wait_and_capture(pane, kind, kinds, max_lines, check, debugger_patterns)
        
        # Check if we're in debugger
        from tmux_repl_mcp.core import is_debugger_prompt, last_meaningful_line
        last_line = last_meaningful_line(final_lines)
        if last_line is not None and is_debugger_prompt(last_line, kind, debugger_patterns):
            last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
            return {
                "status": "debugger",
                "reason": "REPL entered debugger (error occurred).",
                "last_command": last_command,
                "output": output,
            }
        
        last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
        return {"status": "ok", "last_command": last_command, "output": output}
    """
    kinds = load_kinds()
    debugger_patterns = load_debugger_patterns()
    
    # Pre-flight check
    lines = split_lines(capture_pane(pane, max_lines))
    current_kind = detect_kind(lines, kinds, debugger_patterns)
    
    print(f"[execute_command] Pre-flight: detected kind = {current_kind!r}")
    
    if current_kind is None:
        return {
            "status": "error",
            "reason": "REPL is not ready (no prompt detected).",
            "last_command": None,
            "output": None,
        }
    
    if current_kind != kind:
        return {
            "status": "error",
            "reason": f"Expected REPL kind {kind!r} but detected {current_kind!r}.",
            "last_command": None,
            "output": None,
        }
    
    print(f"[execute_command] Sending command: {command!r}")
    send_keys(pane, command)
    
    print(f"[execute_command] Waiting for REPL to be idle...")
    final_lines = wait_and_capture(pane, kind, kinds, max_lines, check, debugger_patterns)
    
    # Check if we're in debugger
    from tmux_repl_mcp.core import is_debugger_prompt, last_meaningful_line
    last_line = last_meaningful_line(final_lines)
    if last_line is not None and is_debugger_prompt(last_line, kind, debugger_patterns):
        last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
        print(f"[execute_command] Debugger detected")
        print(f"[execute_command] Last command: {last_command!r}")
        print(f"[execute_command] Output: {output!r}")
        return {
            "status": "debugger",
            "reason": "REPL entered debugger (error occurred).",
            "last_command": last_command,
            "output": output,
        }
    
    last_command, output = extract_last_command_and_output(final_lines, kind, kinds)
    
    print(f"[execute_command] Command completed")
    print(f"[execute_command] Last command: {last_command!r}")
    print(f"[execute_command] Output: {output!r}")
    
    return {
        "status": "ok",
        "last_command": last_command,
        "output": output,
    }

def main():
    pane = "0"
    kind = "lisp"
    
    print("=" * 70)
    print("SIMULATING MCP TOOL CALLS")
    print("=" * 70)
    
    # Test 1: is_repl_ready
    print("\n" + "=" * 70)
    print("TEST 1: is_repl_ready(kind='lisp', pane='0', max_lines=200)")
    print("=" * 70)
    result = simulate_is_repl_ready(kind, pane, 200)
    print(f"\nResult: {result}")
    
    # Test 2: get_last_command
    print("\n" + "=" * 70)
    print("TEST 2: get_last_command(kind='lisp', pane='0', max_lines=200)")
    print("=" * 70)
    result = simulate_get_last_command(kind, pane, 200)
    print(f"\nResult: {result}")
    
    # Test 3: execute_command (if REPL is ready)
    if result.get("last_command") is not None or simulate_is_repl_ready(kind, pane, 200).get("is_ready"):
        print("\n" + "=" * 70)
        print("TEST 3: execute_command(command='(+ 1 2)', kind='lisp', pane='0', max_lines=200, check=0.5)")
        print("=" * 70)
        result = simulate_execute_command("(+ 1 2)", kind, pane, 200, 0.5)
        print(f"\nResult: {result}")
    
    # Test 4: get_last_command after execute
    print("\n" + "=" * 70)
    print("TEST 4: get_last_command(kind='lisp', pane='0', max_lines=200) - after execute")
    print("=" * 70)
    result = simulate_get_last_command(kind, pane, 200)
    print(f"\nResult: {result}")

if __name__ == "__main__":
    main()
