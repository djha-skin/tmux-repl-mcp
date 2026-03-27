"""tmux-repl-mcp – MCP server for interacting with a REPL via tmux."""

from tmux_repl_mcp.server import mcp


def main() -> None:
    """Entry-point used by ``uvx tmux-repl-mcp``."""
    mcp.run()
