# 04: Selecionar e trocar o Usuário operacional

**What to build:** um fluxo inicial no qual a pessoa escolhe um Usuário operacional pré-carregado, entra na experiência correspondente ao papel e só muda de identidade por uma ação explícita.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente.

**Status:** ready-for-agent

- [ ] A tela inicial apresenta Garçom 1, Garçom 2 e Caixa 1 com seus papéis.
- [ ] A escolha persiste durante a navegação e direciona à interface adequada ao papel.
- [ ] A ação “Trocar usuário” retorna explicitamente à seleção e não ocorre de forma implícita.
- [ ] O identificador selecionado fica disponível para ser enviado e validado pelo backend nas operações posteriores.
- [ ] A interface é utilizável em dimensões representativas de celular e desktop.
- [ ] Testes cobrem seleção, persistência da escolha, troca explícita e usuário inexistente.

