# 02: Configurar persistência SQLite durável

**What to build:** uma configuração de SQLite persistente no servidor central que priorize a durabilidade dos commits e ofereça uma base verificável para as futuras operações transacionais.

**Blocked by:** 01 — Inicializar o monólito Django.

**Status:** ready-for-agent

- [ ] O banco usa um diretório persistente e conhecido, fora de diretórios temporários ou dependentes da sessão.
- [ ] Cada conexão operacional habilita WAL e `synchronous=FULL`.
- [ ] A inicialização verifica a configuração efetiva e falha com mensagem compreensível quando a garantia não puder ser aplicada.
- [ ] O arquivo SQLite não é preparado para acesso direto por clientes nem para uso em pasta de rede compartilhada.
- [ ] Testes de integração usam SQLite real e verificam os pragmas e a permanência de um registro após reabrir a conexão.
- [ ] A documentação deixa explícito que transações de escrita devem ser curtas e não podem depender de bloqueio de linha.

