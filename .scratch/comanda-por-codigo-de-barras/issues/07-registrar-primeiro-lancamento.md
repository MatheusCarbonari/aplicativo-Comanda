# 07: Registrar o primeiro Lançamento

**What to build:** o fluxo móvel no qual um Garçom confirma o primeiro consumo de uma Comanda disponível e cria atomicamente o Atendimento com seu primeiro Lançamento.

**Blocked by:** 06 — Consultar o estado de uma Comanda física.

**Status:** ready-for-agent

- [ ] A visão do Garçom permite selecionar Produto, informar quantidade e confirmar o Lançamento.
- [ ] Somente quantidade inteira positiva é aceita; zero, valores negativos e fracionários são rejeitados com feedback claro.
- [ ] Produto e Comanda física precisam existir, e o Usuário operacional precisa ter papel `GARCOM`.
- [ ] O Atendimento e o primeiro Lançamento são confirmados na mesma transação ou integralmente revertidos.
- [ ] O Lançamento preserva quantidade, preço vigente em centavos, Garçom responsável e instante UTC definido pelo backend.
- [ ] Após o sucesso, a Comanda física aparece em atendimento e o total é exibido em BRL.
- [ ] Testes unitários, de aplicação, SQLite real e interface cobrem sucesso, validações, autorização e rollback.

