# 12: Exibir o histórico de cancelamentos

**What to build:** apresentar os lançamentos cancelados em uma seção separada e manter a área principal e o Total do atendimento restritos aos lançamentos válidos.

**Blocked by:** 11 — Cancelar integralmente um Lançamento.

**Status:** ready-for-agent

- [ ] Lançamentos cancelados não aparecem entre os consumos válidos nem participam do total.
- [ ] A seção de cancelados mostra Produto, quantidade, preço original, autores, horários e motivo quando disponíveis.
- [ ] Horários são apresentados em `America/Sao_Paulo`, com data e formato de 24 horas definidos na especificação.
- [ ] Se todos os lançamentos forem cancelados, o Atendimento permanece aberto e apresenta total `R$ 0,00`.
- [ ] A visualização continua priorizando consumos válidos e o total atual.
- [ ] Testes de apresentação e integração cobrem cancelamentos isolados, múltiplos cancelamentos e total zero.

