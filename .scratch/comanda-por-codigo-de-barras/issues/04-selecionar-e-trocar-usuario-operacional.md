# 04: Selecionar e trocar o Usuário operacional

**What to build:** um fluxo inicial no qual a pessoa escolhe um Usuário operacional pré-carregado, entra na experiência correspondente ao papel e só muda de identidade por uma ação explícita.

**Blocked by:** 03 — Carregar dados iniciais idempotentemente.

**Status:** resolved

- [x] A tela inicial apresenta Garçom 1, Garçom 2 e Caixa 1 com seus papéis.
- [x] A escolha persiste durante a navegação e direciona à interface adequada ao papel.
- [x] A ação “Trocar usuário” retorna explicitamente à seleção e não ocorre de forma implícita.
- [x] O identificador selecionado fica disponível para ser enviado e validado pelo backend nas operações posteriores.
- [x] A interface é utilizável em dimensões representativas de celular e desktop.
- [x] Testes cobrem seleção, persistência da escolha, troca explícita e usuário inexistente.

## Answer

A aplicação usa a sessão padrão do Django para persistir somente o identificador do Usuário operacional escolhido. Em cada requisição, o backend recarrega o registro e usa o papel armazenado no banco para direcionar à experiência-base de Garçom ou Caixa. A troca ocorre exclusivamente por uma ação POST explícita que remove a seleção. Identificadores inválidos ou usuários removidos limpam a sessão e retornam à seleção com aviso, sem criar registros. Esse fluxo operacional não é apresentado como autenticação.

