# 19: Apresentar o resumo final do Atendimento

**What to build:** mostrar ao Caixa, imediatamente após o Fechamento, uma fotografia legível e completa do Atendimento que acabou de ser encerrado.

**Blocked by:** 12 — Exibir o histórico de cancelamentos; 16 — Fechar um Atendimento confirmado.

**Status:** resolved

- [x] O resumo mostra Identificador da comanda, identificador do Atendimento, abertura e fechamento.
- [x] Itens válidos aparecem consolidados com quantidade, preço unitário e subtotal.
- [x] Lançamentos cancelados aparecem em seção separada com sua rastreabilidade.
- [x] O total final e o Caixa responsável são apresentados claramente.
- [x] Valores e horários respeitam BRL, `America/Sao_Paulo`, data brasileira e formato de 24 horas.
- [x] A tela não oferece pagamento, impressão de recibo, emissão fiscal ou reabertura.
- [x] Testes de apresentação cobrem Atendimento com cancelamentos, preços diferentes e total zero.

## Answer

O fechamento redireciona para uma rota que contém o identificador do Atendimento
encerrado. A consulta filtra esse identificador pelo estado `ENCERRADO`, por isso
continua exibindo o histórico correto mesmo após a Comanda receber outro
Atendimento.

O resumo reutiliza a consolidação por Produto e preço histórico, a formatação BRL,
o histórico de cancelamentos e a conversão para `America/Sao_Paulo`. Os consumos
válidos aparecem consolidados; os cancelados permanecem em seção separada e fora
do Total final.

O campo `Atendimento.aberto_em` registra a abertura em UTC. A migration 0008
preenche o histórico com o primeiro Lançamento disponível (ou o instante da
migração quando não há Lançamento) e preserva o trigger que impede Lançamentos
após o fechamento.

