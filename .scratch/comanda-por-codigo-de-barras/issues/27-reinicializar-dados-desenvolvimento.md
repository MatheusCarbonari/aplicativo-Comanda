# 27: Reinicializar dados de desenvolvimento com segurança

**What to build:** um comando exclusivo de desenvolvimento que recrie a massa inicial somente após avisar sobre a remoção dos dados operacionais, obter confirmação e gerar um backup válido.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente; 23 — Criar backup SQLite seguro.

**Status:** ready-for-agent

- [ ] O comando nunca é executado automaticamente nem aparece na interface operacional.
- [ ] Antes de qualquer remoção, ele identifica claramente o ambiente e os dados que serão perdidos.
- [ ] Sem confirmação explícita, nenhuma alteração ou limpeza ocorre.
- [ ] A limpeza só começa depois de um backup seguro e validado.
- [ ] Ao concluir, a massa inicial é recriada sem duplicidades.
- [ ] Falha antes do commit não deixa uma massa parcialmente recriada.
- [ ] Testes cobrem recusa, confirmação, falha de backup e reconstrução bem-sucedida.

