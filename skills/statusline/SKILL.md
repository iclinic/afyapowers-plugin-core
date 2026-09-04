---
name: statusline
description: Install or remove the afyapowers status line
disable-model-invocation: true
---
# /afyapowers-core:statusline — Install or Remove the afyapowers Status Line

You are installing (or removing) the afyapowers custom status line for the current user. It is installed **globally** in `~/.claude/settings.json` and applies to every project on this machine. Follow these steps exactly.

The status line shows, at the bottom of Claude Code: the afyapowers brand, model and context usage; the Jira ticket confirmed for the current session — resolved per-session by `session_id` from `~/.claude/afyapowers-core/sessions/`, and simply omitted until the user confirms one (or when working without a ticket); git branch/status, session cost and duration.

## Step 0: Preconditions

afyapowers-core requires Python 3.9+ at runtime. Check it is available:

```bash
command -v python3 >/dev/null && echo OK || echo MISSING
```

If the result is `MISSING`, tell the user: "O afyapowers requer Python 3.9+, que não está no seu PATH. Instale o Python 3.9 ou mais recente e rode `/afyapowers-core:statusline` novamente." Then **stop**.

## Step 1: Determine the Mode

- Default (no arguments, or words like "install", "on", "enable"): **install**.
- If the user asked for removal ("remove", "off", "uninstall", "disable", "remover", "desativar"): **remove**.

## Step 2: Run the Installer

Run the install script (`${CLAUDE_PLUGIN_ROOT}` is this plugin's root directory):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/statusline/scripts/install.py"
```

For removal, append `--remove`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/statusline/scripts/install.py" --remove
```

The script is idempotent. On install it writes the user-level `~/.claude/afyapowers-core/plugin-root` pointer and merges a `statusLine` entry into `~/.claude/settings.json`, preserving every other key. On removal it deletes only the `statusLine` key.

Confirm the output is `ok=true`. If it is `ok=false` or the command errors, report the error output to the user and **stop**. In particular, if the failure mentions invalid JSON in `~/.claude/settings.json`, tell the user the file needs to be fixed by hand first — the installer never overwrites a broken settings file.

## Step 3: Confirm to the User

After a successful **install**, tell the user:
- A status line foi instalada globalmente para o seu usuário em `~/.claude/settings.json` e vale para todos os projetos; aparece na próxima interação (ou nova sessão).
- Ela é atualizada automaticamente quando o plugin for atualizado (o hook `refresh-plugin-root` regrava o ponteiro `~/.claude/afyapowers-core/plugin-root` a cada início de sessão).
- O segmento de Jira mostra o ticket confirmado na sessão atual; até a confirmação (ou quando se trabalha sem ticket) ele simplesmente não aparece.
- Para removê-la: `/afyapowers-core:statusline remove`.

After a successful **remove**, tell the user the status line entry was removed from `~/.claude/settings.json` and the default footer returns on the next interaction.
