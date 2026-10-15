# 09: Criar idempotência reutilizável para operações mutáveis

**What to build:** um mecanismo persistente e reutilizável de idempotência, aplicado inicialmente ao registro de Lançamento e preparado para ser usado sem duplicação de solução pelo cancelamento e pelo Fechamento.

**Blocked by:** 07 — Registrar o primeiro Lançamento.

**Status:** resolved

- [x] O mecanismo não depende de conceitos exclusivos do Lançamento e possui contrato reutilizável por diferentes operações mutáveis.
- [x] Cada solicitação registra chave, identidade da operação, representação verificável do conteúdo e resultado confirmado.
- [x] O registro de Lançamento usa o mecanismo e confirma a chave e a mudança de domínio na mesma transação.
- [x] Reenviar a mesma chave com o mesmo conteúdo retorna o resultado original sem repetir a operação.
- [x] Reutilizar a chave com operação ou conteúdo incompatível é rejeitado claramente.
- [x] Chaves diferentes permitem ações intencionais iguais, e o comportamento permanece correto após reiniciar a aplicação.
- [x] A interface evita duplicação por toque duplo, mas a garantia efetiva permanece no backend.
- [x] Testes de integração com SQLite real demonstram reutilização pelo contrato, atomicidade, repetição, conflito e persistência após reinício.

## Answer

Foi criado um registro persistente e independente de operação específica, com chave
única, identificador estável da operação, hash SHA-256 do conteúdo canônico, resultado
JSON e horário. O contrato `executar_idempotente` envolve callback e registro na mesma
transação e foi aplicado ao primeiro Lançamento e aos Lançamentos adicionais. A
interface gera UUID por intenção e reduz envios duplos com JavaScript local; a
garantia real permanece no backend e na unicidade do SQLite.

