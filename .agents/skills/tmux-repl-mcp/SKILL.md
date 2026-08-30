---
name: tmux-repl-mcp
description: >
    How to drive Python, shell, Lisp, and other REPLs in tmux panes through
    tmux-repl-mcp MCP tools, including their current constraints and reliable
    workarounds.
---

# tmux-repl-mcp — driving REPLs in tmux panes

`tmux-repl-mcp` is an MCP server that interacts with a REPL in an already
running tmux pane. Its three tools inspect whether a **specific expected
REPL kind** is idle, retrieve the last complete command/output block, and
send one command while waiting for the REPL to become idle again.

```text
is_repl_ready(kind="python", pane="0")
execute_command(kind="python", command="2 + 3", pane="0", check=0.1)
get_last_command(kind="python", pane="0")
```

Use the MCP tools rather than raw `tmux capture-pane`, hand-written polling,
or guessed `sleep` intervals. They return only the command result instead of
flooding the conversation with pane history.

> **Scope:** This server can interact only with panes that already exist on
> the MCP server's default tmux server. It has no `socket`, `split-pane`,
> `send-keys`, `kill-pane`, custom per-call prompt, multi-line, or timeout
> parameter. If you need those capabilities, use the `muxxy` CLI or raw tmux
> deliberately; do not attempt to pass them to these MCP tools.

## The three tools

### `is_repl_ready`

Call this before a command when you need to choose or verify the REPL kind:

```text
is_repl_ready(kind="python", pane="0", max_lines=200)
```

It returns:

```json
{"kind": "python", "is_ready": true}
```

A result such as `{"kind": null, "is_ready": false}` means the pane's last
meaningful line did not match a recognized prompt. It may be busy, at an
unknown prompt, or merely have a prompt whose trailing space tmux removed.
Wait and retry rather than sending another command.

`kind` is **both an input and a check**: the tool reports `is_ready: true`
only when the detected kind equals the requested kind. It does not
auto-discover a kind for later calls.

### `execute_command`

Use this for normal single-line REPL evaluation:

```text
execute_command(
  kind="python",
  command="[print(i) for i in range(3)]",
  pane="0",
  max_lines=200,
  check=0.1
)
```

It:

1. Checks that the pane is idle and matches the requested `kind`.
2. Sends `command` followed by Enter through tmux.
3. Polls every `check` seconds until the same kind's prompt appears again.
4. Returns `status`, `last_command`, and `output`.

For a busy pane it returns `status: "error"` without sending the command.
For a prompt-kind mismatch it likewise returns an error and identifies the
detected kind. With no timeout parameter, an incomplete input or hung REPL
can wait indefinitely. Use a modest `check` such as `0.1`–`0.5` for an
interactive REPL, and do **not** use this tool for inputs that can leave the
REPL at a continuation prompt.

### `get_last_command`

Use it to read a result already present in a pane:

```text
get_last_command(kind="python", pane="0", max_lines=5000)
```

It searches the captured history for the last complete:

```text
prompt + command → output → prompt
```

It returns `{"last_command": null, "output": null}` when it cannot locate
that block. Increase `max_lines` for test suites, system loads, or other large
output. Do not infer that a `null` result means the command never ran: its
command line may simply have scrolled outside the requested capture window.

## Supported kinds and configuration

The server chooses from a fixed named-kind table. Pass the same `kind` to all
three tools:

| Kind | Intended prompt style | Notes |
|---|---|---|
| `python` | `>>> ` | In the current server build, tmux may trim the final space from a bare prompt, so this kind can fail to recognize an otherwise-idle standard Python pane. See the workaround below. |
| `ipython` | `In [n]: ` | The implementation's configured pattern differs from the README's advertised bracketed form; verify it against the actual pane before relying on it. |
| `bash`, `sh` | `user@host$ ` / `# ` | Matches a decorated shell prompt ending in `$` or `#`; a minimal bare `$ ` is not covered by the current pattern. |
| `zsh` | decorated `$` / `#` prompt | Same limitation for an overly minimal prompt. |
| `node` | `> ` | Standard Node REPL prompt. |
| `irb` | `irb(...):line:field> ` | Current pattern expects the older two-number prompt and may not accept modern `irb(main):001> `. |
| `iex` | `iex(n)> ` | Elixir IEx. |
| `lisp` | `* `, CCL `? `, package `NAME> `, `0]` debugger | Generic Common Lisp prompt family. |
| `goose` | Goose ready footer | Recognizes `🪿 Enter to send...`; this is a TUI interaction, not a language REPL. |

