# 22: Registrar logs estruturados com rotação

**What to build:** produzir registros locais compreensíveis para diagnosticar o ciclo da aplicação e falhas operacionais sem transformar os logs em uma segunda cópia dos consumos.

**Blocked by:** 01 — Inicializar o monólito Django.

**Status:** ready-for-agent

- [ ] Logs registram inicialização, encerramento, erros inesperados e falhas de banco com horário e severidade.
- [ ] Identificadores técnicos relevantes permitem correlacionar uma operação sem registrar desnecessariamente todo o conteúdo consumido.
- [ ] Arquivos usam diretório persistente conhecido e política de rotação documentada.
- [ ] Segredos e informações desnecessárias não são incluídos.
- [ ] Falha ao escrever um log é tratada de forma segura e não confirma falsamente uma operação de domínio.
- [ ] Testes verificam formato, rotação configurada e ausência dos campos de consumo definidos como indevidos.

