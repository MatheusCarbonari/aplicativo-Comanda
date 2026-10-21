# 23: Criar backup SQLite seguro

**What to build:** um comando administrativo capaz de produzir e validar uma cópia consistente do banco SQLite em uso, sem copiar ingenuamente o arquivo aberto.

**Blocked by:** 02 — Configurar persistência SQLite durável.

**Status:** resolved

- [x] O comando usa o mecanismo seguro de backup do SQLite.
- [x] O destino é persistente, conhecido e separado do arquivo operacional.
- [x] Cada cópia possui identificação temporal inequívoca e não sobrescreve silenciosamente outra cópia.
- [x] A cópia resultante passa por verificação mínima de abertura e integridade antes de ser declarada válida.
- [x] Falhas deixam o banco operacional intacto, removem ou identificam artefatos incompletos e retornam erro compreensível.
- [x] O comando registra início, sucesso e falha nos logs administrativos.
- [x] Testes com SQLite real comprovam consistência durante uso normal e comportamento seguro diante de falha.

## Answer

Implementado o comando `python manage.py criar_backup` usando
`sqlite3.Connection.backup()` sobre a conexão SQLite efetivamente configurada
pelo Django. A cópia é produzida como `.incompleto`, fechada, reaberta e
validada com `PRAGMA integrity_check`; somente o resultado `ok` é publicado em
`.local/backups/`.

Os nomes usam timestamp UTC com microssegundos. A publicação cria o nome final
sem substituir arquivos existentes e acrescenta sufixo numérico em colisões.
Falhas retornam `CommandError`, preservam a origem e removem o temporário quando
possível; se a limpeza falhar, o artefato continua explicitamente marcado como
`.incompleto`.

O logging registra `backup_sqlite_iniciado`, `backup_sqlite_concluido` e
`backup_sqlite_falhou` com identificador técnico, nome do arquivo validado ou
tipo do erro, sem conteúdo do banco. O sucesso ocorre apenas depois da validação
e publicação.

Validação concluída com 12 testes direcionados, 190 testes Django e 21 testes
JavaScript. `manage.py check`, `makemigrations --check --dry-run` e
`git diff --check` passaram.

