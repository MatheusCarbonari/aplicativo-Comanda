# 10: Proteger a abertura simultânea de Atendimento

**What to build:** garantir que primeiros lançamentos concorrentes para uma Comanda disponível resultem em um único Atendimento aberto e preservem todos os lançamentos válidos confirmados.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 09 — Criar idempotência reutilizável para operações mutáveis.

**Status:** ready-for-agent

- [ ] O banco impede mais de um Atendimento aberto para a mesma Comanda física por restrição compatível com SQLite.
- [ ] A operação usa transações curtas e não depende de `SELECT FOR UPDATE` ou bloqueio de linha.
- [ ] Duas primeiras solicitações concorrentes válidas convergem para um único Atendimento.
- [ ] Ambos os lançamentos são preservados quando suas transações podem ser confirmadas validamente.
- [ ] Contenção e violações de restrição são tratadas sem erro interno genérico nem estado parcial.
- [ ] Testes concorrentes usam SQLite real e repetem o cenário o suficiente para detectar criações duplicadas ou perda de Lançamento.

