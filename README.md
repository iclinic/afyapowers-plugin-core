# afyapowers-core

Plugin core da família **afyapowers** para o **Claude Code**, responsável por fornecer contexto de Jira, status line, histórico de conversas em HTML, telemetria OTLP e diretiva de idioma pt-BR.

Funciona de forma independente do workflow de fases do [afyapowers](https://github.com/afya/afyapowers) — instale este plugin mesmo em projetos que não usam o workflow.

> **Apenas Claude Code.** Diferente do afyapowers, este plugin não tem distribuições para Cursor, Gemini ou GitHub Copilot.

## Visão geral

| Componente | Evento(s) | O que faz |
|---|---|---|
| [`hooks/jira-context`](#contexto-de-jira) | `SessionStart`, `UserPromptSubmit` | Confirma o ticket Jira **por sessão** e o injeta como contexto de cada prompt |
| [`hooks/lang-directive`](#diretiva-de-idioma-pt-br) | `PreToolUse` (Skill), `UserPromptExpansion` | Reinjeta a diretiva de idioma pt-BR quando qualquer skill `afyapowers*:` é invocada |
| [`hooks/render-history`](#histórico-de-conversas) | `SessionEnd` | Renderiza a conversa da sessão em HTML autocontido |
| [`hooks/otel-context`](#telemetria-opentelemetry) | `SessionStart`, `UserPromptSubmit`, `SessionEnd` | Emite log records OTLP com contexto de git/Jira/versão |
| [`hooks/refresh-plugin-root`](#ponteiro-de-instalação-e-pré-requisitos) | `SessionStart` | Regrava o ponteiro usado pela status line e avisa se o Python está ausente |
| [`scripts/statusline.py`](#status-line) + `/afyapowers-core:statusline` | — | Status line opt-in: marca afyapowers, modelo, contexto, ticket Jira, git, custo e duração |

**Requisito de runtime:** Python 3.9+ no PATH (`python3`).

### Garantias de execução

Todos os hooks seguem o mesmo contrato:

- **Nunca bloqueiam a sessão.** São observabilidade/enriquecimento de contexto: qualquer erro resulta em `exit 0` silencioso, nunca em prompt travado ou sessão quebrada.
- **Nunca criam `.afyapowers/`.** A presença desse diretório é o que marca um projeto como afyapowers-enabled, e sua criação é responsabilidade do plugin afyapowers (`/afyapowers:new`). Em projetos sem `.afyapowers/`, os hooks degradam graciosamente: history vai para o diretório global. O estado **por sessão** (ticket Jira confirmado) fica fora do projeto, em `~/.claude/afyapowers-core/sessions/`, e não depende de `.afyapowers/` existir.
- **Trabalho pesado fora do caminho crítico.** O que envolve git ou rede (telemetria) roda em processo filho destacado; o hook em si retorna em milissegundos.

## Componentes

### Contexto de Jira

`hooks/jira-context` é o dono do fluxo de ticket Jira. O ticket é **por sessão**, não por projeto: duas sessões do Claude Code abertas na mesma pasta são dois trabalhos distintos, e cada uma grava a própria resposta em

```text
~/.claude/afyapowers-core/sessions/<session_id>/
  jira-ticket    # escrito pelo modelo: ABC-123 ou o literal none
  branch-key     # escrito pelo hook: chave sugerida pela branch no último prompt
```

(`~/.claude` respeita `CLAUDE_CONFIG_DIR`.) O arquivo `jira-ticket` é o que a telemetria e a status line leem — ambas o resolvem pelo `session_id` que já recebem no stdin.

A cada `UserPromptSubmit`, dentro de um repositório git, o hook:

1. **Lê o arquivo da sessão** e **extrai uma sugestão da branch** atual (padrão `ABC-123` no nome da branch).
2. **Sessão sem resposta** → injeta, junto com o prompt, a instrução para o modelo perguntar ao usuário (via `AskUserQuestion`) como primeira ação do turno. Opção recomendada: a chave da branch, se houver; senão, "sem ticket". A instrução traz o caminho absoluto do arquivo da sessão a gravar.
3. **Branch trocou no meio da sessão** (a chave sugerida mudou desde o último prompt e difere do ticket gravado) → pergunta de novo, uma vez por troca.
4. **Sessão resolvida** → injeta só um lembrete curto com o ticket atual e a regra de perguntar de novo quando o prompt inicia outra tarefa/feature/bug.

A deduplicação é por estado em disco, não pela memória do modelo: a pergunta se repete enquanto o arquivo da sessão não existir e nunca mais depois — sobrevive a `/compact`, e `--resume` reaproveita a resposta. O hook nunca grava o ticket por conta própria (não infere da branch): o usuário confirma uma vez por sessão.

Não existe mais ponteiro por projeto: o antigo `.afyapowers/current-jira-ticket` era compartilhado por todas as sessões da pasta, exatamente o que fazia a resposta de uma sessão vazar para a telemetria da outra. Este plugin não o lê nem o grava.

Em `SessionStart` o hook só faz manutenção: cria `sessions/` e remove entradas sem uso há mais de 7 dias (o arquivo da sessão é "tocado" a cada prompt, então uma sessão viva ou retomada nunca expira em uso). Não há registro em `SessionEnd`: `--resume` e `/clear` mantêm a sessão anterior retomável, e os hooks de `SessionEnd` de plugins dividem um orçamento total de 1,5 s.

O hook não toca no projeto (nem `.afyapowers/` nem `.gitignore`). Fora de um repositório git ele não faz nada — um ticket só faz sentido atado a um projeto.

> **Follow-up no afyapowers-dev:** a skill `design` ainda grava `.afyapowers/current-jira-ticket` (e `/new` o cria vazio), que nada mais lê. Para o ticket validado no design refletir na sessão corrente, ela deve passar a gravar o arquivo de sessão cujo caminho o `jira-context` informa no contexto de cada prompt.

### Diretiva de idioma pt-BR

`hooks/lang-directive` reinjeta a diretiva de idioma da família afyapowers no momento em que ela é mais necessária: quando uma skill `afyapowers*:` é invocada — pelo modelo (`PreToolUse` no tool `Skill`) ou pelo usuário via slash command (`UserPromptExpansion`).

A diretiva instrui o modelo a conversar e escrever todos os artefatos afyapowers em português do Brasil, tratando os templates em inglês dentro das skills como guia de conteúdo (não texto final), mantendo em inglês os termos técnicos convencionais e os identificadores de fase do workflow, e nunca traduzindo código, identificadores ou caminhos de arquivo.

Injetar por skill (em vez de a cada prompt) mantém a diretiva próxima da ação sem custo de tokens em turnos que não usam afyapowers.

### Histórico de conversas

`hooks/render-history` (`SessionEnd`) lê o transcript JSONL da sessão e renderiza **um HTML interativo e autocontido por sessão**, mais um `index.html` regenerado com a lista de sessões. Conversas de subagentes (tool `Agent`) são seguidas recursivamente e renderizadas aninhadas sob a chamada que as criou.

Destino dos arquivos:

- Projetos afyapowers-enabled: `.afyapowers/history/claude/` (ignorado pelo git via `.afyapowers/.gitignore`).
- Demais projetos: `~/.claude/afyapowers-core/history/<projeto>/claude/` — todo projeto tem histórico, nenhum ganha um `.afyapowers/` que não pediu.

### Status line

Opt-in, instalada **globalmente** (vale para todos os projetos do usuário):

```
/afyapowers-core:statusline
```

Mostra no rodapé do Claude Code: a marca afyapowers, modelo e uso de contexto, o ticket Jira confirmado **nesta sessão** (resolvido pelo `session_id`; omitido até o usuário confirmar ou quando trabalha sem ticket), branch/estado do git, custo e duração da sessão.

Remoção: `/afyapowers-core:statusline remove`. O instalador é idempotente: mescla apenas a chave `statusLine` em `~/.claude/settings.json` e, na remoção, deleta apenas ela — nunca sobrescreve um settings quebrado.

A entrada `statusLine` resolve o script através do ponteiro `~/.claude/afyapowers-core/plugin-root`, regravado a cada início de sessão pelo hook `refresh-plugin-root` — assim ela sobrevive a upgrades de versão do plugin, que mudam o caminho de instalação.

### Ponteiro de instalação e pré-requisitos

`hooks/refresh-plugin-root` (`SessionStart`) regrava o ponteiro `~/.claude/afyapowers-core/plugin-root` com o caminho da versão instalada do plugin (é ele que mantém a status line funcionando após upgrades) e emite um aviso não-bloqueante na sessão quando o `python3` não está no PATH — já que todos os demais hooks e a status line são Python.

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
| `jira.key` | `ABC-123` | ticket confirmado **nesta sessão** (`~/.claude/afyapowers-core/sessions/<session_id>/jira-ticket`); sempre presente, `null` até o usuário confirmar ou quando trabalha sem ticket. Sem fallback para o ponteiro do projeto: sessões simultâneas na mesma pasta não se contaminam |
| `afyapowers_dev.current_phase` | `implement` | fase atual da feature ativa do afyapowers-dev (`.afyapowers/features/<slug>/state.yaml`); omitido quando não há feature ativa |
| `<plugin>.version` | `afyapowers_dev.version = 1.8.0` | versão de cada plugin da família afyapowers instalado (`claude plugin list --json`); omitido quando indisponível |
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

**`jira.key` no primeiro record:** o hook dispara junto com o prompt, antes de o modelo perguntar e o
usuário responder, então o record de `SessionStart` e o do primeiro `UserPromptSubmit` de cada sessão
saem com `jira.key: null` por construção. Para atribuir a sessão inteira ao ticket, preencha no
backend com o último valor não nulo da sessão, ex. (SQL/Databricks):

```sql
last_value(jira.key, true) over (partition by session.id order by time_unix_nano
                                 rows between unbounded preceding and unbounded following)
```

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
>
> **Migração 1.1 → 1.2:** `jira.key` manteve nome e formato, mas a semântica mudou: passou a ser o
> ticket confirmado **na sessão** (antes: `.afyapowers/current-jira-ticket`, compartilhado por todas
> as sessões da pasta, que este plugin não lê mais) e é `null` até a confirmação, inclusive no
> primeiro `UserPromptSubmit`. Queries que agregam por ticket devem usar o preenchimento por sessão
> descrito acima.

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
  refresh-plugin-root        # Ponteiro da status line + aviso de Python (SessionStart)
  jira-context               # Ticket Jira por sessão (SessionStart/UserPromptSubmit)
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
