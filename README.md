# afyapowers-core

Plugin base da família **afyapowers**. Pergunta e registra o ticket do Jira de cada sessão, envia à telemetria o contexto da sessão (ticket, repositório, branch), injeta a diretiva de idioma pt-BR nas skills afyapowers, gera o histórico das conversas em HTML e mostra uma status line.

## Onde roda

| Produto | Canais | O que funciona |
|---|---|---|
| Claude Code | terminal, extensão de IDE, aba Code do app | tudo |
| Cowork | app, na máquina | pergunta do ticket em texto e idioma |
| Cowork | nuvem | nenhum hook roda |
| Chat, Office, Claude Tag | todos | nenhum hook roda |

## Instalação

Distribuído pelo console da Anthropic como plugin obrigatório nas contas da Afya: chega sozinho, sem instalação manual. Requisito: Python 3.9+ no PATH (`python3`).

## Hooks

Os caminhos com `~/.claude` usam a pasta de `CLAUDE_CONFIG_DIR` quando essa variável está definida, como no Cowork. A exceção é o ponteiro da status line, no hook 5.

| # | Hook | Gatilho | O que faz |
|---|---|---|---|
| 1 | `track-jira-ticket` | `UserPromptSubmit`, `PostToolUse` do `AskUserQuestion` | pergunta e grava o ticket da sessão |
| 2 | `emit-session-context` | `UserPromptSubmit` | envia o contexto da sessão à telemetria |
| 3 | `enforce-language` | `PreToolUse` do `Skill`, `UserPromptExpansion` | injeta a diretiva de idioma pt-BR nas skills afyapowers |
| 4 | `render-history` | `SessionEnd` | gera o histórico da conversa em HTML |
| 5 | `refresh-plugin-root` | `SessionStart` | atualiza o ponteiro da status line |

### 1. track-jira-ticket — ticket da sessão

**Gatilhos:** `UserPromptSubmit` e `PostToolUse` do `AskUserQuestion`.

**O que faz:** garante que cada sessão tenha um ticket do Jira, ou a indicação de que não há ticket.

- **Pergunta.** No primeiro prompt da sessão, o hook instrui o modelo a perguntar o ticket:

  | Situação | Como a pergunta aparece |
  |---|---|
  | A branch tem uma chave no nome, como `feat/DEVEX-90-login` | caixa **Ticket Jira** com duas opções: a chave da branch e **Sem ticket**. Outro ticket vai no campo de texto livre da caixa |
  | A branch não tem chave, não há repositório, ou é o Cowork | pergunta em texto, no chat |

- **Resposta.** Vale uma chave do Jira, como `ABC-123`, ou "sem ticket", escolhida ou digitada na caixa, ou digitada como prompt com até 30 caracteres, depois da pergunta. A chave pode estar em qualquer ponto da resposta: "é o DEVEX-97" vale como DEVEX-97. Se a resposta não trouxer nenhuma das duas, o modelo repete "O id do ticket não veio. Digite o ticket, por exemplo: 'ABC-123', ou responda 'sem ticket'." até vir uma resposta válida.
- **Depois da resposta.** O ticket fica gravado e não muda mais nessa sessão. No mesmo momento, o hook apaga as pastas de sessões paradas há mais de 7 dias e dispara o envio do contexto da sessão (hook 2). A cada prompt seguinte, o hook informa o ticket ao modelo, que pode usá-lo em commits e pull requests e não pergunta de novo.

**Grava:** em `~/.claude/afyapowers-core/sessions/<session_id>/`:

- `jira-ticket`: a chave, ou `none` para "sem ticket";
- `ticket-asked`: indica que a pergunta já foi feita nesta sessão.

---

### 2. emit-session-context — contexto na telemetria

**Gatilhos:** `UserPromptSubmit`, e chamado pelo `track-jira-ticket` ao gravar o ticket.

**O que faz:** envia o evento `afyapowers-core.session_context` (log OTLP) quando o ticket fica conhecido e, depois, a cada mudança de repositório ou branch. Prompts sem mudança não enviam nada. O envio roda em processo filho; um envio que falha é repetido no prompt seguinte. Sem destino configurado, não envia nada. É o caso do Cowork: o destino vem das variáveis `AFYAPOWERS_OTLP_LOGS_*`, definidas na política do Claude Code, e o Cowork não carrega essa política nas sessões dele.

**Atributos:** `event.name`, `session.id`, `prompt.id`, `hook.event`, `jira.key` (string vazia `""` = sem ticket), `git.repo`, `git.branch`, `git.commit`, `host.name` e, com feature ativa do afyapowers-dev, `afyapowers_dev.current_phase`. E-mail e versões dos plugins não vão no evento: vêm da telemetria nativa da mesma sessão, pelo `session.id`.

