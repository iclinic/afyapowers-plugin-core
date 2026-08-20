# afyapowers-core

Plugin de contexto de sessão da família **afyapowers** para o **Claude Code**. Contém a status line e os hooks de contexto que funcionam de forma independente do workflow do [afyapowers](https://github.com/afya/afyapowers) — instale este plugin mesmo em projetos que não usam o workflow de fases.

> **Apenas Claude Code.** Diferente do afyapowers, este plugin não tem distribuições para Cursor, Gemini ou GitHub Copilot.

## Componentes

| Componente | Evento(s) | O que faz |
|---|---|---|
| `hooks/jira-context` | `UserPromptSubmit` | Injeta o ticket Jira atual (`.afyapowers/current-jira-ticket`) como contexto do prompt e mantém o `.afyapowers/.gitignore` |
| `hooks/lang-directive` | `PreToolUse` (Skill), `UserPromptExpansion` | Reinjeta a diretiva de idioma pt-BR quando qualquer skill `afyapowers*:` é invocada |
| `hooks/render-history` | `SessionEnd` | Renderiza a conversa da sessão em HTML autocontido (`.afyapowers/history/claude/`, ou `~/.claude/afyapowers-core/history/<projeto>/claude/` em projetos sem `.afyapowers/`) |
| `hooks/otel-context` | `SessionStart`, `UserPromptSubmit`, `SessionEnd` | Emite log records OTLP com contexto de git/Jira/versão (ver [Telemetria](#telemetria-opentelemetry)) |
| `hooks/refresh-plugin-root` | `SessionStart` | Regrava o ponteiro `~/.claude/afyapowers-core/plugin-root` usado pela status line |
| `scripts/statusline.py` + `/afyapowers-core:statusline` | — | Status line opt-in: marca afyapowers, modelo, contexto, ticket Jira, git, custo e duração |

**Requisito de runtime:** Python 3.9+ no PATH (`python3`).

Os hooks nunca criam o diretório `.afyapowers/` — a presença dele é o que marca um projeto como afyapowers-enabled, e sua criação é responsabilidade do plugin afyapowers (`/afyapowers:new`). Em projetos sem `.afyapowers/`, os hooks degradam graciosamente (sem ticket Jira, history no diretório global).

## Status line

Instalação (global, vale para todos os projetos do usuário):

```
/afyapowers-core:statusline
```

Remoção: `/afyapowers-core:statusline remove`.

A entrada `statusLine` em `~/.claude/settings.json` resolve o script através do ponteiro `~/.claude/afyapowers-core/plugin-root`, regravado a cada início de sessão pelo hook `refresh-plugin-root` — assim ela sobrevive a upgrades de versão do plugin, que mudam o caminho de instalação.

## Telemetria (OpenTelemetry)

O Claude Code já exporta métricas e eventos via OTLP, mas nada dinâmico: `env` em `settings.json` é
estritamente estático (sem interpolação, sem command substitution) e nenhum hook consegue exportar env
var de volta para o processo do Claude Code. Ou seja, a branch atual jamais chega em
`OTEL_RESOURCE_ATTRIBUTES`.

O hook `otel-context` resolve isso emitindo **log records OTLP próprios** para o mesmo coletor, em
`SessionStart`, `UserPromptSubmit` e `SessionEnd`. Cada record carrega:

| Atributo | Exemplo | Observação |
|---|---|---|
| `event.name` | `afyapowers-core.git_context` | discrimina nossos records dos nativos |
| `session.id` | `abc123` | **chave de join** com os eventos `claude_code.*` |
| `prompt.id` | `550e8400-…` | join exato por prompt; ausente no `SessionStart` |
| `hook.event` | `UserPromptSubmit` | qual evento originou o record |
| `afyapowers.version` | `1.0.0` | versão do plugin afyapowers-core que produziu o record; lida do manifesto instalado (fallback: `claude plugin details afyapowers-core`), `null` se indeterminável |
| `jira.key` | `ABC-123` | ticket atual (`.afyapowers/current-jira-ticket`); sempre presente, `null` quando não há ticket |
| `git.branch` | `feat/tela-de-quizzes` | `detached` quando em detached HEAD |
| `git.repo` | `iclinic/afyapowers` | slug do remote (`origin`, ou o primeiro remote); cai para o nome da pasta local se não houver remote hospedado |
| `git.commit` | `73f5798` | SHA curto do `HEAD` |
| `git.dirty` | `true` / `false` | opt-in (ver abaixo) |

Os pares de `OTEL_RESOURCE_ATTRIBUTES` (department, cost center, squad) viajam no resource dos nossos
records também, então filtram igual aos eventos nativos.

> `git.repo` sai do remote justamente porque o nome da pasta local é escolha de cada dev e não
> identifica repositório numa frota. São extraídos apenas o owner e o repo — nunca o host nem
> credenciais eventualmente embutidas na URL de clone. Remote que é caminho local do filesystem é
> ignorado, para não vazar o layout de diretórios do dev.

**Como correlacionar:** no backend, junte nossos records aos nativos por `prompt.id` (exato) ou por
`session.id` (sessão inteira). Ex.: custo de tokens por branch = `claude_code.token.usage` ⨝
`event.name = 'afyapowers-core.git_context'` em `prompt.id`.

### Configuração

O hook não tem config própria obrigatória: ele **herda** a configuração OTLP que você já usa. Se
`CLAUDE_CODE_ENABLE_TELEMETRY=1` e houver um endpoint de logs resolvível, ele emite; caso contrário
fica silenciosamente inerte. As env vars podem vir do ambiente ou do bloco `env` de qualquer
`settings.json` (managed > projeto local > projeto > usuário) — o hook lê os arquivos como fallback,
então funciona independente de env var de settings ser herdada por subprocesso.

| Variável | Efeito |
|---|---|
| `AFYAPOWERS_CORE_OTEL_ENABLED` | `1` liga mesmo sem `CLAUDE_CODE_ENABLE_TELEMETRY`; `0` é kill switch e vence tudo |
| `AFYAPOWERS_CORE_OTEL_ENDPOINT` | sobrescreve o endpoint de logs (necessário se a org usa `grpc`, já que o hook só fala OTLP sobre HTTP) |
| `AFYAPOWERS_CORE_OTEL_HEADERS` | headers extras/sobrescritos, formato `k=v,k=v` |
| `AFYAPOWERS_CORE_OTEL_PROTOCOL` | `http/protobuf` (default) ou `http/json` |
| `AFYAPOWERS_CORE_OTEL_GIT_DIRTY` | `1` inclui `git.dirty`. Opt-in porque `git status` varre a árvore inteira e custa segundos em monorepo |
| `AFYAPOWERS_CORE_OTEL_DEBUG` | `1` grava o que foi enviado (ou por que não) em `.afyapowers/otel-debug.jsonl` |

> **Migração do afyapowers ≤ 1.x:** as variáveis mudaram de prefixo (`AFYAPOWERS_OTEL_*` →
> `AFYAPOWERS_CORE_OTEL_*`) e o `event.name` mudou de `afyapowers.git_context` para
> `afyapowers-core.git_context`. Atualize managed settings e queries do backend.

Ordem de resolução do endpoint: `AFYAPOWERS_CORE_OTEL_ENDPOINT` → `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` →
`OTEL_EXPORTER_OTLP_ENDPOINT` + `/v1/logs`. Headers e protocolo seguem a mesma lógica per-signal do
OTel (`OTEL_EXPORTER_OTLP_LOGS_HEADERS` / `_PROTOCOL` ganham dos genéricos).

### Rollout na frota

Um único arquivo de managed settings (`/Library/Application Support/ClaudeCode/managed-settings.json`
no macOS, `/etc/claude-code/` no Linux) mais o plugin atualizado cobrem toda a base de devs — sem
dotfile e sem setting por repositório:

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "https://collector.exemplo.com.br/v1/logs",
    "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "Authorization=Bearer TOKEN",
    "OTEL_RESOURCE_ATTRIBUTES": "department=engineering,cost_center=eng-123",
    "OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES": "false"
  }
}
```

> Managed settings **remove** env vars conflitantes definidas pelo dev no startup. Fixar
> `OTEL_RESOURCE_ATTRIBUTES` ali é o que você quer para atributos organizacionais, mas inviabiliza
> qualquer enriquecimento local via wrapper de shell.

**Garantias do hook:** roda no caminho crítico do prompt apenas para resolver config e fazer spawn de
um filho destacado (~50 ms); git e rede acontecem no filho. Nunca escreve em stdout (em
`UserPromptSubmit` o stdout do hook seria injetado como contexto no prompt), nunca bloqueia a sessão e
sai `0` em qualquer erro.

## Estrutura

```text
.claude-plugin/plugin.json   # Manifesto do plugin
hooks/
  hooks.json                 # Registro dos hooks
  refresh-plugin-root        # Ponteiro da status line (SessionStart)
  jira-context               # Contexto de ticket Jira (UserPromptSubmit)
  lang-directive             # Diretiva de idioma pt-BR (PreToolUse/UserPromptExpansion)
  render-history             # Histórico da conversa em HTML (SessionEnd)
  otel-context               # Telemetria OTLP (SessionStart/UserPromptSubmit/SessionEnd)
scripts/
  statusline.py              # Renderizador da status line
skills/
  statusline/                # /afyapowers-core:statusline — instala/remove a status line
```

## Licença

MIT
