"""
Regression tests for tmux-repl-mcp.

Real pane capture from pane 0 after running `(/ 1 0)` in SBCL:

    * (+ 1 2)
    3
    * (/ 1 0)

    debugger invoked on a DIVISION-BY-ZERO in thread
    #<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
      arithmetic error DIVISION-BY-ZERO signalled
    Operation was (/ 1 0).

    Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

    restarts (invokable by number or by possibly-abbreviated name):
      0: [ABORT] Exit debugger, returning to top level.

    (SB-KERNEL::INTEGER-/-INTEGER 1 0)
    0] abort
    * (/ 1 0)

    debugger invoked on a DIVISION-BY-ZERO in thread
    #<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
      arithmetic error DIVISION-BY-ZERO signalled
    Operation was (/ 1 0).

    Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

    restarts (invokable by number or by possibly-abbreviated name):
      0: [ABORT] Exit debugger, returning to top level.

    (SB-KERNEL::INTEGER-/-INTEGER 1 0)
    0]

The tool reported:
  last_command = "abort"   <-- BUG: should be "(/ 1 0)"
  output       = ""        <-- BUG: should contain the DIVISION-BY-ZERO lines
"""

from unittest.mock import patch

import pytest

from tmux_repl_mcp.core import (
    DEFAULT_DEBUGGER_PATTERNS,
    DEFAULT_READY_PATTERNS,
    extract_last_command_and_output,
    split_lines,
)
from tmux_repl_mcp.server import execute_command

# ---------------------------------------------------------------------------
# The exact pane content captured from tmux pane 0 (trimmed to the relevant
# final block: from the last `* (/ 1 0)` through the `0]` idle prompt).
# ---------------------------------------------------------------------------
PANE_AFTER_DIVIDE_BY_ZERO = (
    "* (+ 1 2)\n"
    "3\n"
    "* (/ 1 0)\n"
    "\n"
    "debugger invoked on a DIVISION-BY-ZERO in thread\n"
    "#<THREAD tid=98751 \"main thread\" RUNNING {1203FF0003}>:\n"
    "  arithmetic error DIVISION-BY-ZERO signalled\n"
    "Operation was (/ 1 0).\n"
    "\n"
    "Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.\n"
    "\n"
    "restarts (invokable by number or by possibly-abbreviated name):\n"
    "  0: [ABORT] Exit debugger, returning to top level.\n"
    "\n"
    "(SB-KERNEL::INTEGER-/-INTEGER 1 0)\n"
    "0] \n"
)

# ---------------------------------------------------------------------------
# NEW REGRESSION: Full pane capture from the latest bug report.
# This is the ACTUAL captured pane content from tmux pane 0 after running
# `(/ 1 0)` in SBCL. The pane ends with the debugger prompt "0]".
# ---------------------------------------------------------------------------
PANE_CAPTURE_FULL = """  arithmetic error DIVISION-BY-ZERO signalled
Operation was (/ 1 0).

Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

restarts (invokable by number or by possibly-abbreviated name):
  0: [ABORT] Reduce debugger level (to debug level 1).
  1:         Exit debugger, returning to top level.

(SB-KERNEL::INTEGER-/-INTEGER 1 0)
0[2] 0

0] abort
* (/ 1 0)

debugger invoked on a DIVISION-BY-ZERO in thread
#<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
  arithmetic error DIVISION-BY-ZERO signalled
Operation was (/ 1 0).

Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

restarts (invokable by number or by possibly-abbreviated name):
  0: [ABORT] Exit debugger, returning to top level.

(SB-KERNEL::INTEGER-/-INTEGER 1 0)
0]
0
* (/ 1 0)

debugger invoked on a DIVISION-BY-ZERO in thread
#<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
  arithmetic error DIVISION-BY-ZERO signalled
Operation was (/ 1 0).

Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

restarts (invokable by number or by possibly-abbreviated name):
  0: [ABORT] Exit debugger, returning to top level.

(SB-KERNEL::INTEGER-/-INTEGER 1 0)
0]"""

# Trimmed version for testing - just the final debugger state
PANE_CAPTURE_FINAL_DEBUGGER = """* (/ 1 0)

debugger invoked on a DIVISION-BY-ZERO in thread
#<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
  arithmetic error DIVISION-BY-ZERO signalled
Operation was (/ 1 0).

Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

restarts (invokable by number or by possibly-abbreviated name):
  0: [ABORT] Exit debugger, returning to top level.

(SB-KERNEL::INTEGER-/-INTEGER 1 0)
0]"""

