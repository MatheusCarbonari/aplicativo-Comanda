# 23: Criar backup SQLite seguro

**What to build:** um comando administrativo capaz de produzir e validar uma cópia consistente do banco SQLite em uso, sem copiar ingenuamente o arquivo aberto.

**Blocked by:** 02 — Configurar persistência SQLite durável.

**Status:** ready-for-agent

- [ ] O comando usa o mecanismo seguro de backup do SQLite.
- [ ] O destino é persistente, conhecido e separado do arquivo operacional.
- [ ] Cada cópia possui identificação temporal inequívoca e não sobrescreve silenciosamente outra cópia.
- [ ] A cópia resultante passa por verificação mínima de abertura e integridade antes de ser declarada válida.
- [ ] Falhas deixam o banco operacional intacto, removem ou identificam artefatos incompletos e retornam erro compreensível.
- [ ] O comando registra início, sucesso e falha nos logs administrativos.
- [ ] Testes com SQLite real comprovam consistência durante uso normal e comportamento seguro diante de falha.

