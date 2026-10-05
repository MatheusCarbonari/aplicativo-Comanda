# 25: Garantir backup antes de migrações

**What to build:** proteger mudanças de esquema executando e validando um backup antes de aplicar migrações ao banco operacional.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** ready-for-agent

- [ ] O procedimento operacional de migração dispara o mesmo mecanismo seguro de backup antes de alterar o esquema.
- [ ] A migração não começa quando o backup prévio falha ou não pode ser validado.
- [ ] O operador recebe mensagem clara indicando se a falha ocorreu no backup ou na migração.
- [ ] Um backup pré-migração é distinguível dos backups diários e não é apagado prematuramente por uma execução incompleta.
- [ ] O processo registra início, backup confirmado, migração concluída e falhas relevantes.
- [ ] Testes cobrem backup bem-sucedido, falha que impede a migração e falha da migração após uma cópia válida.

