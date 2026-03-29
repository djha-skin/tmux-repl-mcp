#!/usr/bin/env python3
"""Debug extract_last_command_and_output to find why last_command is empty."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

import re
from tmux_repl_mcp.config import load_kinds
from tmux_repl_mcp.core import (
    capture_pane,
    split_lines,
    last_meaningful_line,
    is_prompt_line,
    last_prompt_index,
    second_to_last_prompt_index,
)

def debug_extract(pane: str, kind: str, max_lines: int = 200):
    kinds = load_kinds()
    lines = split_lines(capture_pane(pane, max_lines))
    
    print(f"Captured {len(lines)} lines from pane {pane}")
    print(f"Looking for kind: {kind!r}")
    print(f"Pattern for {kind}: {kinds[kind]!r}")
    print()
    
    # Show all lines that match the lisp prompt
    print("Lines matching Lisp prompt pattern:")
    for i, line in enumerate(lines):
        if is_prompt_line(line, kind, kinds):
            print(f"  {i}: {line!r}")
    print()
    
    end_idx = last_prompt_index(lines, kind, kinds)
    start_idx = second_to_last_prompt_index(lines, kind, kinds)
    
    print(f"last_prompt_index: {end_idx}")
    print(f"second_to_last_prompt_index: {start_idx}")
    print()
    
    if start_idx is None or end_idx is None:
        print("ERROR: Could not find both prompts!")
        return
    
    print(f"Lines around the command block:")
    for i in range(max(0, start_idx-2), min(len(lines), end_idx+3)):
        marker = " <-- second-to-last prompt" if i == start_idx else ""
        marker += " <-- last prompt" if i == end_idx else ""
        print(f"  {i}: {lines[i]!r}{marker}")
    print()
    
    pattern = kinds[kind]
    prompt_line = lines[start_idx]
    print(f"Prompt line to parse: {prompt_line!r}")
    print(f"Pattern: {pattern!r}")
    
    # Try the regex substitution
    last_command = re.sub(pattern, "", prompt_line, count=1).strip()
    print(f"After re.sub: {last_command!r}")
    
    # Show what the regex matches
    match = re.search(pattern, prompt_line)
    if match:
        print(f"Regex matched: {match.group()!r} at position {match.span()}")
    
    # The issue might be with the lisp pattern!
    print()
    print("=" * 60)
    print("Testing the Lisp pattern more carefully:")
    print("=" * 60)
    
    # The lisp pattern is: r"^\*(?:\s.*)?$|^\d+\] |^[A-Za-z0-9.]+> "
    # This has THREE alternatives:
    # 1. ^\*(?:\s.*)?$  - matches "*" or "* " followed by anything
    # 2. ^\d+\]         - matches "1] ", "2] ", etc.
    # 3. ^[A-Za-z0-9.]+>  - matches "slynk> ", etc.
    
    test_lines = [
        "*",
        "* (+ 1 2)",
        "1] ",
        "1] (error)",
        "slynk> ",
        "slynk> (foo)",
    ]
    
    for test in test_lines:
        match = re.search(pattern, test)
        if match:
            extracted = re.sub(pattern, "", test, count=1).strip()
            print(f"  {test!r:20s} -> matched {match.group()!r:15s} -> extracted {extracted!r}")
        else:
            print(f"  {test!r:20s} -> NO MATCH")

if __name__ == "__main__":
    debug_extract("0", "lisp", 200)
