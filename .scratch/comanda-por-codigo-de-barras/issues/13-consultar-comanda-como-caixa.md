# 13: Consultar a Comanda como Caixa

**What to build:** uma visão de Caixa que recupere o Atendimento aberto e apresente os lançamentos válidos consolidados para conferência em computador.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 12 — Exibir o histórico de cancelamentos.

**Status:** ready-for-agent

- [ ] O backend exige Usuário operacional `CAIXA` para a consulta de Caixa.
- [ ] Lançamentos válidos do mesmo Produto e preço unitário são consolidados visualmente.
- [ ] Lançamentos do mesmo Produto com preços unitários diferentes aparecem em linhas separadas.
- [ ] Cada linha mostra Produto, quantidade, preço unitário e subtotal; o total geral usa BRL.
- [ ] A consolidação não altera nem elimina os lançamentos individuais persistidos.
- [ ] A seção de cancelados permanece separada e acessível.
- [ ] Testes cobrem autorização, consolidação, preços distintos, subtotais e preservação do histórico.

