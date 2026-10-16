# 15: Gerar a folha de códigos de barras

**What to build:** uma página utilitária separada que apresente códigos Code 128 imprimíveis para as comandas físicas pré-carregadas, destinada exclusivamente ao desenvolvimento e à demonstração.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente.

**Status:** resolved

- [x] A página mostra um código Code 128 e o texto legível para cada comanda de `001` a `020`.
- [x] A geração usa o Identificador da comanda sem convertê-lo em número.
- [x] O layout de impressão produz uma folha de teste legível e não inclui controles operacionais desnecessários.
- [x] A página deixa claro que não representa impressão de recibos, documentos fiscais ou comandas operacionais.
- [x] Recursos necessários funcionam sem CDN ou internet externa.
- [x] Testes verificam o conjunto de comandas e a preservação dos identificadores; a legibilidade física integra o roteiro manual.

## Answer

A rota utilitária `/utilitarios/codigos-barras/` consulta no banco somente as
Comandas com Identificador textual de `001` a `020`. Cada valor é codificado
localmente em Code 128 conjunto B, incluindo checksum, parada e margens
silenciosas, e renderizado como SVG com o Identificador legível abaixo.

A página usa apenas template Django e CSS local, com grade específica para
impressão A4 e aviso de que a folha serve exclusivamente para desenvolvimento e
demonstração. Nenhuma dependência foi adicionada. O README documenta o roteiro
manual para imprimir em escala de 100% e conferir a leitura física.

