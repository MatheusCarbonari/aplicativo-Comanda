# 06: Consultar o estado de uma Comanda física

**What to build:** a consulta de uma Comanda física pelo seu identificador textual, permitindo ao Garçom ou Caixa distinguir uma comanda disponível, uma comanda em atendimento e um identificador desconhecido sem criar Atendimento.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente; 04 — Selecionar e trocar o Usuário operacional.

**Status:** resolved

- [x] A consulta preserva zeros à esquerda e encontra somente comandas físicas previamente cadastradas.
- [x] Uma Comanda disponível apresenta “Comanda disponível — nenhum atendimento aberto”.
- [x] Um identificador desconhecido apresenta “Comanda não encontrada” e não cria qualquer registro.
- [x] Consultar uma Comanda disponível não abre Atendimento nem altera seu estado.
- [x] O backend carrega o Usuário operacional informado e valida que o papel pode usar a consulta correspondente.
- [x] Testes de caso de uso, integração com SQLite e interface cobrem os três resultados da consulta.

## Answer

Foi criado o caso de uso `consultar_estado_comanda`, que recarrega o Usuário operacional pelo identificador persistido, aceita somente Garçom ou Caixa e busca a Comanda física pelo identificador textual exato. O resultado distingue `DISPONIVEL`, `EM_ATENDIMENTO` e `NAO_ENCONTRADA` sem executar escrita. O modelo mínimo Atendimento possui estados aberto/encerrado e uma restrição condicional no banco que impede mais de um Atendimento aberto por Comanda. A interface oferece consulta GET para os dois papéis e apresenta somente o identificador e o estado atual.

