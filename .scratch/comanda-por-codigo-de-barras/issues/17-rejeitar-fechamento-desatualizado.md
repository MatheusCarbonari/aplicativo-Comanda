# 17: Rejeitar Fechamento com revisão desatualizada

**What to build:** impedir que o Caixa confirme um total antigo quando o Atendimento mudou depois da apresentação do resumo.

**Blocked by:** 16 — Fechar um Atendimento confirmado.

**Status:** resolved

- [x] O resumo usado na confirmação contém uma revisão verificável do Atendimento.
- [x] Qualquer mudança relevante no conteúdo invalida a revisão anteriormente apresentada.
- [x] Confirmar com revisão antiga não encerra o Atendimento.
- [x] A resposta apresenta ou permite carregar imediatamente o resumo atualizado e exige nova confirmação.
- [x] Repetir a confirmação com a revisão atual encerra o Atendimento uma única vez.
- [x] Testes de integração cobrem Lançamento e cancelamento ocorridos entre visualização e confirmação.

## Answer

A conferência de Fechamento agora inclui uma revisão SHA-256 determinística
do Atendimento, da Comanda e de todos os Lançamentos e cancelamentos relevantes.
O resumo e a revisão são preparados no mesmo snapshot transacional curto do
SQLite.

O POST inclui a revisão na identidade idempotente e a compara com o estado
persistido dentro da operação atômica, antes de encerrar. Uma divergência reverte
o registro idempotente provisório, mantém o Atendimento aberto e devolve HTTP 409
com resumo, Total, revisão e chave novos para outra confirmação explícita. O replay
de uma confirmação válida continua retornando o resultado original.

Os testes cobrem revisão no GET, estabilidade sem alterações, invalidação por
novo Lançamento e cancelamento, ausência de estado parcial, resumo atualizado,
nova confirmação e replay idempotente.

