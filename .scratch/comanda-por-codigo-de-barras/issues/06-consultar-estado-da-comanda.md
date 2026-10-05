# 06: Consultar o estado de uma Comanda física

**What to build:** a consulta de uma Comanda física pelo seu identificador textual, permitindo ao Garçom ou Caixa distinguir uma comanda disponível, uma comanda em atendimento e um identificador desconhecido sem criar Atendimento.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente; 04 — Selecionar e trocar o Usuário operacional.

**Status:** ready-for-agent

- [ ] A consulta preserva zeros à esquerda e encontra somente comandas físicas previamente cadastradas.
- [ ] Uma Comanda disponível apresenta “Comanda disponível — nenhum atendimento aberto”.
- [ ] Um identificador desconhecido apresenta “Comanda não encontrada” e não cria qualquer registro.
- [ ] Consultar uma Comanda disponível não abre Atendimento nem altera seu estado.
- [ ] O backend carrega o Usuário operacional informado e valida que o papel pode usar a consulta correspondente.
- [ ] Testes de caso de uso, integração com SQLite e interface cobrem os três resultados da consulta.

