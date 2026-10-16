# 12: Exibir o histórico de cancelamentos

**What to build:** apresentar os lançamentos cancelados em uma seção separada e manter a área principal e o Total do atendimento restritos aos lançamentos válidos.

**Blocked by:** 11 — Cancelar integralmente um Lançamento.

**Status:** resolved

- [x] Lançamentos cancelados não aparecem entre os consumos válidos nem participam do total.
- [x] A seção de cancelados mostra Produto, quantidade, preço original, autores, horários e motivo quando disponíveis.
- [x] Horários são apresentados em `America/Sao_Paulo`, com data e formato de 24 horas definidos na especificação.
- [x] Se todos os lançamentos forem cancelados, o Atendimento permanece aberto e apresenta total `R$ 0,00`.
- [x] A visualização continua priorizando consumos válidos e o total atual.
- [x] Testes de apresentação e integração cobrem cancelamentos isolados, múltiplos cancelamentos e total zero.

## Answer

A consulta do Garçom agora prepara duas projeções independentes: os Lançamentos
válidos continuam vindo de `atendimento.lancamentos.validos()` e os cancelados são
carregados separadamente com seus dados originais e os dados do cancelamento. O
Total permanece calculado exclusivamente sobre a coleção válida, inclusive quando
ela está vazia e o Atendimento aberto apresenta `R$ 0,00`.

Produto, quantidade, preço unitário original, autores, horários, motivo e descrição
opcional chegam prontos ao template do histórico. Os instantes persistidos em UTC
são convertidos somente na camada de apresentação para `America/Sao_Paulo`, no
formato `dd/MM/yyyy HH:mm`.

Testes pela interface cobrem separação entre as seções, exclusão do Total, dados
completos, múltiplos cancelamentos, conversão de fuso, Atendimento aberto com todos
os Lançamentos cancelados e ausência limpa da seção quando não há cancelamentos.

