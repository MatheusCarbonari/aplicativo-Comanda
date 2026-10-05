# 15: Gerar a folha de códigos de barras

**What to build:** uma página utilitária separada que apresente códigos Code 128 imprimíveis para as comandas físicas pré-carregadas, destinada exclusivamente ao desenvolvimento e à demonstração.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente.

**Status:** ready-for-agent

- [ ] A página mostra um código Code 128 e o texto legível para cada comanda de `001` a `020`.
- [ ] A geração usa o Identificador da comanda sem convertê-lo em número.
- [ ] O layout de impressão produz uma folha de teste legível e não inclui controles operacionais desnecessários.
- [ ] A página deixa claro que não representa impressão de recibos, documentos fiscais ou comandas operacionais.
- [ ] Recursos necessários funcionam sem CDN ou internet externa.
- [ ] Testes verificam o conjunto de comandas e a preservação dos identificadores; a legibilidade física integra o roteiro manual.

