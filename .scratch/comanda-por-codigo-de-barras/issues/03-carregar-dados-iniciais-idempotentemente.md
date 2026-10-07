# 03: Carregar dados iniciais idempotentemente

**What to build:** uma carga inicial repetível que disponibilize as comandas físicas, os produtos e os usuários operacionais necessários à demonstração sem alterar dados operacionais existentes.

**Blocked by:** 02 — Configurar persistência SQLite durável.

**Status:** resolved

- [x] A carga cria as comandas físicas com Identificador da comanda de `001` a `020`, preservando zeros à esquerda.
- [x] A carga cria Garçom 1, Garçom 2 e Caixa 1 com os papéis definidos na especificação.
- [x] A carga cria os dez produtos e seus preços em centavos conforme a massa aprovada.
- [x] Executar a carga novamente não duplica nem sobrescreve registros já existentes.
- [x] A inicialização normal nunca remove Atendimentos, lançamentos ou cancelamentos.
- [x] Testes com SQLite real comprovam a primeira carga, a repetição idempotente e a preservação de dados preexistentes.

## Answer

Foram criados os modelos mínimos de Comanda física, Produto e Usuário operacional, com unicidade nas respectivas identidades naturais. A massa inicial é carregada somente pelo comando explícito `carregar_dados_iniciais`, que usa `get_or_create` dentro de uma transação: os valores aprovados são usados apenas na criação e registros existentes nunca são sobrescritos ou removidos. A migration é exclusivamente estrutural e a inicialização do Django não executa a carga implicitamente.

