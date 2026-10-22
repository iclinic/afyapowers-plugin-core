"""Where afyapowers-core keeps its state, how a session's ticket is read, and
the helpers the hooks share.

The single definition of the contract between the hooks: track-jira-ticket
writes the session's ticket, emit-session-context and the status line read it.
The config dir, the session folder, the ticket file and the key format live
here, so a change cannot reach one side and miss the other — the failure that
would leave the core silently mute. The git helper lives here too, so its
error handling is one copy. Files used by a single hook (last-send.json,
context-sent.json, ticket-asked) and the status line pointer are defined where
they are used.

Not a hook: it is not registered in hooks.json. The hooks import it from their
own folder (Python puts a script's folder on the import path); the status line
adds this folder to the path first. Every importer guards the import, so a
broken module ends the hook in silence like any other error.

    <config>/afyapowers-core/                     state root (last-send.json)
    <config>/afyapowers-core/sessions/<id>/       one folder per session
    <config>/afyapowers-core/sessions/<id>/jira-ticket
        `ABC-123`, or the literal `none` for "no ticket"

`<config>` is CLAUDE_CONFIG_DIR when set (Cowork sets one per session), else
`~/.claude`.
"""

import os
import re
import subprocess
from pathlib import Path

# The key format, in one place: the recorded ticket must match it whole, and
# KEY_IN_TEXT_RE finds it inside a branch name or an answer. ASCII only, so a
# key found in text always passes JIRA_KEY_RE once upper-cased.
_KEY = r"[A-Z][A-Z0-9]+-[0-9]+"
JIRA_KEY_RE = re.compile(rf"^{_KEY}$", re.ASCII)
# Both ends must sit on a word boundary: no letter or digit right before the
# key, and after the number no letter, no digit and no `.` followed by a digit.
# That keeps `feat/DEVEX-90-login`, `fix/DC-12465/ad` and a typed "DEVEX-97."
# but drops `claude/jolly-lovelace-8f488e` (Claude Code worktrees),
# `release-1.135.0` (versions) and `revert-5e9a3c44` (hashes).
KEY_IN_TEXT_RE = re.compile(
    rf"(?<![A-Z0-9]){_KEY}(?![A-Z0-9])(?!\.[0-9])", re.IGNORECASE | re.ASCII
)
TICKET_FILE = "jira-ticket"
NO_TICKET = "none"


def config_dir():
    """`${CLAUDE_CONFIG_DIR:-~/.claude}`; None when HOME cannot be resolved
    (expanduser then returns the literal `~`, which would otherwise create a
    `~` folder relative to the cwd)."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    if not base or base.startswith("~"):
        return None
    return Path(base)


def state_dir():
    """`<config>/afyapowers-core`, or None."""
    base = config_dir()
    return base / "afyapowers-core" if base else None


def sessions_root():
    """`<config>/afyapowers-core/sessions`, or None."""
    state = state_dir()
    return state / "sessions" if state else None


def safe_name(value):
    """Any character outside letters, digits, `-` and `_` becomes `-`."""
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(value))


def session_dir(session_id):
    """`<config>/afyapowers-core/sessions/<id>`, or None without a session."""
    root = sessions_root()
    if root is None or not session_id:
        return None
    safe = safe_name(session_id)
    return root / safe if safe else None


def ticket_file(session_id):
    sdir = session_dir(session_id)
    return sdir / TICKET_FILE if sdir else None


def read_ticket(session_id):
    """The session's answer: a validated key (upper case), `none` ("no
    ticket"), or None while nobody has answered (missing, empty or garbage)."""
    path = ticket_file(session_id)
    if path is None:
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if raw.lower() == NO_TICKET:
        return NO_TICKET
    raw = raw.upper()
    return raw if JIRA_KEY_RE.match(raw) else None


def git(cwd, *args, timeout):
    """`git -C cwd args...` stdout, stripped; None on failure, timeout or empty
    output. Each caller passes the timeout its hook can afford."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