**Grava:**

- `~/.claude/afyapowers-core/sessions/<session_id>/context-sent.json`: repositório e branch do último envio confirmado;
- `~/.claude/afyapowers-core/last-send.json`: resultado do último envio.

---

### 3. enforce-language — idioma pt-BR

**Gatilhos:** `PreToolUse` do `Skill` e `UserPromptExpansion`.

**O que faz:** injeta a diretiva de idioma pt-BR quando uma skill `afyapowers*:` é invocada.

**Grava:** nada.

---

### 4. render-history — histórico das conversas

**Gatilhos:** `SessionEnd`.

**O que faz:** gera o histórico da conversa em HTML, um arquivo por sessão e um `index.html`.

**Grava:** em `.afyapowers/history/claude/`, quando o projeto já tem `.afyapowers/`, e acrescenta `history/` ao `.gitignore` dessa pasta; senão, em `~/.claude/afyapowers-core/history/<projeto>/claude/`.

---

### 5. refresh-plugin-root — ponteiro da status line

**Gatilhos:** `SessionStart`.

**O que faz:** registra o caminho da versão instalada do plugin, que a status line usa, e avisa o modelo se o `python3` não estiver no PATH.

**Grava:** `~/.claude/afyapowers-core/plugin-root`.

---

## Status line

Ligada pela política do console nas contas da Afya; só sai se for removida da política. Fora delas: `/afyapowers-core:statusline` (remover: `/afyapowers-core:statusline remove`). Mostra marca, modelo, contexto, ticket, git, custo e duração. Requer Python 3.9+.

## Configuração da telemetria

No bloco `env` da política do Claude Code, no console, em cada conta:

| Variável | Valor |
|---|---|
| `AFYAPOWERS_OTLP_LOGS_ENDPOINT` | URL completa do endpoint de logs OTLP, usada como está |
| `AFYAPOWERS_OTLP_LOGS_HEADERS` | `chave=valor,chave=valor`, o mesmo valor de `OTEL_EXPORTER_OTLP_LOGS_HEADERS` |
| `AFYAPOWERS_OTLP_LOGS_PROTOCOL` | `http/protobuf` (padrão) ou `http/json` |

O Claude Code apaga as `OTEL_*` do ambiente dos hooks; por isso o core usa variáveis próprias. As variáveis precisam estar na política **antes** de publicar uma versão do core que as lê.

## Garantias

- Nenhum hook bloqueia a sessão: qualquer erro termina com `exit 0`.
- Nenhum hook cria `.afyapowers/` no projeto. O estado fica em `~/.claude/afyapowers-core/`, e o histórico vai para `.afyapowers/history/` quando o projeto já tem essa pasta.
- O envio do evento roda em processo filho. Os outros hooks fazem só operações curtas, com tempo limite.

## Diagnóstico de uma máquina sem `session_context`

1. `ls ~/.claude/afyapowers-core/sessions/$(ls -t ~/.claude/afyapowers-core/sessions | head -1)/` — mostra a pasta da sessão mais recente. Sem `jira-ticket`, a pessoa ainda não respondeu à pergunta, e nada é enviado antes disso.
2. `cat ~/.claude/afyapowers-core/last-send.json` — data, endpoint, status, erro e último sucesso. Erro `no AFYAPOWERS_OTLP_LOGS_ENDPOINT`: a política não chegou; reiniciar o Claude Code ou refazer o login.
3. Numa sessão, `! env | grep -c '^AFYAPOWERS_OTLP_LOGS_'` deve mostrar 3.

## Teste de uma versão em desenvolvimento

Só no terminal:

```
claude --plugin-dir <pasta deste repositório>
```

Nessa sessão, a cópia local substitui a do console. As variáveis `AFYAPOWERS_OTLP_LOGS_*` também funcionam no `.claude/settings.json`; quando a política as define, vale a política.

## Estrutura

```text
.claude-plugin/plugin.json   # Manifesto
hooks/
  hooks.json                 # Registro dos hooks
  track-jira-ticket          # Ticket da sessão
  emit-session-context       # Contexto na telemetria
  enforce-language           # Diretiva de idioma pt-BR
  render-history             # Histórico em HTML
  refresh-plugin-root        # Ponteiro da status line
  session_store.py           # Pastas do core, ticket, formato da chave e helper de git; usado pelos hooks e pela status line
scripts/statusline.py        # Status line
skills/statusline/           # /afyapowers-core:statusline
CHANGELOG.md                 # Mudanças por versão
```
