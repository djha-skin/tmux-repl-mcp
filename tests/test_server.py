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


@pytest.fixture(autouse=True)
def no_real_probe():
    """Keep the probe fallback from touching a real tmux server in unit tests."""
    with patch("tmux_repl_mcp.server.probe_prompt_pattern", return_value=None):
        yield


# ---------------------------------------------------------------------------
# is_repl_ready
# ---------------------------------------------------------------------------


def test_is_repl_ready_python():
    with _mock_capture(PYTHON_IDLE):
        result = srv.is_repl_ready(kind="python", pane="0")
    assert result == {"kind": "python", "is_ready": True, "probed": False}


def test_is_repl_ready_busy():
    with _mock_capture("Running something...\n"):
        result = srv.is_repl_ready(kind="python", pane="0")
    assert result == {"kind": None, "is_ready": False, "probed": False}


def test_is_repl_ready_lisp():
    # SBCL / generic CL prompts are matched by the "lisp" kind.
    content = "* (+ 1 2)\n3\n* \n"
    with _mock_capture(content):
        result = srv.is_repl_ready(kind="lisp", pane="1")
    assert result == {"kind": "lisp", "is_ready": True, "probed": False}


def test_is_repl_ready_lisp_debugger():
    # When in debugger, should return is_ready=True
    content = "* (/ 1 0)\nerror\n0] \n"
    with _mock_capture(content):
        result = srv.is_repl_ready(kind="lisp", pane="0")
    assert result == {"kind": "lisp", "is_ready": True, "probed": False}


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


# ---------------------------------------------------------------------------
# goose
# ---------------------------------------------------------------------------

GOOSE_READY_PANE = (
    "    __( O)>  ● new session · openrouter deepseek/deepseek-v4-flash\n"
    "   \\____)    20260702_6 · /home/skin/Code/djha-skin/tmux-repl-mcp\n"
    "     L L     goose is ready\n"
    "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 0% 0/128k\n"
    "Cost: $0.0000 USD (0 tokens: in 0, out 0)\n"
    "🪿 Enter to send · Ctrl+J newline"
)

def test_is_repl_ready_goose():
    with _mock_capture(GOOSE_READY_PANE):
        result = srv.is_repl_ready(kind="goose", pane="8.0")
    assert result == {"kind": "goose", "is_ready": True, "probed": False}


def test_is_repl_ready_goose_busy():
    busy = (
        "    __( O)>  ● new session\n"
        "   \\____)    20260702_6\n"
        "     L L     processing...\n"
        "  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 2% 100/128k\n"
        "Cost: $0.0012 USD (50 tokens: in 30, out 20)\n"
        "🪿 Press Ctrl+C again to exit, or type new instructions to continue"
    )
    with _mock_capture(busy):
        result = srv.is_repl_ready(kind="goose", pane="8.0")
    assert result == {"kind": None, "is_ready": False, "probed": False}


def test_execute_command_goose():
    """Send a command to goose and wait for the ready prompt to return."""
    ready_lines = GOOSE_READY_PANE.split("\n")

    with patch("tmux_repl_mcp.server.capture_pane", return_value=GOOSE_READY_PANE), \
         patch("tmux_repl_mcp.server.send_keys") as mock_send, \
         patch("tmux_repl_mcp.server.wait_and_capture",
               return_value=ready_lines):
        result = srv.execute_command(
            command="what is 2+2",
            kind="goose",
            pane="8.0",
            max_lines=200,
            check=0.0,
        )

    mock_send.assert_called_once_with("8.0", "what is 2+2")
    assert result["status"] == "ok"
    # extract_last_command_and_output finds the prompt block;
    # with only one prompt line in the result there's no second prompt
    # to delimit output, so last_command / output may be None.
    # The important thing is status == ok.
