# 09: Criar idempotência reutilizável para operações mutáveis

**What to build:** um mecanismo persistente e reutilizável de idempotência, aplicado inicialmente ao registro de Lançamento e preparado para ser usado sem duplicação de solução pelo cancelamento e pelo Fechamento.

**Blocked by:** 07 — Registrar o primeiro Lançamento.

**Status:** ready-for-agent

- [ ] O mecanismo não depende de conceitos exclusivos do Lançamento e possui contrato reutilizável por diferentes operações mutáveis.
- [ ] Cada solicitação registra chave, identidade da operação, representação verificável do conteúdo e resultado confirmado.
- [ ] O registro de Lançamento usa o mecanismo e confirma a chave e a mudança de domínio na mesma transação.
- [ ] Reenviar a mesma chave com o mesmo conteúdo retorna o resultado original sem repetir a operação.
- [ ] Reutilizar a chave com operação ou conteúdo incompatível é rejeitado claramente.
- [ ] Chaves diferentes permitem ações intencionais iguais, e o comportamento permanece correto após reiniciar a aplicação.
- [ ] A interface evita duplicação por toque duplo, mas a garantia efetiva permanece no backend.
- [ ] Testes de integração com SQLite real demonstram reutilização pelo contrato, atomicidade, repetição, conflito e persistência após reinício.

