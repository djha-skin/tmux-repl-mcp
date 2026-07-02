"""
Unit tests for tmux_repl_mcp.core (no tmux required).
"""

import pytest
from tmux_repl_mcp.core import (
    DEFAULT_PROMPT_PATTERNS,
    detect_kind,
    extract_last_command_and_output,
    is_prompt_line,
    last_meaningful_line,
    last_prompt_index,
    prompt_block_p,
    second_to_last_prompt_index,
    split_lines,
)

PROMPT_PATTERNS = DEFAULT_PROMPT_PATTERNS


# ---------------------------------------------------------------------------
# split_lines
# ---------------------------------------------------------------------------


def test_split_lines_basic():
    assert split_lines("a\nb\nc") == ["a", "b", "c"]


def test_split_lines_trailing_newline():
    assert split_lines("a\nb\n") == ["a", "b", ""]


# ---------------------------------------------------------------------------
# is_prompt_line
# ---------------------------------------------------------------------------


def test_is_prompt_line_python():
    assert is_prompt_line(">>> ", "python", PROMPT_PATTERNS)
    assert is_prompt_line(">>> 1 + 1", "python", PROMPT_PATTERNS)
    assert not is_prompt_line("... ", "python", PROMPT_PATTERNS)


def test_is_prompt_line_lisp():
    # Top-level CL prompt ("* " followed by optional command text)
    assert is_prompt_line("* ", "lisp", PROMPT_PATTERNS)
    assert is_prompt_line("* (+ 1 2)", "lisp", PROMPT_PATTERNS)
    # Named package prompt
    assert is_prompt_line("slynk> ", "lisp", PROMPT_PATTERNS)
    assert is_prompt_line("0] ", "lisp", PROMPT_PATTERNS)
    assert is_prompt_line("   3] ", "lisp", PROMPT_PATTERNS)
    # Not a prompt
    assert not is_prompt_line("hello", "lisp", PROMPT_PATTERNS)
    assert not is_prompt_line("3", "lisp", PROMPT_PATTERNS)



def test_is_prompt_line_bash():
    assert is_prompt_line("user@host:~$ ", "bash", PROMPT_PATTERNS)
    assert is_prompt_line("root@host:~# ", "bash", PROMPT_PATTERNS)
    assert not is_prompt_line("echo hello", "bash", PROMPT_PATTERNS)


def test_is_prompt_line_unknown_kind():
    assert not is_prompt_line(">>> ", "nonexistent", PROMPT_PATTERNS)


# ---------------------------------------------------------------------------
# last_meaningful_line
# ---------------------------------------------------------------------------


def test_last_meaningful_line_basic():
    assert last_meaningful_line(["a", "b", "c"]) == "c"


def test_last_meaningful_line_trailing_empties():
    assert last_meaningful_line(["a", "b", "", "  ", ""]) == "b"


def test_last_meaningful_line_all_empty():
    assert last_meaningful_line(["", "  ", ""]) is None


# ---------------------------------------------------------------------------
# last_prompt_index / second_to_last_prompt_index
# ---------------------------------------------------------------------------


PYTHON_SESSION = [
    ">>> 1 + 1",
    "2",
    ">>> print('hello')",
    "hello",
    ">>> ",
]


def test_last_prompt_index():
    assert last_prompt_index(PYTHON_SESSION, "python", PROMPT_PATTERNS) == 4


def test_second_to_last_prompt_index():
    assert second_to_last_prompt_index(PYTHON_SESSION, "python", PROMPT_PATTERNS) == 2


def test_last_prompt_index_none():
    lines = ["just some output", "no prompt here"]
    assert last_prompt_index(lines, "python", PROMPT_PATTERNS) is None


def test_second_to_last_prompt_index_only_one_prompt():
    lines = ["some output", ">>> "]
    assert second_to_last_prompt_index(lines, "python", PROMPT_PATTERNS) is None


# ---------------------------------------------------------------------------
# prompt_block_p
# ---------------------------------------------------------------------------


def test_prompt_block_p_true():
    assert prompt_block_p(PYTHON_SESSION, "python", PROMPT_PATTERNS)


def test_prompt_block_p_no_trailing_prompt():
    lines = [">>> 1 + 1", "2"]
    assert not prompt_block_p(lines, "python", PROMPT_PATTERNS)


def test_prompt_block_p_only_one_prompt():
    lines = ["some output", ">>> "]
    assert not prompt_block_p(lines, "python", PROMPT_PATTERNS)


# ---------------------------------------------------------------------------
# detect_kind
# ---------------------------------------------------------------------------


def test_detect_kind_python():
    lines = [">>> 1 + 1", "2", ">>> "]
    assert detect_kind(lines, PROMPT_PATTERNS) == "python"


def test_detect_kind_sbcl():
    # SBCL uses the generic "lisp" prompt (* / debugger N]); no separate kind.
    lines = ["* (+ 1 1)", "2", "* "]
    assert detect_kind(lines, PROMPT_PATTERNS) == "lisp"


