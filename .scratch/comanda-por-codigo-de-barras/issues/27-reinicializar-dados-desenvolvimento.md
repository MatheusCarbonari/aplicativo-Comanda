# 27: Reinicializar dados de desenvolvimento com segurança

**What to build:** um comando exclusivo de desenvolvimento que recrie a massa inicial somente após avisar sobre a remoção dos dados operacionais, obter confirmação e gerar um backup válido.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente; 23 — Criar backup SQLite seguro.

**Status:** resolved

- [x] O comando nunca é executado automaticamente nem aparece na interface operacional.
- [x] Antes de qualquer remoção, ele identifica claramente o ambiente e os dados que serão perdidos.
- [x] Sem confirmação explícita, nenhuma alteração ou limpeza ocorre.
- [x] A limpeza só começa depois de um backup seguro e validado.
- [x] Ao concluir, a massa inicial é recriada sem duplicidades.
- [x] Falha antes do commit não deixa uma massa parcialmente recriada.
- [x] Testes cobrem recusa, confirmação, falha de backup e reconstrução bem-sucedida.

## Answer

Implementado o comando administrativo `reinicializar_dados_desenvolvimento`,
restrito a `DEBUG=True`, com aviso e confirmação exata `REINICIALIZAR`. Depois
da confirmação, ele reutiliza `criar_backup`; somente após a cópia validada
remove deliberadamente dados operacionais, sessões e dados de demonstração e
reutiliza `carregar_dados_iniciais`. Limpeza e recriação compartilham a mesma
transação, com rollback integral em falhas e eventos de sucesso somente após
commit.

