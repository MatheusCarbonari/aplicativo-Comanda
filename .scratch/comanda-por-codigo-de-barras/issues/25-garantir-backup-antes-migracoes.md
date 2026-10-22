# 25: Garantir backup antes de migrações

**What to build:** proteger mudanças de esquema executando e validando um backup antes de aplicar migrações ao banco operacional.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** resolved

- [x] O procedimento operacional de migração dispara o mesmo mecanismo seguro de backup antes de alterar o esquema.
- [x] A migração não começa quando o backup prévio falha ou não pode ser validado.
- [x] O operador recebe mensagem clara indicando se a falha ocorreu no backup ou na migração.
- [x] Um backup pré-migração é distinguível dos backups diários e não é apagado prematuramente por uma execução incompleta.
- [x] O processo registra início, backup confirmado, migração concluída e falhas relevantes.
- [x] Testes cobrem backup bem-sucedido, falha que impede a migração e falha da migração após uma cópia válida.

## Answer

Implementado o comando `python manage.py migrar_com_backup`. Ele preserva a
interface pública do `migrate` do Django, cria primeiro uma cópia pelo comando
seguro `criar_backup` e somente inicia a migration depois que o backup retorna
com integridade validada e publicação concluída.

Backups desse fluxo usam o nome
`restaurante-pre-migracao-<timestamp UTC>.sqlite3`. O prefixo os distingue dos
backups diários e não corresponde ao padrão usado pela retenção do Ticket 24.
Falha no backup impede a migration e preserva cópias anteriores; falha na
migration mantém a nova cópia válida e não inicia restore automático.

O procedimento registra início, início e confirmação do backup pré-migração,
início e conclusão da migration e eventos distintos para falha em cada etapa.
Falhas do logging permanecem desacopladas do resultado administrativo.

Validação concluída com 6 testes direcionados, 31 testes combinados dos Tickets
23–25, 209 testes Django e 21 testes JavaScript. `manage.py check`,
`makemigrations --check --dry-run` e `git diff --check` passaram.