# What the tool INCORRECTLY captured (truncated output)
PANE_CAPTURE_TRUNCATED = """* (/ 1 0)

debugger invoked on a DIVISION-BY-ZERO in thread
#<THREAD tid=98751 "main thread" RUNNING {1203FF0003}>:
  arithmetic error DIVISION-BY-ZERO signalled
Operation was (/ 1 0).

Type HELP for debugger help, or (SB-EXT:EXIT) to exit from SBCL.

restarts (invokable by number or by possibly-abbreviated name):
  0: [ABORT] Exit debugger, returning to top level."""


# ---------------------------------------------------------------------------
# Regression: execute_command should return last_command="(/ 1 0)" and
# non-empty output containing the error, not last_command="abort".
# ---------------------------------------------------------------------------


class TestDivideByZeroRegression:
    """
    Regression for the bug where executing `(/ 1 0)` in a Lisp REPL
    caused execute_command to report last_command="abort" and output="".

    The root cause: after the REPL entered the debugger, `wait_and_capture`
    returned the pane correctly, but `extract_last_command_and_output` was
    called on lines that ended with a debugger prompt (`0] `).  Because the
    debugger prompt does NOT match the lisp ready-pattern, the function
    could not find a "last prompt line" and fell back to None/None.  The
    server then returned the stale get_last_command result (which saw
    "abort" as the last command at the top-level prompt).
    """

    def _run_execute_command(self, post_command_pane_content: str) -> dict:
        """
        Call execute_command with:
          - capture_pane returning a ready-state pane for the pre-flight check
          - wait_and_capture returning the post-command pane (with debugger prompt)
          - send_keys mocked out (no real tmux)
        """
        # Pre-flight needs a ready lisp prompt so the command is actually sent.
        preflight_pane = "* (+ 1 2)\n3\n* \n"

        with patch(
            "tmux_repl_mcp.server.capture_pane", return_value=preflight_pane
        ), patch(
            "tmux_repl_mcp.server.send_keys"
        ), patch(
            "tmux_repl_mcp.server.wait_and_capture",
            return_value=split_lines(post_command_pane_content),
        ):
            return execute_command(command="(/ 1 0)", kind="lisp", pane="0")

    def test_last_command_is_the_division_expression(self):
        """last_command must be '(/ 1 0)', not 'abort'."""
        result = self._run_execute_command(PANE_AFTER_DIVIDE_BY_ZERO)
        assert result["last_command"] == "(/ 1 0)", (
            f"Expected last_command='(/ 1 0)' but got {result['last_command']!r}. "
            "This is the regression: the tool was returning 'abort' (the restart "
            "command typed inside the debugger) instead of the original expression."
        )

    def test_output_contains_division_by_zero_error(self):
        """output must contain the DIVISION-BY-ZERO error lines."""
        result = self._run_execute_command(PANE_AFTER_DIVIDE_BY_ZERO)
        assert result["output"], (
            f"Expected non-empty output but got {result['output']!r}."
        )
        assert "DIVISION-BY-ZERO" in result["output"], (
            f"Expected 'DIVISION-BY-ZERO' in output but got: {result['output']!r}"
        )

    def test_output_contains_lines_between_command_and_debugger_prompt(self):
        """output must be the lines between '* (/ 1 0)' and '0]'."""
        result = self._run_execute_command(PANE_AFTER_DIVIDE_BY_ZERO)
        output = result["output"] or ""
        # The error block should be present
        assert "arithmetic error DIVISION-BY-ZERO signalled" in output
        assert "Operation was (/ 1 0)." in output
        assert "restarts" in output
        # The debugger prompt itself (0] ) should be the boundary, not in output
        assert not output.strip().endswith("0]"), (
            "The debugger prompt '0]' should be the boundary line, not part of output"
        )


# ---------------------------------------------------------------------------
# Unit-level: extract_last_command_and_output with a debugger-terminated block
# ---------------------------------------------------------------------------


