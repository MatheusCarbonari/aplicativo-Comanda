# 16: Fechar um Atendimento confirmado

**What to build:** permitir que o Caixa confira o resumo atual e confirme de forma explícita e irreversível o Fechamento de um Atendimento aberto.

**Blocked by:** 09 — Criar idempotência reutilizável para operações mutáveis; 13 — Consultar a Comanda como Caixa.

**Status:** ready-for-agent

- [ ] Somente Usuário operacional `CAIXA` pode confirmar o Fechamento.
- [ ] O sistema exibe conteúdo e total antes de solicitar a confirmação explícita.
- [ ] O Fechamento registra instante UTC e Caixa responsável, encerra o Atendimento e libera imediatamente a Comanda física.
- [ ] Atendimento com total zero pode ser fechado explicitamente.
- [ ] Depois do commit, novas mutações no Atendimento são rejeitadas e não existe reabertura no protótipo.
- [ ] A operação reutiliza o mecanismo geral de idempotência do ticket 09.
- [ ] Testes cobrem autorização, confirmação, total zero, liberação da Comanda física, idempotência e irreversibilidade.

