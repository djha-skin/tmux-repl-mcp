"""
Unit tests for tmux_repl_mcp.core (no tmux required).
"""

import pytest
from tmux_repl_mcp.core import (
    DEFAULT_KINDS,
    detect_kind,
    extract_last_command_and_output,
    is_prompt_line,
    last_meaningful_line,
    last_prompt_index,
    prompt_block_p,
    second_to_last_prompt_index,
    split_lines,
)

KINDS = DEFAULT_KINDS


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
    assert is_prompt_line(">>> ", "python", KINDS)
    assert is_prompt_line(">>> 1 + 1", "python", KINDS)
    assert not is_prompt_line("... ", "python", KINDS)


def test_is_prompt_line_lisp():
    # Top-level CL prompt ("* " followed by optional command text)
    assert is_prompt_line("* ", "lisp", KINDS)
    assert is_prompt_line("* (+ 1 2)", "lisp", KINDS)
    # Debugger prompt
    assert is_prompt_line("1] ", "lisp", KINDS)
    assert is_prompt_line("1] (help)", "lisp", KINDS)
    # Named package prompt
    assert is_prompt_line("slynk> ", "lisp", KINDS)
    # Not a prompt
    assert not is_prompt_line("hello", "lisp", KINDS)
    assert not is_prompt_line("3", "lisp", KINDS)


def test_is_prompt_line_bash():
    assert is_prompt_line("user@host:~$ ", "bash", KINDS)
    assert is_prompt_line("root@host:~# ", "bash", KINDS)
    assert not is_prompt_line("echo hello", "bash", KINDS)


def test_is_prompt_line_unknown_kind():
    assert not is_prompt_line(">>> ", "nonexistent", KINDS)


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
    assert last_prompt_index(PYTHON_SESSION, "python", KINDS) == 4


def test_second_to_last_prompt_index():
    assert second_to_last_prompt_index(PYTHON_SESSION, "python", KINDS) == 2


def test_last_prompt_index_none():
    lines = ["just some output", "no prompt here"]
    assert last_prompt_index(lines, "python", KINDS) is None


def test_second_to_last_prompt_index_only_one_prompt():
    lines = ["some output", ">>> "]
    assert second_to_last_prompt_index(lines, "python", KINDS) is None


# ---------------------------------------------------------------------------
# prompt_block_p
# ---------------------------------------------------------------------------


def test_prompt_block_p_true():
    assert prompt_block_p(PYTHON_SESSION, "python", KINDS)


def test_prompt_block_p_no_trailing_prompt():
    lines = [">>> 1 + 1", "2"]
    assert not prompt_block_p(lines, "python", KINDS)


def test_prompt_block_p_only_one_prompt():
    lines = ["some output", ">>> "]
    assert not prompt_block_p(lines, "python", KINDS)


# ---------------------------------------------------------------------------
# detect_kind
# ---------------------------------------------------------------------------


def test_detect_kind_python():
    lines = [">>> 1 + 1", "2", ">>> "]
    assert detect_kind(lines, KINDS) == "python"


def test_detect_kind_sbcl():
    # SBCL uses the generic "lisp" prompt (* / debugger N]); no separate kind.
    lines = ["* (+ 1 1)", "2", "* "]
    assert detect_kind(lines, KINDS) == "lisp"


def test_detect_kind_none():
    lines = ["just some output"]
    assert detect_kind(lines, KINDS) is None


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
    cmd, out = extract_last_command_and_output(PYTHON_BLOCK, "python", KINDS)
    assert cmd == "print('world')"
    assert out == "world"


def test_extract_last_command_no_block():
    lines = ["some output", ">>> "]
    cmd, out = extract_last_command_and_output(lines, "python", KINDS)
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
    cmd, out = extract_last_command_and_output(lines, "lisp", KINDS)
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
    cmd, out = extract_last_command_and_output(lines, "python", KINDS)
    assert cmd == "for i in range(3): print(i)"
    assert out == "0\n1\n2"
