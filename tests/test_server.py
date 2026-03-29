"""
Unit tests for the MCP tool functions in tmux_repl_mcp.server.
All tmux subprocess calls are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock

from tmux_repl_mcp import server as srv

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
        result = srv.is_repl_ready(kind="python", pane="0")
    assert result == {"kind": "python", "is_ready": True}


def test_is_repl_ready_busy():
    with _mock_capture("Running something...\n"):
        result = srv.is_repl_ready(kind="python", pane="0")
    assert result == {"kind": None, "is_ready": False}


def test_is_repl_ready_lisp():
    # SBCL / generic CL prompts are matched by the "lisp" kind.
    content = "* (+ 1 2)\n3\n* \n"
    with _mock_capture(content):
        result = srv.is_repl_ready(kind="lisp", pane="1")
    assert result == {"kind": "lisp", "is_ready": True}


def test_is_repl_ready_lisp_debugger():
    # When in debugger, should return is_ready=True
    content = "* (/ 1 0)\nerror\n0] \n"
    with _mock_capture(content):
        result = srv.is_repl_ready(kind="lisp", pane="0")
    assert result == {"kind": "lisp", "is_ready": True}


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

    with patch("tmux_repl_mcp.server.capture_pane", return_value=PYTHON_IDLE), \
         patch("tmux_repl_mcp.server.send_keys"), \
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


def test_execute_command_lisp_debugger():
    # Test that execute_command returns ok status even when error occurs
    # The output includes the command line and error message
    debugger_output = "* (/ 1 0)\ndebugger invoked on a DIVISION-BY-ZERO\n0] \n"

    with patch("tmux_repl_mcp.server.capture_pane", return_value="* \n"), \
         patch("tmux_repl_mcp.server.send_keys"), \
         patch("tmux_repl_mcp.server.wait_and_capture",
               return_value=debugger_output.split("\n")):
        result = srv.execute_command(
            command="(/ 1 0)",
            kind="lisp",
            pane="0",
            max_lines=200,
            check=0.0,
        )

    # Status should be "ok" - the tool worked correctly, the REPL just entered debugger
    assert result["status"] == "ok"
    # When in debugger, we should extract the command and error output
    assert result["last_command"] == "(/ 1 0)"
    if result["output"] is not None:
        assert "debugger invoked" in result["output"]