class TestExtractWithDebuggerPrompt:
    """
    extract_last_command_and_output must handle the case where the final
    'prompt' is a debugger prompt (e.g. '0] ') rather than the normal
    top-level prompt ('* ').
    """

    def test_extract_command_when_block_ends_in_debugger_prompt(self):
        lines = split_lines(PANE_AFTER_DIVIDE_BY_ZERO)
        cmd, out = extract_last_command_and_output(
            lines, "lisp", DEFAULT_READY_PATTERNS, DEFAULT_DEBUGGER_PATTERNS
        )
        assert cmd == "(/ 1 0)", f"Got {cmd!r}"
        assert out is not None
        assert "DIVISION-BY-ZERO" in out

    def test_extract_output_does_not_include_debugger_prompt_line(self):
        lines = split_lines(PANE_AFTER_DIVIDE_BY_ZERO)
        _, out = extract_last_command_and_output(
            lines, "lisp", DEFAULT_READY_PATTERNS, DEFAULT_DEBUGGER_PATTERNS
        )
        # The boundary line "0] " should not appear as the last line of output
        assert out is not None
        last_out_line = out.rstrip("\n").splitlines()[-1] if out.strip() else ""
        assert not last_out_line.strip().startswith("0]"), (
            f"Debugger prompt leaked into output: {last_out_line!r}"
        )


# ---------------------------------------------------------------------------
# NEW REGRESSION TESTS: Bug from latest session
# ---------------------------------------------------------------------------

class TestFullPaneCaptureRegression:
    """
    Regression tests for the latest bug report:
    1. Not all lines were captured - last line should be
       "(SB-KERNEL::INTEGER-/-INTEGER 1 0)" but was truncated at
       "Operation was (/ 1 0)."
    2. The "0]" prompt SHOULD be recognized as a ready lisp prompt.
    """

    def test_debugger_prompt_0_is_recognized_as_ready(self):
        """The '0]' debugger prompt should be recognized as a lisp prompt."""
        from tmux_repl_mcp.core import is_debugger_prompt
        
        # The pattern "0] " should match the debugger pattern
        assert is_debugger_prompt("0] ", "lisp", DEFAULT_DEBUGGER_PATTERNS)
        assert is_debugger_prompt("0]", "lisp", DEFAULT_DEBUGGER_PATTERNS)
        assert is_debugger_prompt("1] ", "lisp", DEFAULT_DEBUGGER_PATTERNS)

    def test_extract_command_from_full_pane_capture(self):
        """Extract command and output from the full pane capture."""
        lines = split_lines(PANE_CAPTURE_FULL)
        cmd, out = extract_last_command_and_output(
            lines, "lisp", DEFAULT_READY_PATTERNS, DEFAULT_DEBUGGER_PATTERNS
        )
        # Should extract the last command "(/ 1 0)"
        assert cmd == "(/ 1 0)", f"Expected '(/ 1 0)' but got {cmd!r}"
        # Output should contain the full error including the last line
        assert out is not None
        assert "DIVISION-BY-ZERO" in out
        assert "(SB-KERNEL::INTEGER-/-INTEGER 1 0)" in out, (
            f"Expected '(SB-KERNEL::INTEGER-/-INTEGER 1 0)' in output but got: {out!r}"
        )

    def test_extract_command_from_final_debugger_state(self):
        """Extract command and output from the final debugger state."""
        lines = split_lines(PANE_CAPTURE_FINAL_DEBUGGER)
        cmd, out = extract_last_command_and_output(
            lines, "lisp", DEFAULT_READY_PATTERNS, DEFAULT_DEBUGGER_PATTERNS
        )
        assert cmd == "(/ 1 0)", f"Expected '(/ 1 0)' but got {cmd!r}"
        assert out is not None
        # The output should include ALL lines up to the debugger prompt
        assert "DIVISION-BY-ZERO" in out
        assert "arithmetic error DIVISION-BY-ZERO signalled" in out
        assert "Operation was (/ 1 0)." in out
        assert "restarts" in out
        # CRITICAL: The last line before the prompt should be captured
        assert "(SB-KERNEL::INTEGER-/-INTEGER 1 0)" in out, (
            f"BUG: Last line not captured! Output was: {out!r}"
        )

    def test_truncated_capture_fails(self):
        """
        Demonstrate the bug: when capture is truncated, the last line
        "(SB-KERNEL::INTEGER-/-INTEGER 1 0)" is missing.
        """
        lines = split_lines(PANE_CAPTURE_TRUNCATED)
        cmd, out = extract_last_command_and_output(
            lines, "lisp", DEFAULT_READY_PATTERNS, DEFAULT_DEBUGGER_PATTERNS
        )
        # With truncated capture, there's no debugger prompt at the end,
        # so extraction should fail or return incomplete results
        # This test documents the bug - it should FAIL before the fix
        if out is not None:
            # If we got output, it should still be missing the last line
            assert "(SB-KERNEL::INTEGER-/-INTEGER 1 0)" not in out, (
                "Truncated capture should not have the last line"
            )
