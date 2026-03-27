# tmux-repl-mcp

An [MCP](https://modelcontextprotocol.io/) server for interacting with a REPL
running inside a [tmux](https://github.com/tmux/tmux) pane.

Use it with [Goose](https://github.com/block/goose), Cursor, or any other MCP
client to send commands to a running REPL and read back the output with perfect
timing — no more guessing how long to `sleep`.

---

## Features

| Tool | Description |
|---|---|
| `is_repl_ready` | Check whether the pane is showing a known REPL prompt |
| `get_last_command` | Read the last command and its output from the pane history |
| `execute_command` | Send a command, wait for the REPL to finish, return output |

---

## Quick start

```bash
uvx tmux-repl-mcp
```

### Goose configuration

```yaml
extensions:
  tmux-repl-mcp:
    type: stdio
    cmd: uvx
    args:
      - tmux-repl-mcp
    enabled: true
```

---

## Tools

### `is_repl_ready`

```
is_repl_ready(pane="0", max_lines=50)
```

Returns `{"kind": "<kind>"}` if a known REPL prompt is detected on the last
non-empty line of the pane, or `{"kind": null}` if the pane is busy or shows
an unrecognised prompt.

### `get_last_command`

```
get_last_command(kind, pane="0", max_lines=200)
```

Looks back through up to `max_lines` lines of the pane history for a complete
prompt→command→output→prompt block and returns:

```json
{"last_command": "...", "output": "..."}
```

Both values are `null` when no complete block is found or the REPL is still
running.

### `execute_command`

```
execute_command(command, kind, pane="0", max_lines=200, check=2.0)
```

1. Verifies the REPL is ready and of the expected `kind`.
2. Sends `command` to the pane via `tmux send-keys`.
3. Waits (polling every `check` seconds) until the REPL prompt reappears.
4. Returns `{"status": "ok", "last_command": "...", "output": "..."}`.

---

## REPL kinds

The following kinds are built-in:

| Kind | Prompt pattern |
|---|---|
| `python` | `^>>> ` |
| `ipython` | `^In \[\d+\]: ` |
| `bash` | `[\$\#]\s*$` |
| `zsh` | `[\$\#%]\s*$` |
| `sh` | `[\$\#]\s*$` |
| `lisp` | `^\*\s*$` / `^…>\s*$` / `^\d+\]\s*$` |
| `sbcl` | `^\*\s*$` / `^\d+\]\s*$` |
| `node` | `^> ` |
| `irb` | `^irb\(.*\):\d+:\d+> $` |
| `iex` | `^iex\(\d+\)> $` |

### Adding custom kinds

Set the `TMUX_REPL_KINDS` environment variable to a JSON object:

```bash
export TMUX_REPL_KINDS='{"myrepl": "^myrepl> "}'
```

Entries here are merged on top of the built-in defaults, so existing kinds can
also be overridden.

---

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest -v
```

---

## Goose permission tips

Because `is_repl_ready` and `get_last_command` only read tmux state, they are
safe to mark as **Always Allow** in Goose.  Reserve **Ask User** for
`execute_command` since it writes to your REPL.
