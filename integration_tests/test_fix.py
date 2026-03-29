#!/usr/bin/env python3
"""Test the FIXED Lisp pattern with hyphen support."""

import re

# Original buggy pattern
OLD_PATTERN = r"^\*(?:\s.*)?$|^\d+\] |^[A-Za-z0-9.]+> "

# Fixed pattern - only match the prompt, not the command
# Added hyphen to character class for CL-USER> style prompts
NEW_PATTERN = r"^\* |^\*$|^\d+\] |^[A-Za-z0-9.-]+> "

test_lines = [
    "*",              # bare prompt
    "* ",             # prompt with space
    "* (+ 1 2)",      # prompt with command
    "* (foo bar)",    # another command
    "1] ",            # debugger prompt
    "1] (error)",     # debugger with command
    "slynk> ",        # package prompt
    "slynk> (foo)",   # package with command
    "CL-USER> ",      # another package prompt
    "CL-USER> (bar)", # with command
]

print("Comparing OLD vs NEW pattern:")
print("=" * 80)
print(f"{'Line':<20} {'OLD match':<20} {'OLD extract':<15} {'NEW match':<20} {'NEW extract':<15}")
print("=" * 80)

for line in test_lines:
    old_match = re.search(OLD_PATTERN, line)
    new_match = re.search(NEW_PATTERN, line)
    
    old_extracted = re.sub(OLD_PATTERN, "", line, count=1).strip() if old_match else "NO MATCH"
    new_extracted = re.sub(NEW_PATTERN, "", line, count=1).strip() if new_match else "NO MATCH"
    
    old_match_str = old_match.group() if old_match else "NO MATCH"
    new_match_str = new_match.group() if new_match else "NO MATCH"
    
    print(f"{repr(line):<20} {repr(old_match_str):<20} {repr(old_extracted):<15} {repr(new_match_str):<20} {repr(new_extracted):<15}")