def test_detect_kind_lisp_debugger():
    # When in debugger, detect_kind should return None (not ready)
    lines = ["* (/ 1 0)", "error message", "0] "]
    assert detect_kind(lines, PROMPT_PATTERNS) == "lisp"


def test_detect_kind_none():
    lines = ["just some output"]
    assert detect_kind(lines, PROMPT_PATTERNS) is None


# ---------------------------------------------------------------------------
# extract_last_command_and_output
# ---------------------------------------------------------------------------


PYTHON_BLOCK = [
    ">>> 2 + 2",
    "4",
    ">>> print('world')",
    "world",
    ">>> ",
]


def test_extract_last_command_and_output_python():
    cmd, out = extract_last_command_and_output(PYTHON_BLOCK, "python", PROMPT_PATTERNS)
    assert cmd == "print('world')"
    assert out == "world"


def test_extract_last_command_no_block():
    lines = ["some output", ">>> "]
    cmd, out = extract_last_command_and_output(lines, "python", PROMPT_PATTERNS)
    assert cmd is None
    assert out is None


def test_extract_last_command_lisp():
    # SBCL/generic CL prompts are matched by the "lisp" kind.
    lines = [
        "* (+ 1 2)",
        "3",
        '* (format t "hello~%")',
        "hello",
        "NIL",
        "* ",
    ]
    cmd, out = extract_last_command_and_output(lines, "lisp", PROMPT_PATTERNS)
    assert cmd == '(format t "hello~%")'
    assert "hello" in out
    assert "NIL" in out


def test_extract_multiline_output():
    lines = [
        ">>> for i in range(3): print(i)",
        "0",
        "1",
        "2",
        ">>> ",
    ]
    cmd, out = extract_last_command_and_output(lines, "python", PROMPT_PATTERNS)
    assert cmd == "for i in range(3): print(i)"
    assert out == "0\n1\n2"


# ---------------------------------------------------------------------------
# goose
# ---------------------------------------------------------------------------

GOOSE_READY = "🪿 Enter to send · Ctrl+J newline"
GOOSE_BUSY = "🪿 Press Ctrl+C again to exit, or type new instructions to continue"


def test_is_prompt_line_goose():
    assert is_prompt_line(GOOSE_READY, "goose", PROMPT_PATTERNS)
    assert not is_prompt_line(GOOSE_BUSY, "goose", PROMPT_PATTERNS)
    assert not is_prompt_line("some other output", "goose", PROMPT_PATTERNS)


def test_is_prompt_line_goose_not_other_kinds():
    assert not is_prompt_line(GOOSE_READY, "python", PROMPT_PATTERNS)
    assert not is_prompt_line(GOOSE_READY, "bash", PROMPT_PATTERNS)


def test_last_meaningful_line_goose():
    lines = [
        "    __( O)>  ● new session",
        "   \\____)    20260702_6",
        "     L L     goose is ready",
        "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 0% 0/128k",
        f"Cost: $0.0000 USD (0 tokens: in 0, out 0)",
        GOOSE_READY,
    ]
    assert last_meaningful_line(lines) == GOOSE_READY


def test_last_prompt_index_goose():
    lines = [
        "    __( O)>  ● new session",
        "   \\____)    20260702_6",
        "     L L     goose is ready",
        "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 0% 0/128k",
        f"Cost: $0.0000 USD (0 tokens: in 0, out 0)",
        GOOSE_READY,
    ]
    assert last_prompt_index(lines, "goose", PROMPT_PATTERNS) == 5


def test_detect_kind_goose():
    lines = [
        "    __( O)>  ● new session",
        "   \\____)    20260702_6",
        "     L L     goose is ready",
        "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 0% 0/128k",
        f"Cost: $0.0000 USD (0 tokens: in 0, out 0)",
        GOOSE_READY,
    ]
    assert detect_kind(lines, PROMPT_PATTERNS) == "goose"


def test_detect_kind_goose_busy():
    lines = [
        "    __( O)>  ● new session",
        "   \\____)    20260702_6",
        "     L L     processing...",
        "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 2% 100/128k",
        f"Cost: $0.0012 USD (50 tokens: in 30, out 20)",
        GOOSE_BUSY,
    ]
    assert detect_kind(lines, PROMPT_PATTERNS) is None


def test_prompt_block_p_goose():
    # Two goose prompts with content between them = valid block
    lines = [
        "Cost: $0.0000 USD (0 tokens: in 0, out 0)",
        GOOSE_READY,
        "Cost: $0.0012 USD (50 tokens: in 30, out 20)",
        GOOSE_READY,
    ]
    assert prompt_block_p(lines, "goose", PROMPT_PATTERNS)


def test_prompt_block_p_goose_single_prompt():
    lines = [
        "    __( O)>  ● new session",
        GOOSE_READY,
    ]
    assert not prompt_block_p(lines, "goose", PROMPT_PATTERNS)
