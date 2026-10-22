# Changelog

## 1.4.0

### Mudanças

- **Destino da telemetria:** lido só de `AFYAPOWERS_OTLP_LOGS_ENDPOINT`, `_HEADERS` e `_PROTOCOL`, do ambiente. Deixam de ser lidos o cache `remote-settings.json`, os arquivos de settings e as `OTEL_*`.
- **Cadência do envio:** o contexto sai quando o ticket fica conhecido e a cada mudança de repositório ou branch; não mais no início da sessão, a cada prompt e no fim. Envio que falha é repetido no prompt seguinte.
- **Pergunta do ticket:** com chave na branch, caixa "Ticket Jira" com a chave e "Sem ticket"; sem chave, pergunta em texto; resposta sem decisão recebe uma frase fixa até vir uma resposta válida.
- **Resposta digitada:** depois da pergunta, um prompt de até 30 caracteres com uma chave ou "sem ticket" grava o ticket. O modelo não grava mais o arquivo.
- **Registro do último envio:** `~/.claude/afyapowers-core/last-send.json`, sobrescrito a cada tentativa.
- **Limpeza de sessões:** roda ao gravar o ticket de uma sessão nova e apaga a pasta inteira de sessões paradas há mais de 7 dias.
- **Chave do Jira:** só é reconhecida com o número fechando a palavra. Branches como `claude/jolly-lovelace-8f488e`, `release-1.135.0` e `revert-5e9a3c44` deixam de sugerir uma chave falsa.
- **Aviso de Python ausente:** passa a chegar ao modelo; o formato anterior era descartado pelo Claude Code.
- **Status line:** mostra a branch, ou `detached`, num repositório sem commits e com HEAD solto.
- **`jira.key` vazio (`""`):** no `session_context`, é uma string vazia e significa "sem ticket", porque o evento só sai depois da resposta.
- **Caminho com espaço:** os hooks rodam quando o caminho do plugin tem espaço, como no app desktop do macOS (`~/Library/Application Support/...`). Antes, nenhum hook do core rodava nesse caso.
- **Nomes:** `otel-context` → `emit-session-context`, `jira-context` → `track-jira-ticket`, `lang-directive` → `enforce-language`; evento `afyapowers-core.git_context` → `afyapowers-core.session_context`.

### Removido

- Hook do ticket e envio de contexto no `SessionStart`; envio no `SessionEnd`.
- `AFYAPOWERS_CORE_OTEL_DEBUG` e o arquivo `otel-debug.jsonl`.
- Opções "Another ticket id" e "No specific task"; respostas negativas diferentes de "sem ticket".
- Atributos do evento que a telemetria nativa já traz na mesma sessão: `afyapowers.version`, `afyapowers_core.version`, as versões dos outros plugins da família (vêm do `plugin_loaded`) e `user.email`. Sai também a chamada a `claude plugin list`.
- `git.dirty` e a variável `AFYAPOWERS_CORE_OTEL_GIT_DIRTY`.
- Suporte a Gemini, Cursor e Copilot nos hooks de idioma e de histórico.

### Implantação

1. Política do Claude Code com as variáveis `AFYAPOWERS_OTLP_LOGS_*` nas três contas.
2. Control Tower lendo `afyapowers-core.session_context` (visão `ct_session_tickets`).
3. Publicação do core 1.4.0 no console.

## Versões anteriores

Ver as tags `v1.0.0` a `v1.3.0` e o histórico do git.
