# 02: Configurar persistência SQLite durável

**What to build:** uma configuração de SQLite persistente no servidor central que priorize a durabilidade dos commits e ofereça uma base verificável para as futuras operações transacionais.

**Blocked by:** 01 — Inicializar o monólito Django.

**Status:** resolved

- [x] O banco usa um diretório persistente e conhecido, fora de diretórios temporários ou dependentes da sessão.
- [x] Cada conexão operacional habilita WAL e `synchronous=FULL`.
- [x] A inicialização verifica a configuração efetiva e falha com mensagem compreensível quando a garantia não puder ser aplicada.
- [x] O arquivo SQLite não é preparado para acesso direto por clientes nem para uso em pasta de rede compartilhada.
- [x] Testes de integração usam SQLite real e verificam os pragmas e a permanência de um registro após reabrir a conexão.
- [x] A documentação deixa explícito que transações de escrita devem ser curtas e não podem depender de bloqueio de linha.

## Answer

O banco operacional passou a usar `.local/dados/restaurante.sqlite3`. Toda nova conexão Django aplica `journal_mode=WAL` e `synchronous=FULL` pelo mecanismo nativo do backend e tem os valores efetivos validados pelo hook de criação da conexão. Um system check força e valida a conexão durante a inicialização, apresentando erro claro quando a garantia não é atendida. Os testes usam arquivo SQLite real, observam `wal` e `2` (`FULL`) e comprovam que um registro confirmado permanece após fechar e reabrir a conexão.

