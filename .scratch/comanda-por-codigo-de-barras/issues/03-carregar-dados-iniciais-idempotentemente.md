# 03: Carregar dados iniciais idempotentemente

**What to build:** uma carga inicial repetível que disponibilize as comandas físicas, os produtos e os usuários operacionais necessários à demonstração sem alterar dados operacionais existentes.

**Blocked by:** 02 — Configurar persistência SQLite durável.

**Status:** ready-for-agent

- [ ] A carga cria as comandas físicas com Identificador da comanda de `001` a `020`, preservando zeros à esquerda.
- [ ] A carga cria Garçom 1, Garçom 2 e Caixa 1 com os papéis definidos na especificação.
- [ ] A carga cria os dez produtos e seus preços em centavos conforme a massa aprovada.
- [ ] Executar a carga novamente não duplica nem sobrescreve registros já existentes.
- [ ] A inicialização normal nunca remove Atendimentos, lançamentos ou cancelamentos.
- [ ] Testes com SQLite real comprovam a primeira carga, a repetição idempotente e a preservação de dados preexistentes.

