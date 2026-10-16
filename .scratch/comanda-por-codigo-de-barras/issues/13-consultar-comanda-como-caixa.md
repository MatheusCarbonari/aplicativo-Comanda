# 13: Consultar a Comanda como Caixa

**What to build:** uma visão de Caixa que recupere o Atendimento aberto e apresente os lançamentos válidos consolidados para conferência em computador.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 12 — Exibir o histórico de cancelamentos.

**Status:** resolved

- [x] O backend exige Usuário operacional `CAIXA` para a consulta de Caixa.
- [x] Lançamentos válidos do mesmo Produto e preço unitário são consolidados visualmente.
- [x] Lançamentos do mesmo Produto com preços unitários diferentes aparecem em linhas separadas.
- [x] Cada linha mostra Produto, quantidade, preço unitário e subtotal; o total geral usa BRL.
- [x] A consolidação não altera nem elimina os lançamentos individuais persistidos.
- [x] A seção de cancelados permanece separada e acessível.
- [x] Testes cobrem autorização, consolidação, preços distintos, subtotais e preservação do histórico.

## Answer

A experiência do Caixa agora envia a consulta para uma rota própria, cujo caso de
uso exige o papel `CAIXA`; Garçom recebe rejeição do backend. A consulta recupera
somente os Lançamentos válidos do Atendimento aberto e os projeta para a função
pura `consolidar_lancamentos()`.

A consolidação usa a chave composta por Produto e `preco_unitario_centavos`, soma
as quantidades de cada grupo e calcula o subtotal em centavos. Por isso, registros
do mesmo Produto com preços originais diferentes permanecem em linhas distintas.
O Total geral também é calculado apenas a partir dos Lançamentos válidos e é
formatado em BRL na interface.

O histórico de cancelamentos do Ticket 12 é reutilizado como seção separada. Todo
o fluxo é somente leitura: a consolidação existe apenas em memória e nenhum
Lançamento é atualizado, removido ou substituído. Os testes confirmam autorização,
linhas consolidadas, preços distintos, quantidades, subtotais, Total, exclusão de
cancelados e preservação dos registros persistidos.

