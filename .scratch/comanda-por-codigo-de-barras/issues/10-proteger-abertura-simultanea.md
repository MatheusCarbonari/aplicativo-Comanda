# 10: Proteger a abertura simultânea de Atendimento

**What to build:** garantir que primeiros lançamentos concorrentes para uma Comanda disponível resultem em um único Atendimento aberto e preservem todos os lançamentos válidos confirmados.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 09 — Criar idempotência reutilizável para operações mutáveis.

**Status:** resolved

- [x] O banco impede mais de um Atendimento aberto para a mesma Comanda física por restrição compatível com SQLite.
- [x] A operação usa transações curtas e não depende de `SELECT FOR UPDATE` ou bloqueio de linha.
- [x] Duas primeiras solicitações concorrentes válidas convergem para um único Atendimento.
- [x] Ambos os lançamentos são preservados quando suas transações podem ser confirmadas validamente.
- [x] Contenção e violações de restrição são tratadas sem erro interno genérico nem estado parcial.
- [x] Testes concorrentes usam SQLite real e repetem o cenário o suficiente para detectar criações duplicadas ou perda de Lançamento.

## Answer

O fluxo de primeiro Lançamento passou a deixar a constraint parcial de unicidade
do SQLite decidir a disputa pela abertura. A tentativa perdedora reverte apenas a
criação conflitante em um savepoint, reconhece especificamente a unicidade de
`Atendimento` aberto, localiza o vencedor e persiste nele seu Lançamento dentro da
mesma transação idempotente.

Contenções SQLite `BUSY`/`LOCKED` recebem no máximo duas tentativas totais. A
repetição usa a mesma chave idempotente, portanto recupera um resultado já
confirmado ou reaplica uma tentativa integralmente revertida, sem duplicação. Se a
contenção persistir, o caso de uso retorna indisponibilidade temporária e a
interface responde 503; não ficam Atendimento, Lançamento ou registro de
idempotência parciais.

Os testes com `TransactionTestCase`, SQLite real e conexões separadas por thread
repetem cinco vezes duas primeiras solicitações com Garçons, Produtos, quantidades
e chaves distintos, verificando um Atendimento, dois Lançamentos corretos e replay
sem duplicação. Testes adicionais cobrem o interleaving com vencedor já confirmado,
contenção transitória/persistente e a propagação de `IntegrityError` não relacionada.

