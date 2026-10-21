# 22: Registrar logs estruturados com rotação

**What to build:** produzir registros locais compreensíveis para diagnosticar o ciclo da aplicação e falhas operacionais sem transformar os logs em uma segunda cópia dos consumos.

**Blocked by:** 01 — Inicializar o monólito Django.

**Status:** resolved

- [x] Logs registram inicialização, encerramento, erros inesperados e falhas de banco com horário e severidade.
- [x] Identificadores técnicos relevantes permitem correlacionar uma operação sem registrar desnecessariamente todo o conteúdo consumido.
- [x] Arquivos usam diretório persistente conhecido e política de rotação documentada.
- [x] Segredos e informações desnecessárias não são incluídos.
- [x] Falha ao escrever um log é tratada de forma segura e não confirma falsamente uma operação de domínio.
- [x] Testes verificam formato, rotação configurada e ausência dos campos de consumo definidos como indevidos.

## Answer

Implementado logging JSONL local em `.local/logs/restaurante.jsonl`, com rotação
por tamanho aos 5 MiB e retenção de cinco backups. O ciclo Django registra início
e encerramento normal; middleware e endpoint de saúde registram erros inesperados
e falhas de banco; as quatro operações mutáveis registram apenas tipo da operação
e identificadores técnicos após obterem resultado confirmado.
Os eventos de sucesso são registrados por callbacks `on_commit`, de modo que uma
transação externa ainda pode revertê-los sem deixar confirmação falsa no log.

Produto, quantidade, preço, subtotal, Total, motivo e descrição de cancelamento,
formulários, cookies, sessão, CSRF, credenciais e headers sensíveis não são
copiados. A fronteira de logging absorve falhas do handler, mantendo o resultado
e a persistência do domínio independentes da escrita do log.
O ciclo de vida é emitido somente pelo processo operacional do `runserver` ou
pelas entradas WSGI/ASGI; autoreload auxiliar e comandos administrativos são
ignorados. Testes usam arquivo próprio por processo em `.local/testes/`.

Validação: 65 testes direcionados e 178 testes Django aprovados; 21 testes
JavaScript aprovados; `django check`, `makemigrations --check --dry-run` e
`git diff --check` concluídos sem erro.

## Dívida técnica não bloqueante

- Centralizar futuramente a montagem repetida do evento das quatro mutações.
- Reavaliar futuramente a direção da dependência entre casos de uso e logging de
  infraestrutura, sem ampliar este ticket.

