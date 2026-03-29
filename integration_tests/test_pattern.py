#!/usr/bin/env python3
"""Test the lisp pattern directly on the actual last line."""

import sys
sys.path.insert(0, '/home/skin/Code/djha-skin/tmux-repl-mcp/src')

import re
from tmux_repl_mcp.config import load_kinds

kinds = load_kinds()
lisp_pattern = kinds['lisp']

print(f"Lisp pattern: {lisp_pattern!r}")
print()

test_lines = [
    "*",
    "* ",
    "* (+ 1 2)",
    "3",
]

for line in test_lines:
    match = re.search(lisp_pattern, line)
    print(f"{line!r:20s} -> {'MATCH' if match else 'NO MATCH'}")
    if match:
        print(f"  Matched: {match.group()!r}")
