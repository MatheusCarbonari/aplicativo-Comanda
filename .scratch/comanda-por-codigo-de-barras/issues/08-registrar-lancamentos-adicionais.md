# 08: Registrar lançamentos adicionais e calcular o total

**What to build:** permitir que qualquer Garçom acrescente novos lançamentos independentes a um Atendimento aberto e veja o Total do atendimento atualizado sem sobrescrever consumos anteriores.

**Blocked by:** 07 — Registrar o primeiro Lançamento.

**Status:** ready-for-agent

- [ ] Novos lançamentos válidos são associados ao Atendimento aberto já existente.
- [ ] Garçons diferentes podem registrar consumos no mesmo Atendimento, preservando a autoria de cada ação.
- [ ] Lançamentos repetidos permanecem registros individuais no armazenamento.
- [ ] Alterar posteriormente o preço do Produto não modifica o preço já registrado no Lançamento.
- [ ] O Total do atendimento soma quantidade multiplicada pelo preço registrado usando somente centavos inteiros.
- [ ] Um Atendimento encerrado rejeita novos lançamentos sem produzir efeitos parciais.
- [ ] Testes cobrem autoria múltipla, repetição intencional, preço histórico, total e rejeição após Fechamento.

