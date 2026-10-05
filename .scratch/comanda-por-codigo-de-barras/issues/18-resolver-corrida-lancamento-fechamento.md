# 18: Resolver a corrida entre Lançamento e Fechamento

**What to build:** garantir transacionalmente que a primeira operação confirmada prevaleça quando um Garçom lança um consumo enquanto o Caixa tenta fechar o mesmo Atendimento.

**Blocked by:** 10 — Proteger a abertura simultânea de Atendimento; 17 — Rejeitar Fechamento com revisão desatualizada.

**Status:** ready-for-agent

- [ ] Se o Fechamento confirmar primeiro, o Lançamento concorrente é rejeitado sem efeitos parciais.
- [ ] Se o Lançamento confirmar primeiro, ele integra o total e a confirmação antiga do Caixa é rejeitada.
- [ ] Nenhum resultado permite Atendimento encerrado com Lançamento posterior associado.
- [ ] A solução usa transações curtas e restrições persistentes compatíveis com SQLite.
- [ ] Erros de contenção são tratados de forma compreensível e não expõem falha interna bruta ao usuário.
- [ ] Testes concorrentes com SQLite real exercitam repetidamente as duas ordens de commit.

