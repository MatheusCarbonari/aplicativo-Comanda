# 08: Registrar lançamentos adicionais e calcular o total

**What to build:** permitir que qualquer Garçom acrescente novos lançamentos independentes a um Atendimento aberto e veja o Total do atendimento atualizado sem sobrescrever consumos anteriores.

**Blocked by:** 07 — Registrar o primeiro Lançamento.

**Status:** resolved

- [x] Novos lançamentos válidos são associados ao Atendimento aberto já existente.
- [x] Garçons diferentes podem registrar consumos no mesmo Atendimento, preservando a autoria de cada ação.
- [x] Lançamentos repetidos permanecem registros individuais no armazenamento.
- [x] Alterar posteriormente o preço do Produto não modifica o preço já registrado no Lançamento.
- [x] O Total do atendimento soma quantidade multiplicada pelo preço registrado usando somente centavos inteiros.
- [x] Um Atendimento encerrado rejeita novos lançamentos sem produzir efeitos parciais.
- [x] Testes cobrem autoria múltipla, repetição intencional, preço histórico, total e rejeição após Fechamento.

## Answer

Implementado um caso de uso separado para adicionar Lançamentos ao Atendimento
aberto existente, sem criar Atendimento. Cada operação preserva Produto,
quantidade, preço registrado, Garçom e horário em um novo registro independente.

O Total atual é calculado em centavos exclusivamente a partir dos Lançamentos
persistidos. A interface oferece a ação ao Garçom depois da consulta de uma
Comanda em atendimento, mantém o Caixa bloqueado e rejeita Atendimento encerrado
sem criar dados. Testes de domínio, aplicação, SQLite e interface cobrem o fluxo.

