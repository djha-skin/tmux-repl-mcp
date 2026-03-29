#!/usr/bin/env python3
"""Check what the actual last line looks like."""

import subprocess

result = subprocess.run(
    ["tmux", "capture-pane", "-t", "0", "-p", "-S", "-10"],
    capture_output=True,
    text=True,
    encoding="ISO-8859-1",
    errors="replace",
)

lines = result.stdout.split("\n")
print(f"Last 10 lines from pane:")
for i, line in enumerate(lines[-10:], start=len(lines)-10):
    print(f"{i:3d}: {line!r}  (bytes: {[ord(c) for c in line]})")

print(f"\nVery last line: {lines[-1]!r}")
print(f"Very last line bytes: {[ord(c) for c in lines[-1]]}")