`sbcl` is **not** a current server kind. Use `kind="lisp"` for an SBCL pane.

To add or override named kinds before starting the MCP server, set
`TMUX_REPL_KINDS` to a JSON object mapping kind name to **one Python regular
expression string**:

```bash
export TMUX_REPL_KINDS='{
  "python-trimmed": "^>>>$",
  "janet": "^repl:[0-9]+:>"
}'
```

The mapping is merged over the built-ins, so it can also replace one. Unlike
muxxy, a server kind currently accepts one pattern only: it cannot model a
set of top-level plus continuation/debugger patterns under one name.
Restart the MCP server after changing the environment.

## Common languages

### Python

Use a single-line expression or statement only:

```text
is_repl_ready(kind="python", pane="0")
execute_command(kind="python", command="sum(range(10))", pane="0", check=0.1)
```

**Bare-prompt caveat:** Current `tmux-repl-mcp` captures panes without tmux's
`-N` trailing-space option, while the default Python pattern requires `^>>> `.
A normal idle Python prompt can be captured as `>>>` and reported unready.
This is a current server limitation, not evidence that Python is busy.

Start the server with a custom trimmed kind and use it consistently:

```bash
export TMUX_REPL_KINDS='{"python-trimmed":"^>>>$"}'
```

Then call the MCP tools with `kind="python-trimmed"`. This workaround is
appropriate for a standard bare prompt; if your prompt has a visible suffix,
make the regex match that actual suffix.

Do not send a multi-line `for`, `def`, `class`, `try`, or similar compound
statement through `execute_command`. The server sends one final Enter only,
so Python remains at `...` until a blank line is sent; the server does not
support a continuation-prompt set or automatic closing blank line. Use
`muxxy execute-command --lines ...`, or send raw tmux keys with a final blank
line and then use the MCP read tool once `>>>` returns.

### Shell

```text
execute_command(kind="bash", command="echo hi && sleep 2 && echo done", pane="0", check=0.2)
```

The server considers a shell ready only after the bare prompt returns. An
echoed command such as `user@host$ sleep 5` does not satisfy the server's
full-match readiness check, so do not send while it is still running.

### Common Lisp and SBCL

For SBCL, use `kind="lisp"`:

```text
is_repl_ready(kind="lisp", pane="0")
execute_command(kind="lisp", command="(+ 40 2)", pane="0", check=0.1)
```

A numbered SBCL debugger prompt such as `0]` is deliberately treated as a
ready command boundary. You can inspect state or select a restart:

```text
execute_command(kind="lisp", command="4", pane="0", check=0.1)
```

**Exit the debugger with the numbered restart printed by SBCL, not `(abort)`.**
`(abort)` runs in the debugger's evaluation context and does not reliably
return to the top level.

The current `lisp` regex recognizes `0]`, but **not nested debugger prompts**
such as `0[2]`, and does not include SBCL's `ldb> ` low-level debugger. In
those states the tools will report unready or wait forever. Use a custom
single-pattern kind only if it is sufficient for the exact state you need;
otherwise use muxxy, whose `sbcl` kind covers all those prompt styles.

`rlwrap` can echo multi-line pasted Lisp input without a prompt prefix. The
MCP parser can then return a stale `last_command` and history-mixed `output`.
Prefer single-line forms; after raw multi-line input, execute a small
single-line throwaway expression to restore a clean prompt boundary before
trusting `get_last_command`.

