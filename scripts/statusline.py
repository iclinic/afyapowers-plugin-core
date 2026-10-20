#!/usr/bin/env python3
"""afyapowers-core status line for Claude Code.

Reads the session JSON Claude Code pipes to stdin and prints up to three
lines: brand / model / context usage, Jira ticket (confirmed for this session,
resolved by `session_id`) + git status, and session cost/duration. Installed into the user's
`~/.claude/settings.json` by the `/afyapowers-core:statusline` skill,
which resolves this script through the `~/.claude/afyapowers-core/plugin-root`
pointer maintained by the refresh-plugin-root hook (the install path
changes with the plugin version, the account and the distribution channel).

Every field is optional: absent segments are dropped, empty lines are not
printed, and any unexpected error results in silence rather than a
traceback — a non-zero exit or stderr noise would blank the status line.
The single `git status` subprocess is the only non-trivial cost.
"""

import json
import os
import subprocess
import sys

# The session's ticket comes from hooks/session_store.py, the same module the
# hooks use. Guarded: if it cannot be imported, only the ticket segment goes.
sys.dont_write_bytecode = True  # no __pycache__ inside the installed plugin
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
try:
    import session_store as store
except Exception:
    store = None

RESET = "\033[0m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
AFYA_PINK = "\033[38;2;196;4;84m"
JIRA_BLUE = "\033[38;5;33m"

SEPARATOR = DIM + " │ " + RESET

GIT_TIMEOUT = 1.5


def read_stdin_json():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_cwd(data):
    workspace = data.get("workspace") or {}
    return (
        workspace.get("current_dir")
        or workspace.get("project_dir")
        or os.getcwd()
    )


def seg_brand():
    # No version: the afyapowers family ships as multiple plugins, each with
    # its own version, so a single number here would be misleading.
    return "%s⚡ afyapowers%s" % (AFYA_PINK, RESET)


def seg_model(data):
    name = (data.get("model") or {}).get("display_name")
    return "\U0001f916 %s" % name if name else None


def seg_context(data):
    pct = (data.get("context_window") or {}).get("used_percentage")
    if pct is None:
        return None
    pct = int(pct)
    color = RED if pct >= 90 else YELLOW if pct >= 70 else GREEN
    return "%s\U0001f9e0 %d%%%s" % (color, pct, RESET)


def seg_jira(session_id):
    # Per session, not per project: two sessions in the same folder can be on
    # different tickets. Hidden until answered and when there is no ticket.
    if store is None:
        return None
    key = store.read_ticket(session_id)
    if key in (None, store.NO_TICKET):
        return None
    return "%s\U0001f3af %s%s" % (JIRA_BLUE, key, RESET)


def seg_git(cwd):
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v1", "--branch"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    branch = None
    staged = 0
    modified = 0
    for line in result.stdout.splitlines():
        if line.startswith("## "):
            branch = line[3:].split("...")[0].strip()
            # git prints these instead of a plain branch name.
            for prefix in ("No commits yet on ", "Initial commit on "):
                if branch.startswith(prefix):
                    branch = branch[len(prefix):]
            if branch == "HEAD (no branch)":
                branch = "detached"
        elif line.startswith("??"):
            modified += 1
        elif len(line) >= 2:
            if line[0] in "MADRC":
                staged += 1
            if line[1] != " ":
                modified += 1
    if not branch:
        return None
    color = GREEN if staged == 0 and modified == 0 else YELLOW
    parts = ["%s\U0001f33f %s%s" % (color, branch, RESET)]
    if staged:
        parts.append("%s+%d%s" % (GREEN, staged, RESET))
    if modified:
        parts.append("%s~%d%s" % (YELLOW, modified, RESET))
    return " ".join(parts)


def seg_cost(data):
    cost = (data.get("cost") or {}).get("total_cost_usd")
    if cost is None:
        return None
    return "%s\U0001f4b0 $%.2f%s" % (GREEN, cost, RESET)


def seg_duration(data):
    ms = (data.get("cost") or {}).get("total_duration_ms")
    if ms is None:
        return None
    seconds = int(ms) // 1000
    if seconds < 60:
        text = "%ds" % seconds
    elif seconds < 3600:
        text = "%dm" % (seconds // 60)
    else:
        text = "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "⏱ %s" % text


def _safe(builder, *args):
    """One broken segment must not blank the whole status line."""
    try:
        return builder(*args)
    except Exception:
        return None


def main():
    data = read_stdin_json()
    cwd = resolve_cwd(data)

    lines = [
        [_safe(seg_brand), _safe(seg_model, data), _safe(seg_context, data)],
        [_safe(seg_jira, data.get("session_id")), _safe(seg_git, cwd)],
        [_safe(seg_cost, data), _safe(seg_duration, data)],
    ]
    for segments in lines:
        segments = [s for s in segments if s]
        if segments:
            print(SEPARATOR.join(segments))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
