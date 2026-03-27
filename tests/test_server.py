"""
Unit tests for the MCP tool functions in tmux_repl_mcp.server.
All tmux subprocess calls are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock

from tmux_repl_mcp import server as srv
from tmux_repl_mcp.core import DEFAULT_KINDS


PYTHON_IDLE = ">>> 1 + 1\n2\n>>> print('hi')\nhi\n>>> \n"
PYTHON_IDLE_LINES = PYTHON_IDLE.split("\n")


def _mock_capture(content: str):
    """Return a mock for capture_pane that returns *content*."""
    return patch("tmux_repl_mcp.server.capture_pane", return_value=content)


# ---------------------------------------------------------------------------
# is_repl_ready
# ---------------------------------------------------------------------------


def test_is_repl_ready_python():
    with _mock_capture(PYTHON_IDLE):
        result = srv.is_repl_ready(pane="0")
    assert result == {"kind": "python"}


def test_is_repl_ready_busy():
    with _mock_capture("Running something...\n"):
        result = srv.is_repl_ready(pane="0")
    assert result == {"kind": None}


def test_is_repl_ready_lisp():
    # SBCL / generic CL prompts are matched by the "lisp" kind.
    content = "* (+ 1 2)\n3\n* \n"
    with _mock_capture(content):
        result = srv.is_repl_ready(pane="1")
    assert result == {"kind": "lisp"}


# ---------------------------------------------------------------------------
# get_last_command
# ---------------------------------------------------------------------------


def test_get_last_command_python():
    with _mock_capture(PYTHON_IDLE):
        result = srv.get_last_command(kind="python", pane="0")
    assert result["last_command"] == "print('hi')"
    assert result["output"] == "hi"


def test_get_last_command_repl_not_ready():
    with _mock_capture("Still running...\n"):
        result = srv.get_last_command(kind="python", pane="0")
    assert result == {"last_command": None, "output": None}


def test_get_last_command_no_prior_prompt():
    # Only one prompt – no complete block.
    with _mock_capture(">>> \n"):
        result = srv.get_last_command(kind="python", pane="0")
    assert result == {"last_command": None, "output": None}


# ---------------------------------------------------------------------------
# execute_command
# ---------------------------------------------------------------------------


def test_execute_command_success():
    after_send = ">>> 1 + 1\n2\n>>> print('hi')\nhi\n>>> \n"

    call_count = 0

    def fake_capture(pane, max_lines):
        nonlocal call_count
        call_count += 1
        # First call: pre-flight / sentinel (idle prompt visible).
        # Subsequent calls: pane has changed and settled.
        if call_count == 1:
            return PYTHON_IDLE         # pre-flight check
        elif call_count == 2:
            return PYTHON_IDLE         # sentinel capture (after send-keys)
        elif call_count == 3:
            return after_send + ">>> 2 + 2\n4\n>>> \n"  # changed! phase-1 exit
        else:
            return after_send + ">>> 2 + 2\n4\n>>> \n"  # idle – phase-2 exit

    with patch("tmux_repl_mcp.server.capture_pane", side_effect=fake_capture), \
         patch("tmux_repl_mcp.server.send_keys") as mock_send, \
         patch("tmux_repl_mcp.server.wait_and_capture",
               return_value=(after_send + ">>> 2 + 2\n4\n>>> \n").split("\n")):
        result = srv.execute_command(
            command="2 + 2",
            kind="python",
            pane="0",
            max_lines=200,
            check=0.0,
        )

    assert result["status"] == "ok"
    assert result["last_command"] is not None


def test_execute_command_repl_not_ready():
    with _mock_capture("still running...\n"):
        result = srv.execute_command(
            command="(+ 1 2)", kind="sbcl", pane="0"
        )
    assert result["status"] == "error"
    assert "not ready" in result["reason"]


def test_execute_command_wrong_kind():
    # Pane shows a Python prompt but caller expects sbcl.
    with _mock_capture(PYTHON_IDLE):
        result = srv.execute_command(
            command="(+ 1 2)", kind="sbcl", pane="0"
        )
    assert result["status"] == "error"
    assert "python" in result["reason"]
