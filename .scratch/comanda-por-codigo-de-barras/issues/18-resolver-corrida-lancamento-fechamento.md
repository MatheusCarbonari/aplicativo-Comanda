# 18: Resolver a corrida entre Lançamento e Fechamento

**What to build:** garantir transacionalmente que a primeira operação confirmada prevaleça quando um Garçom lança um consumo enquanto o Caixa tenta fechar o mesmo Atendimento.

**Blocked by:** 10 — Proteger a abertura simultânea de Atendimento; 17 — Rejeitar Fechamento com revisão desatualizada.

**Status:** resolved

- [x] Se o Fechamento confirmar primeiro, o Lançamento concorrente é rejeitado sem efeitos parciais.
- [x] Se o Lançamento confirmar primeiro, ele integra o total e a confirmação antiga do Caixa é rejeitada.
- [x] Nenhum resultado permite Atendimento encerrado com Lançamento posterior associado.
- [x] A solução usa transações curtas e restrições persistentes compatíveis com SQLite.
- [x] Erros de contenção são tratados de forma compreensível e não expõem falha interna bruta ao usuário.
- [x] Testes concorrentes com SQLite real exercitam repetidamente as duas ordens de commit.

## Answer

As operações mutáveis continuam atômicas e iniciam pela persistência da
idempotência. A serialização de escritores do SQLite faz a primeira transação
confirmada prevalecer; a concorrente repete integralmente no máximo uma vez após
`SQLITE_BUSY` ou `SQLITE_LOCKED`.

A migration 0007 adiciona um trigger `BEFORE INSERT` que recusa persistentemente
qualquer Lançamento associado a Atendimento diferente de `ABERTO`. Apenas o erro
específico desse trigger é traduzido como ausência de Atendimento aberto. Se o
Fechamento confirmou primeiro, o Lançamento é rejeitado sem idempotência parcial;
se o Lançamento confirmou primeiro, a revisão muda e o Fechamento antigo é
rejeitado, preservando o novo consumo no Total.

Os testes com SQLite real usam `TransactionTestCase`, conexões separadas por
thread e cinco repetições de cada ordem. Também cobrem diretamente o trigger e a
resposta HTTP 503 quando a contenção persiste por duas tentativas.

