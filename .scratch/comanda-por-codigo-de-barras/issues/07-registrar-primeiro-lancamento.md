# 07: Registrar o primeiro Lançamento

**What to build:** o fluxo móvel no qual um Garçom confirma o primeiro consumo de uma Comanda disponível e cria atomicamente o Atendimento com seu primeiro Lançamento.

**Blocked by:** 06 — Consultar o estado de uma Comanda física.

**Status:** resolved

- [x] A visão do Garçom permite selecionar Produto, informar quantidade e confirmar o Lançamento.
- [x] Somente quantidade inteira positiva é aceita; zero, valores negativos e fracionários são rejeitados com feedback claro.
- [x] Produto e Comanda física precisam existir, e o Usuário operacional precisa ter papel `GARCOM`.
- [x] O Atendimento e o primeiro Lançamento são confirmados na mesma transação ou integralmente revertidos.
- [x] O Lançamento preserva quantidade, preço vigente em centavos, Garçom responsável e instante UTC definido pelo backend.
- [x] Após o sucesso, a Comanda física aparece em atendimento e o total é exibido em BRL.
- [x] Testes unitários, de aplicação, SQLite real e interface cobrem sucesso, validações, autorização e rollback.

## Answer

Implementado o primeiro Lançamento como operação exclusiva de Garçom. O caso de
uso valida as referências e a quantidade, cria Atendimento e Lançamento em uma
transação curta e copia o preço vigente do Produto. O SQLite protege quantidade
positiva e continua garantindo um único Atendimento aberto por Comanda física.

A interface do Garçom oferece o formulário e apresenta confirmação com total em
BRL; a interface do Caixa não expõe a ação e o backend responde 403 à tentativa.
Testes unitários, de aplicação, integração SQLite e interface cobrem validações,
autorização, snapshot de preço e rollback integral.

