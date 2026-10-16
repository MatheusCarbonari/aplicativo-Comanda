# 14: Usar leitor de código de barras como teclado

**What to build:** permitir que o Caixa consulte uma Comanda física tanto digitando quanto usando um leitor que escreve o identificador e envia Enter, sem criar fluxos de negócio diferentes.

**Blocked by:** 13 — Consultar a Comanda como Caixa.

**Status:** resolved

- [x] O campo preserva o Identificador da comanda como texto, incluindo zeros à esquerda.
- [x] Enter e o botão “Consultar” chamam o mesmo fluxo e produzem resultados equivalentes.
- [x] Não existe dependência de driver, API proprietária ou acesso direto ao dispositivo leitor.
- [x] Entradas desconhecidas e comandas disponíveis preservam as mensagens definidas na consulta comum.
- [x] Testes de interface simulam digitação, Enter e clique no botão.
- [x] O ticket documenta um roteiro curto para validação manual posterior com leitor físico.

## Answer

O formulário compartilhado de consulta declara explicitamente um campo textual,
preserva o Identificador informado e recebe foco automático somente na experiência
do Caixa. O comportamento nativo do HTML envia tanto `Enter` quanto o clique em
`Consultar` pelo mesmo formulário `GET`, para a mesma view e o mesmo caso de uso
já existentes; nenhum JavaScript ou acesso ao dispositivo foi adicionado.

Os testes de interface verificam o contrato do formulário, a preservação de
`001`, a equivalência das submissões e as mensagens existentes para Comanda
disponível ou desconhecida. O README registra o roteiro de validação posterior
com um leitor físico configurado como teclado.