## Working within the MCP server's boundaries

### Targeting the right pane

Supply the tmux pane target every time it is not the default `"0"`:

```text
execute_command(kind="lisp", pane="mysession:2.1", command="(find-package :cl)")
```

One tool call operates on one pane. Repeat calls explicitly for multiple
panes. Be precise about the target: `"0"` means tmux's pane target syntax,
not necessarily “the pane next to me.”

### Visible versus headless work

The MCP server has no pane lifecycle tools. It cannot split a visible pane,
create a hidden session, target a non-default tmux socket, send Ctrl-C, or
clean up a pane. Therefore:

- **Existing visible REPL:** use these MCP tools directly, targeting its pane.
- **Need an agent-created visible pane:** use `muxxy split-pane` / `kill-pane`
  or raw tmux to create and remove it, then use MCP only if it lives on the
  default server and its prompt is supported.
- **Need isolated/headless work:** use muxxy with `--socket`, or raw tmux.
  `tmux-repl-mcp` cannot reach a dedicated tmux server.

Do not accidentally create or destroy user panes with raw tmux merely to work
around this server's missing lifecycle operations. Prefer muxxy when lifecycle
control is part of the task.

## Gotchas and reliable workarounds

1. **Expected kind is required.** Always provide `kind`; `is_repl_ready` does
   not have a discovery-only mode. If it says false, retry later or inspect
   the actual prompt before guessing another kind.
2. **Bare prompt matching is stricter than prompt-line extraction.** The
   readiness/wait loop uses a full regex match; a command echo is correctly
   busy, but prompt patterns that require an invisible trailing space can
   also fail. Use a custom regex that matches exactly the captured idle line.
3. **No timeout.** `execute_command` can block forever on an incomplete form,
   a prompt style it cannot recognize, or a hung REPL. Prefer short,
   guaranteed-complete commands; use muxxy for bounded `--timeout` behavior.
4. **No multi-line command interface.** Do not put embedded newlines in
   `command` and expect reliable execution/result extraction. Use muxxy's
   `--lines` or raw tmux with a terminating blank line instead.
5. **No raw/control-key send.** There is no MCP equivalent of `send-keys
   'C-c'`. Recover a stuck REPL manually or with muxxy/raw tmux.
6. **History depth defaults to 200.** Set `max_lines=5000` (or larger) before
   running a command that will print heavily. It applies to capture and
   subsequent extraction, but still cannot preserve a command line scrolled
   beyond the chosen window.
7. **Output parsing is prompt-based.** A prompt-looking line in ordinary
   output can be interpreted as a boundary because the current server uses
   regex search rather than strictly requiring a prefix. Keep custom regexes
   tightly anchored (`^`) and specific; do not use patterns that match a bare
   numeric result such as `1024`.
8. **Custom kinds are global environment configuration.** They are not a
   per-call option, accept a single regex, and require an MCP-server restart.
   Plan the prompt styles up front.
9. **Read-only versus write permissions.** `is_repl_ready` and
   `get_last_command` only inspect tmux state and are appropriate to always
   allow. `execute_command` sends input and should require user approval if
   your MCP client supports per-tool permissions.

## When to choose muxxy instead

Use `tmux-repl-mcp` when an already configured MCP server can safely drive an
existing pane with a supported single-prompt kind. Choose **muxxy** when you
need any of the following:

- a custom `--prompt` on one invocation or several prompt styles at once;
- supported `sbcl` and `janet` presets, nested SBCL debugger and `ldb>`
  prompts, or current modern-IRB support;
- `execute-command --lines` for a multi-line block and a 60-second default
  timeout (or explicit `--timeout 0`);
- a non-default tmux server via `--socket`;
- `split-pane`, setup commands/sleeps, raw `send-keys` including `C-c`, or
  `kill-pane` cleanup;
- default 5000-line history, trailing-space-safe capture (`-N`), prompt
  safety warnings, or sent-command recovery for rlwrap echoes;
- YAML CLI output suitable for scripts.
