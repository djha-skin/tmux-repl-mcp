# TMUX REPL MCP Design Document

## Overview

TMUX REPL MCP is an MCP server for interacting with a REPL via TMUX. It may be
used together with the Goose CLI or any other MCP client, such as Cursor, to
interact with REPL sessions in a meaningful way through TMUX sessions.

## Motivation

The primary goal is to create a tool that can send commands to a REPL running in
a TMUX session, allowing for seamless interaction and automation. This will be
particularly useful for developers who want to manage their REPL sessions more
efficiently. I use the Goose CLI tool to interact with AI agents. This tool
allows me to set fine grained permissions for different actions that a given MCP
tool can perform. I like to set "Always Allow" permissions for actions that read
state and "Ask User" permissions for actions that write state. I wish to create
different actions inside this tool that I commonly use to interact with my REPL
so that the read actions can be set to "Always Allow".

In addition, there are other points of friction which are created by just using
raw tmux commands. The AI agent is always guessing at how long to wait before
grabbing the tmux window and the guesses vary widely, slowing down interaction,
e.g. `sleep 2 && tmux ...`, `sleep 50 && tmux ...`. Then, when the AI grabs a
region of the screen, too much or too little is grabbed, leading either to AI
confusion and hallucination or repeated grabs, chewing through token count.

We need to create an accurate way to determine when the REPL is ready for input
and when it has finished processing input.

## Description

The tool will have three actions in the initial release:

- `execute_command`: Executes an arbitrary command in the REPL and returns the
  output. This command is complicated, as it does not simply rely on returning
  or exiting processes but determining if the process is done based on tmux pane
  grabs alone. This is the most flexible way and the way which will allow us to
  run arbitrary REPLs in the tmux window. It is a complicated tool to implement,
  and has its own design section later on for that reason.

- `get_last_command`: Gets the output of the last command executed in the
  REPL. It is anticipated (at least in the author's use case) that this tool
  will be given the "Always Allow" permission in the Goose CLI.

- `is_repl_ready`: Checks if the last line in the configured TMUX pane matches
  one of the configured regular expressions corresponding to a REPL prompt.

## Discussion

This design, that of the three tools above, already presents several ripe places
for abstraction. `is_repl_ready` will basically expose a function of the same
name and functionality that will be used in the `execute_command` tool. The same
goes for the `get_last_command` tool.

### `is_repl_ready`

The `is_repl_ready` tool will take only one argument, the `pane` to check (which
can be left unspecified, in which case it should default [the pane] to `0`). It
will return an object. A member of that object will be named `kind`. Its value
will be the kind of REPL that is ready, if any. If no REPL is ready, it will be
`nil`.

### `get_last_command`

The `get_last_command` tool will take three arguments. First, the `pane`
to check (which can be left unspecified, in which case it should default [the
pane] to `0`). Second, the `kind` of REPL for which to check. Finally, the
`max_lines` or maximum number of lines to check "backwards" up the history for
all the lines given. It will return an object. A
member of that object will be named `output`. Its value will be the output of
the last command executed in the REPL, if any. Another member will be named
`last-command`. Its value will be the last command executed in the REPL, if any.
If no command is found, both `output` and `last-command` will be `nil`.

This function will operate by first checking if the REPL is ready using the
`is_repl_ready` tool and returning early with `nil` values if it is not. If the
REPL is ready, it will then check the history of the pane for the last
`max_lines` lines for a line that matches the expected prompt for the given
`kind` of REPL. If it finds such a line, it will then check the lines after that
line for a line that matches the expected prompt for the given `kind` of REPL.
If it finds such a line, it will return the lines between those two lines as the
`output` and the contents of the line matching the first prompt as the
`last-command`, only without those characters matching the prompt itself. If it
does not find such a line, it will return `nil` values for both `output` and
`last-command`.

### `execute_command`

As far as `execute_command` goes, the algorithm should be pretty simple. It
takes four arguments: the `command` to execute, the `kind` of REPL which is
expected, and the `pane` in which the REPL is running (which can be left
unspecified, in which case it should default [the pane] to `0`), `max_lines`, or
the maximum number of lines to check for the command output, defaulting to 200,
and finally `check`, or the number of seconds to wait between checks, defaulting
to 2.

First, it calls `is_repl_ready`. If the repl is ready and its `kind` matches
what is given, the tools proceeds; otherwise it returns an object indicating
what happened.

It starts running after that. First, it sends the `command` to the REPL in the
given `pane` using `tmux send-keys`. Then, it captures an initial picture of the
pane and stores the pane capture (or in other words the last `max_line`s of the
pane) into a variable. Suppose this variable's name is `sentinel`. Then, it
enters a start-state monitoring loop.

During the start-state monitoring loop, every `check` seconds, it pulls the pane's last
`max_line`s. If the pane's last `max_lines` match perfectly with those inside
`sentinel`, then it means the REPL has not processed the command yet, so it
keeps waiting. If the pane's last `max_lines` do not match perfectly with those
inside `sentinel`, then it means the REPL has started processing the command, so
it breaks out of the start-state monitoring loop and enters the end-state
monitoring loop.

Every `check` seconds, it pulls the pane's last line. If the last line matches
the REPL prompt for the given `kind` of REPL, then it means the REPL is ready again, so it breaks out of the
end-state monitoring loop and enters the final check. If the last line does not
match, then there is still more waiting to be done, so it keeps waiting.

Once all this is done, it simply (more or less) calls the `get_last_command`
tool with the given `kind` of REPL and the given `max_lines` to check for the
command output.

## Design Decisions

### Build Target

The end goal will be a `uv` package that can be configured in the goose config,
e.g. `uvx tmux-repl-mcp`, which will then be used in the Goose CLI to interact
with the MCP server. Thus, this project will be using Python.

## Conclusion

Hopefully we can have a tool that works with Goose and is easy to use for
interacting with all types of REPLs, including Lisp implementations, Lisp
debuggers, Python shells, etc.

