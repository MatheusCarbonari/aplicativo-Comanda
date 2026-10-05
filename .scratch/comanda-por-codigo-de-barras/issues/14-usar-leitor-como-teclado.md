# 14: Usar leitor de código de barras como teclado

**What to build:** permitir que o Caixa consulte uma Comanda física tanto digitando quanto usando um leitor que escreve o identificador e envia Enter, sem criar fluxos de negócio diferentes.

**Blocked by:** 13 — Consultar a Comanda como Caixa.

**Status:** ready-for-agent

- [ ] O campo preserva o Identificador da comanda como texto, incluindo zeros à esquerda.
- [ ] Enter e o botão “Consultar” chamam o mesmo fluxo e produzem resultados equivalentes.
- [ ] Não existe dependência de driver, API proprietária ou acesso direto ao dispositivo leitor.
- [ ] Entradas desconhecidas e comandas disponíveis preservam as mensagens definidas na consulta comum.
- [ ] Testes de interface simulam digitação, Enter e clique no botão.
- [ ] O ticket documenta um roteiro curto para validação manual posterior com leitor físico.

